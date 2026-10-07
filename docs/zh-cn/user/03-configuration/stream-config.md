# Stream 配置参考 (L4 代理)

LiteGate 支持 TCP/UDP 层（Layer 4）的动态端口转发，适用于数据库代理、DNS 转发、游戏服务器等非 HTTP 协议场景。

[L4 site 写法与场景指南](l4-guide.md)


---

## 1. 配置位置

Stream 配置文件存放在 `./streams/` 目录下（可通过 `config.yaml` 的 `streams_dir` 修改），格式为 YAML。

---

## 2. 配置格式

### 静态上游

```yaml
# streams/mysql-proxy.yaml
name: mysql-proxy
port: 3307                     # 本地监听端口
protocol: tcp                  # tcp 或 udp
upstream: "192.168.1.100:3306" # 上游地址
enabled: true
idle_timeout: 300              # 空闲断开 (秒)
```

### 动态发现上游

```yaml
# streams/dns-forward.yaml
name: dns-forward
port: 5353
protocol: udp
upstream_type: litemesh         # 从 Litemesh 发现上游
service_name: coredns           # 服务名
service_tag: "production"       # 可选: 服务标签过滤
lb_policy: round_robin          # round_robin, ip_hash
enabled: true
```

---

## 3. 完整参数列表

| 参数 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `site` | string | ⬜ | 统一地址：`tcp://:PORT`、`udp://:PORT`、`tcp://HOSTNAME`。 |
| `proxy` | string | ⬜ | `upstream` 的别名，两者不能同时配置。 |
| `name` | string | ⬜ | Stream 名称，用于日志和 Dashboard 展示。 |
| `port` | int | 条件必填 | 本地监听端口；`listen: false` 时省略。 |
| `listen` | bool | ⬜ | 是否自行监听 `port`，默认为 `true`；Entrypoint 挂载或 Forward Stream 必须设为 `false`。 |
| `entrypoints` | list | ⬜ | 要挂载的共享入口；目前支持 `[websecure]`。配置后自动生成 SNI Stream 路由。 |
| `hostnames` | list | 条件必填 | 挂载共享入口时的 SNI 域名；也作为 `tls.auto_cert` 的默认证书域名。 |
| `protocol` | string | ✅ | 传输协议：`tcp`、`udp` 或 `socks5`。 |
| `upstream` | string | ⬜ | 静态上游地址：`host:port`、`tcp://host:port` 或 TCP Stream 使用的 `unix:///absolute/path.sock`。与 `service_name` 二选一；`protocol: socks5` 时可省略（由客户端动态指定目标）。 |
| `upstream_type` | string | ⬜ | 上游类型：`litemesh`, `consul`。 |
| `service_name` | string | ⬜ | 动态发现时的服务名。 |
| `service_tag` | string | ⬜ | 动态发现时的标签过滤。 |
| `lb_policy` | string | ⬜ | 负载均衡策略：`round_robin` (默认), `ip_hash`。 |
| `enabled` | bool | ⬜ | 是否启用。默认 `true`。 |
| `idle_timeout` | int | ⬜ | 空闲连接超时（秒）。默认 60 秒。 |
| `max_sessions` | int | ⬜ | 最大并发会话数（UDP 默认为 10000）。 |
| `proxy_protocol` | bool | ⬜ | 发送 Proxy Protocol 头到上游。 |
| `proxy_protocol_version` | int | ⬜ | Proxy Protocol 版本 (1 或 2)。 |
| `proxy_protocol_udp_each_packet` | bool | ⬜ | 仅 UDP/QUIC。`false`(默认)时 PROXY 头只**拼接在会话的首个数据报**前;`true` 时拼接在**每个数据报**前。详见下方说明。 |
| `ip_restriction` | object | ⬜ | Stream 级 IP 黑白名单。 |

一个 Stream 只能选择一种入口模式：自行监听端口，或者挂载到共享 Entrypoint。
配置 `entrypoints` 时必须同时设置 `listen: false` 并省略 `port`；不能把
`listen: true`、`port` 和 `entrypoints` 配在同一个 Stream 中。若同一上游确实
需要独立端口和共享 443 两个入口，请定义两个不同名称的 Stream，并让它们引用
同一个 `upstream` 或 `service_name`。这样两条入口的会话上限、TLS、ACL、指标和
生命周期保持独立。

