# LiteGate + NATS 联动部署指南(Linux)

> 从零把 **浏览器 → LiteGate → NATS → Go 消费者 → 浏览器** 这条链路跑通。
>
> 本文档的每一步配置都来自实际跑通的环境,不是示意。
>
> 相关文档:[能力矩阵与消费者契约](./nats_capability_matrix.md) · [消费者框架架构](./nats_sidecar_architecture.md)

---

## 0. 拓扑与部署顺序

```
        浏览器 / 业务方
              │ HTTP
              ▼
  ┌───────────────────────┐
  │  LiteGate             │  :80 / :443   业务流量
  │  内置 NATS Action     │  :9100        指标(仅本机)
  └───────────┬───────────┘
              │ TCP 4222
              ▼
  ┌───────────────────────┐
  │  NATS Server          │  :4222        客户端
  │                       │  :8222        监控(仅本机)
  └───────────┬───────────┘
              │ TCP 4222
              ▼
  ┌───────────────────────┐
  │  natsconsume          │  :9101        指标(仅本机)
  │  (Go 消费者)          │
  └───────────────────────┘
```

**按这个顺序部署,每步都能独立验证:**

| 步骤 | 部署 | 验证方式 |
|---|---|---|
| 1 | NATS Server | `nats-server --version`、监控端口有响应 |
| 2 | LiteGate | 访问 `/hello` 返回 **503 + `no_responders`** ← **这是正确的中间状态** |
| 3 | 消费者 | 访问 `/hello` 返回 200 |

第 2 步那个 503 很关键:它证明**网关到 NATS 这半条链路已经通了**,只是还没有消费者。如果这时报的不是 `no_responders` 而是 `unavailable`,说明问题在网关连不上 NATS,而不是缺消费者 —— 两者的排查方向完全不同。

---

## 1. 部署 NATS Server

### 1.1 安装

官方一键脚本会把二进制下载到当前目录,再自行移到 `PATH`:

```bash
# NATS Server
curl -sf https://binaries.nats.dev/nats-io/nats-server/v2@latest | sh
sudo mv nats-server /usr/local/bin/
nats-server --version          # nats-server: v2.14.6

# nats CLI —— 排障时最有用的工具,强烈建议一起装
curl -sf https://binaries.nats.dev/nats-io/natscli/nats@latest | sh
sudo mv nats /usr/local/bin/
nats --version
```

> ⚠️ **`@latest` 解析到的是 commit 而不是 tag**(安装输出里的 `Resolved version latest to 1aa10f9` 就是)。同一条命令在不同时间跑会装出不同的构建。生产环境请把版本固定下来,或把二进制纳入你自己的制品库,否则重装机器时拿到的不是同一个版本。

### 1.2 用户与目录

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin nats
sudo mkdir -p /etc/nats /var/lib/nats
sudo chown -R nats:nats /var/lib/nats
```

### 1.3 配置(内网最小配置)

`/etc/nats/nats-server.conf`:

```hocon
server_name: nats-1
listen: 0.0.0.0:4222

# 监控端口只绑本机:它没有鉴权,暴露出去等于泄漏内部拓扑
http: 127.0.0.1:8222

# 单条消息上限。必须 ≥ 路由的 max_request_body,
# 否则超限的请求会在发布时被服务端拒绝
max_payload: 2MB

# JetStream。同步 hello world 用不到,但提前打开可以省一次重启;
# mode: jetstream_publish 的可靠异步必须要它
jetstream {
  store_dir: /var/lib/nats/jetstream
}
```

就这些。**没有配置鉴权** —— 内网跑通阶段配置越少越好,变量越少越容易定位问题。

> 🔒 **代价要清楚:4222 现在对任何能连上它的人完全开放** —— 可以订阅任意 subject、可以发布任意消息。**此时防火墙是唯一的防护**,所以 1.5 节那步不能省。
>
> 正式上线前再加账号权限,配置见第 6 节的加固清单。

### 1.4 systemd

`/etc/systemd/system/nats.service`:

```ini
[Unit]
Description=NATS Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=nats
Group=nats
ExecStart=/usr/local/bin/nats-server -c /etc/nats/nats-server.conf
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=5
LimitNOFILE=65536

# 加固:除数据目录外全部只读
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=/var/lib/nats

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now nats
sudo systemctl status nats --no-pager
```

### 1.5 防火墙 —— 没有鉴权时这一步不能省

**4222 只对网关和消费者所在主机开放**,绝不能对公网开:

```bash
sudo ufw allow from <litegate_ip> to any port 4222 proto tcp
sudo ufw allow from <consumer_ip> to any port 4222 proto tcp
sudo ufw reload
```

单机全在一台服务器上跑的话,把 `listen` 改成 `127.0.0.1:4222` 更省事,连防火墙都不用配。

### 1.6 验证

```bash
# 服务端自身状态
curl -s http://127.0.0.1:8222/varz | head -20

# 连通性
nats --server nats://127.0.0.1:4222 server check connection

# 收发自测:开两个终端
nats --server nats://127.0.0.1:4222 sub 'demo.>'          # 终端 1
nats --server nats://127.0.0.1:4222 pub demo.test 'hi'     # 终端 2
```

终端 1 能收到 `hi`,说明 NATS 这一层就绪了。

---

## 2. 部署 LiteGate

### 2.1 编译

**NATS Action 已默认编译进标准二进制，无需额外 build tag。** 未配置 NATS 路由时采用懒连接，不会主动连接 NATS Server。

```bash
cd /path/to/LiteGate
CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o bin/litegate ./cmd/litegate
```

> ⚠️ 编译目标必须是 **package**（`./cmd/litegate`），不能是单个文件（`./cmd/litegate/main.go`）。后者会把同 package 下的 `plugins.go` 排除掉，插件的 `init()` 不会执行。

**立刻自检**,别等站点加载失败才发现:

```bash
./bin/litegate plugins list
```

输出里必须有:

```
KIND             NAME                             VERSION        API
action           nats                             -              -
```

Docker 构建:

```bash
docker build -t litegate:nats .
```

### 2.2 目录结构

```bash
sudo mkdir -p /opt/litegate/{bin,sites,certs}
sudo install -m 0755 bin/litegate /opt/litegate/bin/litegate
sudo useradd --system --no-create-home --shell /usr/sbin/nologin litegate
sudo chown -R litegate:litegate /opt/litegate
```

```
/opt/litegate/
├── bin/litegate
├── config.yaml            # 主配置
├── plugin-config.yaml     # 插件配置:NATS 连接与凭据
├── sites/
│   └── demo.yaml          # 站点与路由
└── certs/
```

### 2.3 `config.yaml`

```yaml
mode: observability
sites_dir: "/opt/litegate/sites"

entrypoints:
    web:
        address: ":80"

http:
    port: 80
    https_port: 443

# 插件配置文件。watch: true 支持热更新连接参数,
# 网关会 make-before-break 切换连接,在途请求不受影响。
plugin_config:
    path: /opt/litegate/plugin-config.yaml
    watch: true

# 指标只绑本机,由 Prometheus 通过内网抓取或经反代暴露
metrics:
    enabled: true
    address: "127.0.0.1"
    port: 9100
```

### 2.4 `plugin-config.yaml`

```yaml
plugins:
  nats:
    connections:
      demo:
        servers: "nats://127.0.0.1:4222"   # NATS 在别的机器就换成它的地址
        connect_timeout: "3s"
        reconnect_wait: "1s"
        max_reconnects: "-1"               # -1 = 无限重连
```

NATS 尚未开鉴权,所以这里不需要 `user`/`password`。加了鉴权之后补上即可,格式见第 6 节。

- 多个地址用**逗号分隔**写在一个字符串里:`"nats://a:4222,nats://b:4222"`
- `servers` 缺失时**直接报错**,不会静默回退到 localhost
- NATS 启用 TLS 时,`servers` 写 `tls://host:4222`,并可配下列键(文件在拨号时读取,证书轮换需重启或改动连接配置触发重连):

  | 键 | 说明 |
  |---|---|
  | `tls_ca` | 校验服务端证书的 CA(PEM)。私有 CA 必填,否则走系统根证书 |
  | `tls_cert` / `tls_key` | 客户端证书与私钥(mTLS),必须成对配置,否则加载期报错 |
  | `tls_server_name` | 覆盖证书校验用的主机名(按 IP 连接、证书只签了域名时用) |
  | `tls_first` | `true` 时先握手再收 INFO,对应服务端 `handshake_first` |