Forward 是另一种独立入口模式。用于数据库隧道或安全动态代理时，Stream 只需定义
`listen: false`，并且不配置 `entrypoints`、`hostnames` 或 Stream TLS；再由
`sites/forward.example.com.yaml` 的 `forward.stream` 唯一绑定该 Stream。
公网链路由 TLS 加密（默认 Forward v3，见下文），Stream 到内部数据库默认保持普通 TCP；数据库客户端启用的
MySQL/PostgreSQL 原生 SSL 会作为应用协议字节原样穿透。完整示例参见
[数据库安全访问方案](../../database-proxy-solution.md)。

### 内建 SOCKS5 代理模式 (`protocol: socks5`)

LiteGate 原生支持 RFC 1928 标准 SOCKS5 代理协议。结合 Forward 隧道，可将受限网络的动态访问通道安全穿透映射到本地，无需部署任何第三方 SOCKS5 程序：

```yaml
# streams/socks5-forward.yaml
name: my-socks5
listen: false
protocol: socks5
enabled: true
max_sessions: 200
idle_timeout: 600
socks5:
  # 必填。目的地由客户端指定，没有白名单的 SOCKS5 就是一个开放代理。
  # 地址可为 IP/CIDR 或 public/private/any；端口支持单值、范围和逗号列表。
  allowed_destinations:
    - public:80,443
  denied_destinations:        # 可选，始终优先于 allowed_destinations
    - 10.1.2.3/32
```

> **`allowed_destinations` 是必填项。** 缺失或为空时配置校验会直接拒绝加载，因为
> SOCKS5 的目的地由客户端决定：一旦放开，持有 Forward token 的任何人（或能连上
> 监听端口的任何人）都能把网关当跳板。
>
> 判定发生在**解析之后的 IP** 上，而不是请求里的域名，所以指向内网的域名无法绕过规则。
>
> 无论是否写进 `allowed_destinations`，以下范围都默认拒绝：回环
> (`127.0.0.0/8`、`::1`)、链路本地 (`169.254.0.0/16`、`fe80::/10`，含
> `169.254.169.254` 元数据)、阿里云元数据 `100.100.100.200`、AWS IMDSv6
> `fd00:ec2::254`、以及未指定地址。写 `0.0.0.0/0` **不会**解除这些保护；确实需要放行
> 某一段时，必须用比内建规则更精确的前缀显式声明（例如 `127.0.0.0/8:3306`）。
>
> `public` 同时覆盖 IPv4/IPv6 公网地址，并排除私网、CGNAT、ULA、回环、
> 链路本地、多播、文档/测试保留网段等非公网范围。`private` 表示 RFC 1918
> 和 IPv6 ULA（不包含 CGNAT）；`any` 表示 IPv4+IPv6，但仍然受上述内建保护规则限制。
> NAT64、6to4、IPv4-compatible、IPv4-mapped 和 Teredo 地址中承载的 IPv4 也会被再次
> 判定，不能用 IPv6 外壳绕过 `public` 或内建拒绝规则。

对应的 Forward Site 配置：
```yaml
# sites/forward.example.com.yaml
site: forward.example.com
forward:
  stream: my-socks5
  token_file: /etc/litegate/secrets/forward.token
```

如果这个 SOCKS5 Stream 只供一个 Forward Site 使用，可以直接内联，无需创建单独的
`streams/*.yaml` 文件：

```yaml
site: forward.example.com
forward:
  token_file: /etc/litegate/secrets/forward.token
  max_sessions: 200
  idle_timeout: 600
  socks5:
    allowed_destinations:
      - public:80,443
```

内联配置会生成一个名为 `forward:<domain>` 的内部非监听 Stream，便于在 Dashboard、
metrics 和日志中识别。未设置 `idle_timeout` 时默认使用 60 秒。`stream:`、`target:` 和
`socks5:` 互斥；`forward:` 前缀保留给这类内部 Stream，普通 Stream 配置不能使用。
多个 Site 需要共享策略时，仍使用显式 `stream:` 引用。

在本地运行客户端即可在本地提供 SOCKS5 代理端口：
```bash
litegate forward --remote https://forward.example.com --local 127.0.0.1:1080 --token-file ./forward.token
```