- 所有值都经 `os.ExpandEnv` 展开。**含 `$` 字面量的密码会被误展开成空串** —— 将来配密码时如果撞上这点,改用 `credentials` 指向 `.creds` 文件

### 2.5 `sites/demo.yaml`

```yaml
domain: "0.0.0.0"          # 或换成你的域名
entrypoints: ["web"]
routes:
  - name: "hello-nats"
    match:
      path: "/hello"
    action:
      type: "nats"
      mode: "request"
      connection: "demo"           # 对应 plugin-config.yaml 里的连接名
      subject: "demo.hello.v1"
      max_in_flight: 100           # 在途上限,超了立即 429,不让洪峰压垮消费者
```

> ⚠️ **不要在这里写 `timeout`。**
>
> `timeout` 与 LiteGate 内建的 Action 字段重名,插件读不到它:
> - 写 `timeout: 5s` → **整个站点加载失败**(`cannot unmarshal !!str '5s' into int`)
> - 写 `timeout: 5` → 静默落入内建字段,插件仍用自己的默认值
>
> 同步超时目前固定为 **5s**。详见[能力矩阵 5.2 节](./nats_capability_matrix.md)。

### 2.6 systemd

`/etc/systemd/system/litegate.service`:

```ini
[Unit]
Description=LiteGate
After=network-online.target nats.service
Wants=network-online.target

[Service]
Type=simple
User=litegate
Group=litegate
WorkingDirectory=/opt/litegate
ExecStart=/opt/litegate/bin/litegate -config /opt/litegate/config.yaml
Restart=always
RestartSec=5
LimitNOFILE=65536

# 绑定 80/443 但不以 root 运行
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=/opt/litegate

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now litegate
sudo journalctl -u litegate -f
```

启动日志里应该看到:

```
Shared plugin configuration loaded  path:/opt/litegate/plugin-config.yaml version:1
Loaded generic site                 domain:0.0.0.0 mode:yaml
LiteGate HTTP starting on :80
```

### 2.7 ✅ 阶段验证 —— 此时应该是 503

**消费者还没部署,所以现在访问必须返回 503。这是成功的标志,不是失败。**

```bash
curl -i http://127.0.0.1/hello
# HTTP/1.1 503 Service Unavailable
```

关键是确认**原因**:

```bash
curl -s http://127.0.0.1:9100/metrics | grep litegate_nats_requests_total
```

| 看到什么 | 含义 | 下一步 |
|---|---|---|
| `result="no_responders"` | ✅ **网关↔NATS 已通,只是没有消费者** | 继续第 3 步 |
| `result="unavailable"` | ❌ 网关连不上 NATS | 查 4222 连通性、账号密码、防火墙 |
| 没有任何 `litegate_nats_*` | ❌ 请求根本没进插件 | 查路由是否匹配、`plugins list` 是否有 nats |

再看连接状态:

```bash
curl -s http://127.0.0.1:9100/metrics | grep litegate_nats_connection_status
# litegate_nats_connection_status{connection="demo"} 1     ← 1 = 连接正常
```

---

## 3. 部署消费者

消费者是**独立项目**(`ecp.natsconsume.template.v1`),完整说明见该仓库的 `docs/extend_consumer.md`。这里只给跑通 hello world 的最小配置。

```bash
cd /path/to/ecp.natsconsume.template.v1
make linux                    # 产物在 cmd/bin/,版本号由 git describe 注入

sudo mkdir -p /opt/natsconsume
sudo install -m 0755 cmd/bin/natsconsume_linux_amd64 /opt/natsconsume/natsconsume
/opt/natsconsume/natsconsume -version
```

在 Windows 上交叉编译 Linux 产物也是同一条命令 —— `make all` 会一次编出 Windows / Linux(x64、ARM)/ macOS 五个平台,结束后自动复位 `GOOS/GOARCH`。

`natsconsume.json`:

```jsonc
{
  "app": {
    "instance_lock": "/var/run/natsconsume.lock",
    "shutdown_timeout": "30s",
    "log_level": "info",
    "metrics_addr": "127.0.0.1:9101"
  },
  "nats": {
    "servers": "nats://127.0.0.1:4222",
    "connect_timeout": "3s",
    "reconnect_wait": "1s",
    "max_reconnects": -1
  },
  "subscriptions": [
    {
      "enabled": true,
      "subject": "demo.hello.v1",       // 必须与路由里的 subject 完全一致
      "queue_group": "hello_workers",   // 同组实例自动负载分担
      "classname": "hello",
      "command": "demo.hello",
      "mode": "request",                // 必须与路由的 mode 对应
      "concurrency": 4,
      "queue_size": 32,
      "timeout": "5s"
    }
  ],
  "handlers": {}
}
```

> 配置文件支持 `//` 注释(上面示例里的就是),解析时会自动剥掉,且不影响 `nats://` 这类 URL。

**三处必须与网关对齐**,不一致的表现各不相同:

| 配置项 | 不一致的后果 |
|---|---|
| `subject` | 消息发出去没人收 → 网关 `no_responders` → 503 |
| `mode` | `request` ↔ `jetstream` 对不上,消费者启动期报错或永远收不到消息 |
| `envelope` | 消费者只支持 `nats_headers`(默认)。网关若配 `envelope_mode: envelope_json`,消费者**启动期直接报错** |

启动:

```bash
/opt/natsconsume/natsconsume -config natsconsume.json
```

日志应出现:

```
natsconsume starting      version=v1.0.0-3-g2ee1738
connected to NATS         connection=default url=nats://127.0.0.1:4222
request consumer started  capacity=36 classname=hello subject=demo.hello.v1
application started       handlers=["echo","hello"]
```

---

## 4. 端到端验证

```bash
curl -s "http://127.0.0.1/hello?name=LiteGate" | head -5
```

浏览器打开 `http://<网关IP>/hello?name=LiteGate`,会看到一个由**消费者**生成的页面,上面列出:

- **Request ID** —— 网关生成的 UUID,客户端伪造不了,同时是全链路追踪和业务幂等的键
- **Query** —— `name=LiteGate`,证明 query string 完整穿过了整条链路
- **剩余 deadline** —— 网关传下来的绝对截止时间

两侧指标确认:

```bash
# 网关
curl -s http://127.0.0.1:9100/metrics | grep 'litegate_nats_requests_total'
# litegate_nats_requests_total{...,result="ok",status="200",...} 1

# 消费者
curl -s http://127.0.0.1:9101/metrics | grep 'consumer_messages_total'
# consumer_messages_total{...,result="ok",...} 1
```

**两边计数应当一致。** 不一致说明有消息在中间被丢了 —— 通常是 NATS 权限或 subject 拼写问题。

---

## 5. 排障对照表

诊断的第一步永远是看 `result` 标签,而不是 HTTP 状态码 —— 同样是 503,原因可能完全不同。

| 现象 | `result` | 原因 | 处理 |
|---|---|---|---|
| 503 | `no_responders` | 没有消费者订阅该 subject | 查消费者是否在跑、subject 是否拼错 |
| 503 | `unavailable` | 网关连不上 NATS | 查 4222 连通、账号密码、防火墙 |
| 503 | `rejected` | 在途超过 `max_in_flight` | 加消费者实例或调大上限 |
| 504 | `timeout` | 消费者 5s 内没回复 | 看消费者的 `queue_wait` 与 `handler_duration` |
| 502 | `bad_reply` | 回复格式非法 | 状态码必须 200–599;`request_id` 必须一致 |
| 413 | `too_large` | 请求体超 `max_request_body` | 调大该值,并确认 ≤ NATS `max_payload` |
| 启动失败 | — | `unknown action type: nats` | 编译了单文件而非 `./cmd/litegate` package，或使用了不含 NATS 的旧版本二进制 |
| 启动失败 | — | `cannot unmarshal !!str '5s' into int` | 路由里写了 `timeout`,删掉它 |