如果应用不支持 SOCKS5，可以增加 `--target`。Forward 客户端会在隧道建立后自动完成
SOCKS5 `CONNECT`，本地端口对应用表现为目标服务的原始 TCP 协议：

```bash
litegate forward \
  --remote https://forward.example.com \
  --local 127.0.0.1:13306 \
  --target 10.0.0.25:3306 \
  --token-file ./forward.token
```

此时 Navicat 等客户端直接连接 `127.0.0.1:13306`，不需要配置 SOCKS5。带 `--target`
的客户端必须连接 `protocol: socks5` 的 Stream；如果 Forward Site 指向普通 TCP Stream，
SOCKS5 握手会失败。不带 `--target` 时仍保持原有的透明 Raw Forward 行为。

常驻运行可以把单映射参数写入客户端配置文件：

```yaml
# forward.yaml
version: 1
remote: https://forward.example.com
local: 127.0.0.1:13306
target: 10.0.0.25:3306
token_file: ./forward.token
```

```bash
litegate forward --config ./forward.yaml
```

相对 `token_file` 按 `forward.yaml` 所在目录解析；命令行显式传入的 `--remote`、
`--local`、`--target` 或 `--token-file` 会覆盖文件中的同名字段。

一个客户端进程也可以管理多个命名 mapping：

```yaml
# forward.yaml
version: 1
remotes:
  - https://forward-primary.example.com
  - https://forward-backup.example.com
token_file: ./forward.token

# 监听局域网地址时必须显式确认；全部使用 127.0.0.1 时可省略。
allow_lan_listen: true

mappings:
  - name: mysql
    local: 192.168.50.46:13306
    target: 10.0.0.25:3306

  - name: redis
    local: 127.0.0.1:16379
    target: 10.0.0.26:6379

  - name: ssh
    local: 127.0.0.1:10022
    target: 10.0.0.27:22
    enabled: true
```

`remotes` 初次按顺序尝试，之后优先使用上一次成功的 Cloud，避免主节点黑洞时每个新连接
重复等待。只有 TCP/TLS/WS 等传输失败或服务端容量拒绝才会切换；SOCKS5 策略拒绝、目标
拒绝连接等应用层结果不会重试其他 Cloud。它与兼容旧配置的单值 `remote` 互斥；命令行
`--remote` 会覆盖整个列表。

`name` 和 `local` 必须唯一，`enabled` 省略时默认为 `true`。顶层 `local/target` 与
`mappings` 不能同时出现。启动前会先校验全部 mapping，并尝试绑定全部端口；任一端口
绑定失败时会关闭已经打开的 listener，整个启动失败，不会留下只生效一部分的配置。
多 mapping 模式已经可用，配置热加载仍将在后续版本提供。

#### 传输协议：Forward v3（默认）

客户端默认使用 **Forward v3**：对每个 Cloud 只建立一条 TLS 长连接，通过 HTTP/1.1
Upgrade（`litegate-forward.v3`）鉴权一次，之后每个本地连接只是这条连接上的一个
HTTP/2 CONNECT 流。与每连接一条 WSS 的 v2 相比：

- 新连接不再重复 TCP + TLS + WebSocket 握手，数据库连接池、短连接场景延迟明显下降；
- 存活检测改用 HTTP/2 PING，本地应用暂停读取（慢消费、背压）不会再被误判断开；
- 目标满载（`max_sessions`）等拒绝会返回明确原因，而不是连接被重置。

```yaml
# forward.yaml
transport: auto   # auto（默认）| v3 | v2
```

`auto` 遇到尚未升级的 LiteGate 服务端、检测到 `HTTPS_PROXY` 等代理环境变量，或前置
SLB/WAF/CDN 不放行 v3 的 Upgrade（返回 400、403、502 等）时，会自动回退到 v2（WebSocket，
大多数代理只放行 WebSocket），并在 10 分钟后重新尝试 v3。服务端明确返回的 `429`（会话数超限）
和 `503`（目标不可用）不会触发回退。也可以用 `--transport v2` 临时强制使用旧协议。服务端无需
任何新配置，v2 与 v3 同时支持。两种协议的完整对比见
[Forward 与 Connect 总览](../09-advanced/forward-and-connect.md)。