### 慢:先分清是"排队"还是"业务慢"

这两个数的**比值**决定处方,而处方是相反的:

```bash
curl -s http://127.0.0.1:9101/metrics | grep -E 'consumer_(queue_wait|handler_duration)_seconds_sum'
```

| 现象 | 结论 | 处方 |
|---|---|---|
| queue_wait 大、handler_duration 小 | 并发不够 | 加 `concurrency` 或加实例 |
| queue_wait 小、handler_duration 大 | 业务或数据库慢 | 优化 SQL |
| 两者都大 | 先治业务 | **加并发只会让数据库更糟** |

只看总延迟区分不了,而猜错方向会让情况更坏。

### 常用命令

```bash
# 谁在订阅这个 subject?
nats --server nats://127.0.0.1:4222 sub 'demo.>' --count=1

# 直接向 subject 发请求,绕开网关 —— 用来判断问题在网关还是消费者
nats --server nats://127.0.0.1:4222 request demo.hello.v1 '' --timeout=5s

# 服务端连接数与慢消费者统计
curl -s http://127.0.0.1:8222/connz | head -30
```

第二条命令是**最有效的二分手段**:它能直接回答"是网关的问题还是消费者的问题"。

---

## 6. 生产加固清单

**安全 —— 内网跑通后、正式上线前必须补齐**

- [ ] **给 NATS 加上账号权限**(跑通阶段跳过了,配置见下)
- [ ] 4222 不对公网开放,只放行网关与消费者主机
- [ ] 8222 监控端口只绑 `127.0.0.1`(它没有鉴权)
- [ ] 凭据走环境变量或 `.creds` 文件,配置文件权限 `0600`
- [ ] 指标端口只绑本机

<details>
<summary><b>NATS 账号权限配置(点开)</b></summary>

追加到 `/etc/nats/nats-server.conf`。**这是不可绕过的底线防护** —— 网关侧的 subject 白名单配置写错时会失效,但服务端权限不会。

```hocon
authorization {
  users = [
    {
      # 网关:只能往 demo.* 发布,以及使用应答 inbox
      user: litegate
      password: "$LITEGATE_NATS_PASSWORD"
      permissions: {
        publish:   { allow: ["demo.>", "_INBOX.>"] }
        # 请求-应答需要网关能收到自己 inbox 的回复
        subscribe: { allow: ["_INBOX.>"] }
      }
    },
    {
      # 消费者:只能订阅 demo.*,并回复到 inbox
      user: consumer
      password: "$CONSUMER_NATS_PASSWORD"
      permissions: {
        subscribe: { allow: ["demo.>", "_INBOX.>"] }
        publish:   { allow: ["_INBOX.>", "$JS.ACK.>"] }
      }
    }
  ]
}
```

> ⚠️ **`$JS.ACK.>` 是 JetStream 消费者确认消息的必备 publish 权限。** 漏了会让 Ack/Nak 全部失败,表现为**消息无限重投** —— 这个症状很难往权限上联想。只用同步模式时可以省略。

改完之后三处要同步:

1. `plugin-config.yaml` 加 `user` / `password`
2. 消费者 `natsconsume.json` 的 `nats` 段加 `user` / `password`
3. `nats` CLI 命令改成 `nats://user:PASS@host:4222`