已建立的 v3 会话在每个新连接上都会重新校验站点配置（与握手时相同的检查）：`token_file`
轮换、站点删除，或站点不再暴露在该会话所经过的 entrypoint 上之后，旧会话上的新连接会收到
403，会话进入吊销状态；已在传输中的连接不受影响，会一直运行到自然结束，最后一个连接结束后
会话才关闭。客户端收到 403 后会用新握手重新鉴权，不会中断同一会话上的其他连接。

为防止持有合法 token 的客户端建立大量空闲会话，服务端限制并发 v3 会话数：每个客户端 IP
默认 32 个、每个站点默认 256 个，超出时握手返回 `429`。正常情况下一个客户端对每个 Cloud
只保持一个会话。

v3 的方向性关闭与 Connect 一致：客户端可以只关闭发送方向（半关闭）并继续接收响应；
服务端一侧先结束发送时，整个流随之结束。

也可以通过配置 `listen: true` 和 `port: 1080` 让 LiteGate 作为一个独立的 SOCKS5 代理监听服务。

> **独立监听模式务必收紧访问面。** `listen: true` 会绑定**所有网卡**，而 SOCKS5 协议本身
> 只支持无认证方式（RFC 1928 `0x00`），没有任何身份校验。公网可达的机器上必须同时配置
> `ip_restriction`（限制来源）和 `socks5.allowed_destinations`（限制去向），否则等同于在
> 公网上开了一个开放代理。只需要本机使用时，建议改走 Forward 隧道而不是直接监听端口。

> **UDP / QUIC 说明。** 对 UDP 上游(含 QUIC),PROXY protocol 头会**拼接到数据报载荷的前面**,而不会作为独立数据报单独发送——否则 QUIC 后端会把这个裸头部包当成损坏的帧丢弃.默认只在每个会话的首个数据报携带该头部(PROXY v2,并正确置位 `DGRAM` 传输字节)。如果后端会独立检查每个数据报,请开启 `proxy_protocol_udp_each_packet: true`。后端必须能识别 PROXY protocol 并在解析 QUIC 前剥离该头部。另外请注意:UDP 会话以客户端源 IP:port 与本地目标 IP (还包含非零的接口索引) 的组合为 key,因此 QUIC 的连接迁移(客户端地址变化)会触发新的上游会话。此外，启用 PROXY protocol 会在 UDP/QUIC 首个或每个数据报前增加 28 字节 (IPv4) 或 52 字节 (IPv6) 的头部开销。对于接近 MTU 上限的数据报，这可能会触发分片或发送失败，请确保您的网络路径 MTU 留有足够裕量。

---

## 4. IP 限制

### 全局 Stream IP 限制

在 `config.yaml` 中配置：

```yaml
stream_ip_restriction:
  allow_ips: ["192.168.0.0/16"]
  deny_ips: ["1.2.3.4"]
```

### Stream 级 IP 限制

在单个 Stream 配置中覆盖全局规则：

```yaml
name: ssh-proxy
port: 2222
protocol: tcp
upstream: "10.0.0.5:22"
ip_restriction:
  allow_ips: ["10.0.0.0/8"]
```

---

## 5. 常见用例

### MySQL / PostgreSQL 数据库代理

```yaml
name: db-proxy
port: 13306
protocol: tcp
upstream: "db-master:3306"
enabled: true
ip_restriction:
  allow_ips: ["10.0.0.0/8", "172.16.0.0/12"]
```

### DNS 转发 (UDP)

```yaml
name: dns-relay
port: 53
protocol: udp
upstream: "8.8.8.8:53"
max_sessions: 20000  # 针对高频 DNS 场景调大上限
enabled: true
```

### SSH 跳板机

```yaml
name: ssh-jump
port: 2222
protocol: tcp
upstream_type: litemesh
service_name: ssh-server
proxy_protocol: true
proxy_protocol_version: 2
```

---

## 6. TLS 卸载 (TLS Termination)

LiteGate 支持在四层 Stream 入口处进行 TLS 终止（卸载），将客户端发来的加密 Raw TLS 流量解密后以明文 TCP 形式转发到后端服务。目前仅在 `protocol: tcp` 下生效。

完整的端口共享工作原理、TLS 透传与终止、证书复用、Unix Socket 生命周期和 Nginx 能力对照，参见[同一个 443 承载 HTTPS 与 L4 TCP](../09-advanced/shared-443-l4-stream.md)。

需要与 HTTPS 共用 443 时，可定义一个不自行监听端口的 Stream：

```yaml
name: database
listen: false
entrypoints: [websecure]
hostnames: [db.example.com]
protocol: tcp
upstream: unix:///run/litegate/database.sock
enabled: true
tls:
  enabled: true
  auto_cert: true
```

LiteGate 根据 `hostnames` 自动生成 SNI 路由；SNI Mux 只负责连接分类，命中后
由该 Stream 完成 TLS 终止及后续 L4 治理。启用 `auto_cert` 且省略
`tls.domains` 时会直接使用 `hostnames`，因此域名只需声明一次。
申请前 LiteGate 会先检查 HTTPS 与 L4 Stream 共用的证书池；如果已有仍在有效期内、
且能覆盖该域名的精确证书或泛域名证书（例如 `*.example.com` 覆盖
`db.example.com`），会直接复用并跳过重复申请。

### TLS 参数配置

| 参数 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `tls.enabled` | bool | ✅ | 是否开启 TLS 卸载。 |
| `tls.passthrough` | bool | ⬜ | 保留原始 TLS，由后端终止；主要用于独立 Stream 的 `tls_routes`。简单的 attached Stream 单上游透传可直接省略整个 `tls` 配置。 |
| `tls.auto_cert` | bool | ⬜ | 是否自动确保证书可用。开启时使用显式 `domains`，未配置时回退到 Stream 的 `hostnames`；共享池已有有效覆盖证书时不会重复申请。 |
| `tls.domains` | list | ⬜ | 自动证书关联的域名列表；共享入口 Stream 通常无需重复配置。 |
| `tls.cert_file` | string | ⬜ | 手工证书的文件路径。与 `key_file` 必须成对配置。 |
| `tls.key_file` | string | ⬜ | 手工私钥的文件路径。与 `cert_file` 必须成对配置。 |
| `tls.min_version` | string | ⬜ | 支持的最小 TLS 协议版本：`1.2` (默认) 或 `1.3`。非法输入会导致配置加载失败报错。 |

### 静态配置示例

```yaml
# streams/db-tls.yaml —— 手工证书
name: db-tls
port: 8443
protocol: tcp
upstream: "10.0.0.5:3306"
enabled: true
tls:
  enabled: true
  cert_file: /etc/litegate/certs/db.crt
  key_file: /etc/litegate/certs/db.key
  min_version: "1.2"
```

```yaml
# streams/db-tls-auto.yaml —— ACME 自动证书
name: db-tls-auto
port: 8443
protocol: tcp
upstream: "10.0.0.5:3306"
enabled: true
tls:
  enabled: true
  auto_cert: true
  domains:
    - db.example.com
```

> 上例使用 `8443`，因为它是一个自行监听端口的独立 Stream。如需与现有 HTTPS 共用 443，不要让 Stream 自行绑定 443；应使用 `listen: false`、`entrypoints: [websecure]` 和 `hostnames` 挂载到共享入口。

### 关键行为说明

1. **独立监听与共享入口**：
   `listen: true`（默认）的独立 Stream 不能再次绑定 LiteGate 已占用的 HTTP/HTTPS 端口。需要共享 443 时使用 `listen: false` 挂载到 `websecure`；HTTPS 无需停用或迁移端口。
2. **手工证书热重载**：
   对于手工证书，LiteGate 会在配置加载时记录证书文件的修改时间戳。如需更新证书内容（文件路径未改变），当重载/修改 Stream 的 YAML 配置文件时，LiteGate 会检测到修改时间戳的变化并自动热重载重启对应的监听器，以加载最新证书。
3. **数据库协议与 Raw TLS 的区别**：
   共享 443 的 SNI 分流要求客户端首包就是带 SNI 的 TLS ClientHello。原生 MySQL TLS 和 PostgreSQL SSLRequest 都先交换应用协议数据，再升级到 TLS，不能直接使用此模式；仅打开数据库客户端的 SSL 选项并不足够。应增加 stunnel 等从首字节开始的 TLS 包装层，或使用独立端口。LiteGate 终止 TLS 后到上游的通信是明文 TCP。