生产环境把明文密码换成 [NKey 或 JWT 凭据](https://docs.nats.io/running-a-nats-service/configuration/securing_nats/auth_intro)。

</details>

**可靠性**

- [ ] `max_payload` ≥ 路由的 `max_request_body`
- [ ] 每条路由都设了 `max_in_flight` —— **Core NATS 推送没有流控,积压是丢消息而不是排队**
- [ ] 消费者用了 `queue_group`,多实例部署
- [ ] `litegate plugins list` 确认 `nats` 在列

**用到 JetStream 时额外确认**

- [ ] Stream 推荐由**运维预先创建**；若由网关兜底建流，路由中必须显式配置 `create_if_absent` 全量参数（`subjects`、`retention`、`storage`、`max_age`、`duplicates`、`replicas`，绝不使用隐式默认值）
- [ ] Durable consumer 预先创建，消费者配 `stream` 走 Bind
- [ ] **`MaxAckPending` 按整个消费者池规模设置，不是单实例并发** —— 它是 durable 级别的全局限制，所有实例共享
- [ ] 消费者账号有 `$JS.ACK.>` 的 publish 权限
- [ ] **发布去重与消费端最终幂等**：客户端跨 HTTP 超时重试应优先携带稳定的 `Idempotency-Key`（1–64 字符，仅 `[A-Za-z0-9_:-]`）；未提供时才兼容使用 `X-Request-Id`。网关按租户、路由、连接、Stream 和最终 Subject 隔离并推导 `Nats-Msg-Id`；业务消费侧仍须以业务主键/请求 ID 在数据库事务内部做最终去重防重

**可观测**

- [ ] 两侧指标都被 Prometheus 抓取
- [ ] 告警:`result="no_responders"` 持续出现 = 消费者全挂
- [ ] 告警:`litegate_nats_connection_status == 0` = NATS 不可达
- [ ] 日志脱敏:**`LiteGate-Query` 和请求体禁止整体入日志**(常含 token、密钥、个人信息)

---

## 7. 生产级端点配置示例 (/mq/sync 与 /mq/async)

针对遗留 mqserver 资产迁移至 LiteGate 的场景，以下是生产级推荐的完整路由配置（保存至 `/opt/litegate/config.yaml` 或对应 site 配置中）：

```yaml
routes:
  # 1. 同步端点 /mq/sync：持久化投递至 JetStream 并等待 PubAck 确认
  - path: /mq/sync
    methods: [POST]
    action:
      type: nats
      mode: jetstream_publish
      connection: default
      # 动态提取主题：严格要求 JSON 字符串类型；支持前缀规范化与白名单防护
      subject_from: body.topic
      subject_prefix: "legacy."
      subject_allowlist: ["*"]
      # 载荷解包：将嵌套在 JSON content 字段中的实际载荷提取并直接投递为 NATS 消息体
      payload_from: body.content
      # 网关自身的发送与确认超时（与业务处理 deadline 严格解耦）
      publish_timeout: 3s
      max_in_flight: 2000
      max_request_body: 1048576 # 1 MiB
      # 兼容老 mqserver 的统一应答契约
      response_status: 200
      response_body: '{"success":true,"message":"success","code":1,"data":null}'
      # Stream 拓扑校验与兜底自愈配置（所有建流参数显式声明，杜绝配置漂移）
      stream:
        name: LEGACY_MQ
        create_if_absent:
          subjects: ["legacy.>"]
          retention: workqueue
          storage: file
          max_age: 168h        # 7 天
          duplicates: 2m       # 配合客户端 X-Request-Id / Idempotency-Key 的发布去重窗口
          replicas: 1

  # 2. 异步端点 /mq/async：高性能投递模式（经决策论证，统一归并为 jetstream_publish）
  - path: /mq/async
    methods: [POST]
    action:
      type: nats
      mode: jetstream_publish
      connection: default
      subject_from: body.topic
      subject_prefix: "legacy."
      subject_allowlist: ["*"]
      payload_from: body.content
      publish_timeout: 3s
      max_in_flight: 5000
      max_request_body: 1048576
      response_status: 200
      response_body: '{"success":true,"message":"success","code":1,"data":null}'
      stream:
        name: LEGACY_MQ
        create_if_absent:
          subjects: ["legacy.>"]
          retention: workqueue
          storage: file
          max_age: 168h
          duplicates: 2m
          replicas: 1

---

## 8. 下一步

hello world 跑通后:

1. **保留 `echo`/`hello` handler 在生产环境。** 出问题时把 subject 临时切到它，立刻能分辨是链路问题还是业务 handler 问题 —— 这是唯一能快速二分整条链路的工具。
2. 按 `ecp.natsconsume.template.v1/docs/extend_consumer.md` 添加真实业务 handler。
3. 需要可靠异步时，先建好 Stream 和 Durable Consumer，或在网关路由中显式声明 `stream.create_if_absent` 全量参数。