4. **自动证书 (AutoCert) 异步加载延迟**：
   在动态发现或者配置文件 reload 时，证书申请与签发操作 (`EnsureCertificates`) 会在后台异步进行。此时网关会先同步建立四层 Stream 端口监听。在证书签发成功之前的一小段时间内，尝试进行 TLS 握手的客户端连接可能会因为找不到有效证书而失败。建议在业务上容忍这一短暂的冷启动，或首选通过配置手工证书路径来规避异步延迟。

### 动态服务发现标签（自动生成 L4 Stream）

当上游实例在 Consul / Litemesh 注册时，可通过 **Metadata 或 Tags** 声明 L4 端口，网关会自动为其生成对应的 TCP/UDP Stream（无需手写 YAML）。生成的 Stream 命名为 `auto-<服务名>-<协议>-<端口>`。

**端口声明标签**：

| 标签 | 说明 |
| :--- | :--- |
| `litegate.tcp.port=8080` | 网关在 `8080` 端口监听 TCP，转发到实例注册的端口。 |
| `litegate.udp.port=5353` | 网关在 `5353` 端口监听 UDP，转发到实例注册的端口。 |
| `litegate.<group>.tcp.port=8080` | 带命名组，允许单个实例声明多个独立端口（见下文）。 |

- **多端口**：同一实例可声明多个不同的端口标签，将分别生成多个独立 Stream。
- **只有显式声明才开端口**：实例注册的协议是 `tcp`/`udp` 本身不会让网关开监听，必须写端口标签。
- **端口白名单**：标签中的端口必须列在网关的 `service_discovery.tag_entrypoints.allowed_ports` 中，且不能与 config.yaml 的入口、静态 Stream 或保留端口(metrics、dashboard 等)重复。
- **端口冲突**：两个服务声明同一端口时，已经在运行的 Stream 保留端口，后来者被拒绝；两者都是新的时按 Stream 名确定一个。被拒绝的服务在 dashboard 服务标签页显示诊断，其他服务不受影响。
- **故障转移**：TCP 连接某个实例失败时，会换另一个实例重试(最多 3 次)，并计入与 HTTP 相同的被动健康检查(连续失败的实例被临时摘除)。
- **去重**：同一端口若同时由 Metadata 与 Tags 重复声明、或被多个命名组指向，只生成一个 Stream，后端实例不会被重复计入负载均衡。

**TLS 标签**（在上述端口基础上叠加以启用入口 TLS 卸载；命名组需与对应端口标签一致）：

| 标签 | 说明 |
| :--- | :--- |
| `litegate.(<group>.)tcp.tls.enabled=true` | 开启 TLS 终止。 |
| `litegate.(<group>.)tcp.tls.auto_cert=true` | 启用 ACME 自动申请证书。 |
| `litegate.(<group>.)tcp.tls.domains=db.example.com` | 自动证书域名，多个用英文逗号分隔。 |
| `litegate.(<group>.)tcp.tls.cert_file=/etc/certs/db.crt` | 手工证书路径。 |
| `litegate.(<group>.)tcp.tls.key_file=/etc/certs/db.key` | 手工私钥路径。 |
| `litegate.(<group>.)tcp.tls.min_version=1.2` | 最小协议版本，`1.2` 或 `1.3`。 |

> **命名组 `<group>` 的用途**：当一个实例需要暴露多个 L4 端口、且各端口要绑定**不同的 TLS 配置**时，用不同组名加以区分；TLS 标签会按组名匹配到对应端口。
>
> **错误处理**：
> - UDP 协议流不支持 TLS 卸载。若在 UDP 上声明 TLS 标签，将被忽略并打印 Warn 日志。
> - 端口值非法、TLS 标签非法（如 `auto_cert` 缺 `domains`、`cert_file`/`key_file` 未成对、证书加载失败、`min_version` 非法）或各实例 TLS 配置冲突时，**该端口的 Stream 不会创建**(绝不降级为明文)，诊断显示在 dashboard；同一批次中的其他服务照常生效。

---

## 7. 监控

Stream 的运行状态（活跃连接数、流量统计）可以通过 Dashboard 的「Stream」面板实时查看。

| 指标 | 说明 |
| :--- | :--- |
| Active Sessions | 当前活跃连接数 |
| Upload Bytes | 上传总流量 |
| Download Bytes | 下载总流量 |
| Dropped Sessions | 因达到上限而被丢弃的请求数 (仅 UDP) |
| Timeout Closes | 因空闲超时而关闭的连接数 |
