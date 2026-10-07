<!-- GENERATED FILE — DO NOT EDIT.
     Source: internal/configdocs/docs/zh/global-config.md (package internal/configdocs)
     Regenerate: go generate ./internal/configdocs/...
     Edit the source instead; a drift test fails if this copy is edited directly. -->

# 全局配置参考 (`config.yaml`)

`config.yaml` 定义 LiteGate 的监听、证书、注册发现、观测、缓存、认证以及 MCP 暴露方式。

> [!TIP]
> MCP 的 `get_gateway_config_schema` 直接返回本文件内容。这里的字段应与当前代码中的 `internal/config/types.go` 保持一致。

---

## 0. 全局模式 (Mode)

```yaml
# performance: 高性能模式（默认）。指标、访问日志、链路追踪、Dashboard 开启后照常工作
# observability: 每个请求都记录路由明细，并始终推送 Dashboard 实时请求流
mode: "performance"
```

`performance` 只跳过"没有开启任何消费者时"的逐请求统计，开启 `metrics`、`dashboard`、`log.access_log` 或 `tracing` 后对应功能不受影响；开启 Dashboard 时实时请求流也照常推送。需要始终记录路由明细时写 `mode: observability`。

---

## 1. 监听器与 Entrypoints (多端口/网卡绑定)

LiteGate 支持类似 Traefik 的多入口监听器机制，允许不同站点或内部管理接口绑定在不同端口或特定物理网卡（SO_BINDTODEVICE）上。

```yaml
entrypoints:
  web:
    address: ":80"
  websecure:
    address: ":443"
    tls: true
  # internal:
  #   address: ":8080"
  #   interface_name: "eth0"         # 可选。绑定特定 Linux 网络设备名，跟随 DHCP IP 变化

# 传统兼容端口配置（若已配置 entrypoints，则 entrypoints 拥有最高权威）
http:
  port: 80
  https_port: 443
  response_header_timeout: 60    # 可选。默认 HTTP 响应头超时（秒）
  # upstream_transport_shards: 1  # 可选。每个上游实例分摊到几个连接池，降低高并发下的连接池锁竞争；默认 1 = 不分片
  # upstream_buffer_size: 32768   # 可选。上游 HTTP/1 连接读写缓冲（字节，4096～65536，默认 32768）；大响应体会绕过缓冲直接读写
  # upstream_client: fast         # 可选。默认 fast：明文 HTTP/1.1 后端用同步连接池（开销更低），TLS/mTLS/HTTP2/gRPC/WebSocket 自动走标准客户端；写 standard 则全部使用 Go 标准 Transport
  # drain_delay: 5               # 摘流等待秒数；不写 = 自动，0 = 关闭，N = 固定 N 秒
  # drain_delay_ms: 250          # 可选毫秒覆盖值，优先于 drain_delay
```

**停机摘流（`drain_delay`）**：收到停止信号后，`/readyz` 先返回 503，并主动从 Consul / litemesh 注销，然后等待一段时间再关闭监听端口，让前面的负载均衡停止把新请求发过来。

- **不写（默认，自动）**：只在确实有人观察时才等待——已注册到 Consul / litemesh 时，先注销再等 1 秒；最近 2 分钟内 `/readyz` 被探测过（K8s readinessProbe、云负载均衡）时等 5 秒；单机、无人探测时立即停止。
- `drain_delay: 0` 关闭等待；`drain_delay: N` 固定等待 N 秒（例如负载均衡只做 TCP 探测、自动检测不到时）。
- 等待期间再按一次 Ctrl-C（或再发一次 SIGTERM）可立即跳过。
- 从旧版本升级：旧版生成的配置里写着 `drain_delay: 5`，会被视为显式设置而继续等待 5 秒；想用自动模式请删掉这一行。

---

### 1.1 入口插件（Ingress）

编译期插件可在 Site 匹配和路径清理之前接管指定入口上的 HTTP 请求。数组顺序是
执行顺序，返回未处理时继续后续插件与 Site 路由。默认无插件；每个绑定必须有唯一
名称和显式入口列表。缺失插件、未知入口或插件配置错误使配置校验失败。

```yaml
# 标准二进制已编入 forward_proxy；请在 entrypoints 中声明 websecure TLS 入口。
ingress_plugins:
  - name: developer-egress
    type: forward_proxy
    entrypoints: [websecure]
    config:
      username: developer
      hosts: [proxy.example.com]
      password: '$2a$10$REPLACE_WITH_COMPLETE_BCRYPT_HASH'
      probe_resistance: true
      hide_ip: true
      hide_via: true
      allowed_destinations: [example.org, "*.example.org"]
      allowed_ports: [80, 443]
```

先执行 `litegate -hash '你的密码'`，将完整 bcrypt 哈希填入 `password`。
客户端仍使用原始密码。`password_env` 是从环境变量读取原始密码的替代方案，
必须与 `password` 二选一；不接受明文 `password`。`hosts` 匹配 TLS SNI，
不是 CONNECT 的目标 Host；不匹配或没有 TLS/SNI 时回落到正常路由。
省略 `hosts` 不限制入口域名。防探测开启后认证失败回落，需要普通 Site 或兜底站点。
`hide_ip`、`hide_via` 默认开启：普通 HTTP 请求转发时移除已有来源 IP 头与 Via。
显式关闭时分别追加来源 IP 到 Forwarded、追加 LiteGate 的 Via；不改写 CONNECT 数据。

全局来源检查仍先执行；被插件处理的请求不进入 Site 中间件，宿主按 `ingress:<binding name>` 统一记录访问日志、指标和 Dashboard。
LiteGate Forward/Connect 注入的内部流量不执行入口插件。候选实例初始化失败保留
旧实例，成功提交后旧请求在 `http.shutdown_grace` 内排空（未设置时 30 秒），到期取消实例 Context 并带截止时间关闭；关闭进程则立即关闭实例。
共用网站入口时必须配置 `hosts` 或开启 `probe_resistance`，避免本站 absolute-form 请求收到 407。仅改变 `password_env` 所指环境变量值不会重建未变化的绑定，需改变绑定配置或重启。
成功 bcrypt 认证缓存头部 SHA-256 摘要 5 分钟，命中续期并做常量时间比较；每实例最多同时执行两次 bcrypt，等待槽位受请求 Context 约束且最多 100ms。通配规则默认拒绝本机网卡地址、`64:ff9b::/96`、`240.0.0.0/4` 和 `198.18.0.0/15`，有意访问需显式 IP/CIDR。每个解析地址单独使用拨号超时。网卡地址缓存 30 秒后按需刷新；云主机 1:1 NAT 的弹性公网 IP 可能不在网卡上，应显式加入 `denied_destinations`。绑定不变时，仅修改 `shutdown_grace` 不更新复用实例的宽限期，需改变绑定或重启。HTTP/2/3 下载结束即停止上传并结束响应，半关闭只在 HTTP/1 劫持连接上保留。
完整公共契约与运行示例见 [入口插件指南](../../ingress-plugin-guide.md)。

### 1.2 共享 443 的 SNI / L4 分流

`entrypoints.websecure.routes` 在 HTTPS 解密之前检查 TLS ClientHello，根据 SNI
将连接交给 L4 上游或命名 Stream。未匹配的域名继续进入普通 HTTPS 站点。
当前显式传输路由只支持 `websecure`，并要求 `tls: true`。

#### 直接透传到 TLS 后端

下面配置写在 `config.yaml` 中。`tcp.example.com` 的连接原样转发到 TLS 后端，
其他域名继续由 LiteGate 处理 HTTPS：

```yaml
entrypoints:
  web:
    address: ":80"
  websecure:
    address: ":443"
    tls: true
    default: http
    on_non_tls: reject
    on_no_sni: reject
    inspect:
      timeout: 5s
      max_pending: 2048
      per_ip_pending: 16
    routes:
      - name: private-tls
        match:
          sni: tcp.example.com
        handle:
          proxy: tcp://127.0.0.1:444
```

`handle.proxy` 不终止 TLS，后端必须从第一个字节执行 TLS 握手并持有对应证书。
它也支持 `unix:///run/service/tls.sock` 形式的 TCP Unix socket。

#### 推荐：用 Stream 的 site 简写自动生成路由

简单场景不必手写上面的 `routes`。全局保留 `websecure` 监听，在
`streams/database.yaml` 中定义：

```yaml
site: tcp://db.example.com
name: database
proxy: 127.0.0.1:3306
```

它自动挂载 `websecure` 并生成 SNI 路由；无需再在 `config.yaml` 重复配置同一域名。
默认透传 TLS。如需 LiteGate 解密 TLS，再在 Stream 中配置 `tls.enabled: true`
及证书来源；`proxy` 指向的后端此时接收明文 TCP。

需要显式选路到已有 Stream 时，路由写作下面形式，并合并到
`entrypoints.websecure.routes`；名为 `database` 的 Stream 必须已存在且使用
`listen: false`。每条路由的 `handle.proxy` 与 `handle.stream` 二选一：

```yaml
entrypoints:
  websecure:
    address: ":443"
    tls: true
    routes:
      - name: database
        match:
          sni: db.example.com
        handle:
          stream: database
```

| 字段 | 含义 |
| --- | --- |
| `match.sni` | 一个域名或域名列表，支持 `*.example.com`。 |
| `match.sni_regex` | 正则匹配 SNI；简单域名优先用 `sni`。 |
| `match.alpn` | 可选，限制 ClientHello 提供的协议，如 `[h2]`；匹配协议区分大小写。 |
| `handle.proxy` | 原样转发 TLS 的 TCP / Unix socket 后端。 |
| `handle.stream` | 已存在的命名 Stream，执行其 TLS、ACL 和 L4 转发策略。 |
| `default` | 不匹配路由时回落到 HTTP/HTTPS 处理，当前只支持 `http`。 |
| `on_non_tls`, `on_no_sni` | 非 TLS / 无 SNI 时可配置 `http` 或 `reject`。 |
| `inspect` | ClientHello 检查超时与并发上限。 |

显式路由在声明相同 SNI 且未限定 ALPN 时优先于自动 Stream 路由；限定 ALPN
的显式路由只接管对应协议，其余协议仍可使用自动路由。普通明文 TCP 和 UDP
没有 TLS SNI，不能靠此方式按域名分流。UDP/QUIC 也不走这里的 TCP 443 路由。
不要无意间让 L4 Stream 与 HTTP 站点使用相同域名：SNI 分流发生在 HTTP 路由之前。
完整 Stream 场景见 [L4 指南](l4-guide.md)。

## 2. 静态 TLS

```yaml
tls:
  enabled: false
  certs_dir: "./certs"

  # 本地 CA（自签自信任，对标 Caddy tls internal）
  local_ca: false                       # 启用本地 CA 按需为本地域名签发叶子证书
  local_ca_domains: [".localhost", ".test"]   # 允许签发的域名白名单（.开头=后缀匹配）
  local_ca_trust: false                 # 仅首次生成时自动装入系统信任库（建议仅本机开发开启）
```

---

## 3. Auto-Cert

显式关闭 `auto_cert.enabled` 后，不会自动申请或续期，包括 TLS 握手和热更新触发的路径。已启用的 `dns_providers` 域名组先于站点证书准备；组内泛域名覆盖的站点等待该证书，申请失败也不会另发 HTTP-01 单域名订单。泛域名申请使用 DNS-01。

Auto-Cert 默认开启；显式设置 `enabled: false` 可关闭自动签发。具体域名站点在 TCP 443 成功监听后，先复用有效的精确域名、SAN 或泛域名证书，缺少时默认通过 HTTP-01 申请。仅绑定 `web` 的站点、IP 和通配匹配不会触发这条申请路径。

`https: true` 仅控制 HTTP 到 HTTPS 的重定向，与申请证书无关。HTTP-01 要求域名解析到网关，公网 TCP 80 可达。`on_demand.enabled` 用于未预先配置域名的 SaaS 授权流程；普通域名站点无需开启它。

```yaml
auto_cert:
  enabled: true
  email: "litegate@example.com" # 默认占位联系方式；CA 要求真实邮箱时请修改
  domains: []                    # 旧字段，保留兼容
  certs_dir: "./certs"
  default_challenge: "http"      # 默认挑战模式: "http" (80 端口) 或 "tls-alpn" (443 端口)
  storage_secret: ""             # 可选：ACME 账号私钥对称加密密钥 (长度需 >= 32 字节)

  # 多 CA 配置
  ca_provider: "letsencrypt"     # letsencrypt, zerossl, google, custom
  acme_url: ""                   # 自定义 ACME 目录服务 URL (在 custom 模式下必填)
  acme_ca_cert: ""               # 私有 ACME HTTPS 根证书路径或内联 PEM
  acme_headers: {}                # 私有 ACME 请求附加头
  eab_kid: ""                    # 外部账户绑定 Key ID (针对 ZeroSSL 或 GTS)
  eab_hmac: ""                   # 外部账户绑定 HMAC Key (针对 ZeroSSL 或 GTS)

  provider: ""                   # 旧单 Provider 模式
  provider_config: {}

  dns_providers:
    - name: "aliyun-main"
      type: "aliyun"
      enabled: true
      domains: ["*.example.com", "example.com"]
      ddns:
        enabled: true
        ipv4: ""
        ipv6: ""
        sync_a: true
        sync_aaaa: true
        domains: ["*.example.com"]
      config:
        access_key_id: "..."
        access_key_secret: "..."

  renew_days: 10
  check_interval: 24
  use_staging: false
  propagation_dns: ["223.5.5.5", "114.114.114.114"]
  bootstrap_dns: ""

  dns_update:
    enabled: false
    auto_service_host_sync: false
    ip: ""
    key_prefix: "litedns/v1/records/"
    node_id: ""
    record_ttl: 30
    heartbeat_interval: 30s

  on_demand:
    enabled: false
    ask: "http://your-api/check-domain"
    kv_prefix: ""
    saas_template_site: ""

  webhook_url: ""
  webhook_token: ""
```

说明：

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `enabled` | bool | 是否启用自动证书；默认 `true`，可显式关闭 |
| `ca_provider` | string | 证书颁发机构提供商，默认值为 `letsencrypt` |
| `acme_url` | string | 自定义 ACME 目录接口 URL，仅当 `ca_provider=custom` 时必填 |
| `eab_kid` | string | 外部账户绑定的 Key ID (ZeroSSL/GTS 强制需要) |
| `eab_hmac` | string | 外部账户绑定的 HMAC Key (ZeroSSL/GTS 强制需要) |
| `storage_secret` | string | 可选，对持久层存储中的 ACME 账号私钥进行 AES-256-GCM 加密的对称密钥，长度需 >= 32 字节 |
| `dns_providers` | array | 多 DNS Provider 配置 |
| `ddns.ipv4` / `ddns.ipv6` | string | 手动指定 IP |
| `dns_update` | object | 将本网关内网 IP 按域名发布到 LiteMesh KV，供 LiteDNS 做内网解析（需启用 litemesh） |
| `on_demand.ask` | string | 按需签发授权检查 URL |
| `on_demand.kv_prefix` | string | 按需域名授权 KV 前缀 |
| `on_demand.saas_template_site` | string | SaaS 域名绑定模板站点 |

---

### 3.1 ECH（Encrypted ClientHello）

在主配置中开启浏览器到网关的 ECH，复用已启用的 DNS 提供商：

```yaml
ech:
  enabled: true
  groups:
    - public_name: ech.example.com
      dns_provider: aliyun-main
    - public_name: ech.example.net
      dns_provider: cloudflare-main
  storage: file
  # KV 集群可改为：
  # storage: kv
  # kv:
  #   provider: litemesh  # 或 consul，复用对应连接和 namespace
  #   key_prefix: litegate/ech/mycluster/
  # key_prefix: litegate/ech/mycluster/
```

默认关闭。需要 `auto_cert.enabled: true`、TCP 443 的 `websecure`、允许 TLS 1.3 的站点，以及内置阿里云或 Cloudflare 提供商。域名必须是具体 ASCII 名称；网站需要直接 A/AAAA，不能使用 CNAME；Cloudflare 必须 DNS only。

自动保障公共名称的证书申请、持久化 ECH 密钥并发布 HTTPS DNS 记录（TTL 600 秒）。每 7 天轮换；每个域名独立发布与重试，旧密钥不再被潜在 DNS 记录引用后保留 14 天，失败每分钟重试；不会覆盖非本实例管理的 HTTPS 记录。配置修改需要重启。各组密钥位于 `auto_cert.certs_dir/ech/<public_name>/state.json`（回退到 `tls.certs_dir`；匹配的旧单组状态目录继续复用），需要持久化备份；兼容的 auto 模式仅在启用 Consul/LiteMesh config_watch 时将加密状态共享到 KV；推荐显式 storage: kv，并填写 kv.provider 和 kv.key_prefix，由发布租约保证单个 DNS 写入者；各节点必须使用相同 storage_secret、public_name、提供商、站点配置及 key_prefix。显式 storage: file 使用单节点本地模式。关闭前先撤回 HTTPS 记录并等待 DNS 缓存过期。完整配置与测试步骤见 [ECH](../06-certificates/ech.md)。

## 4. Consul

```yaml
consul:
  enabled: false
  address: "127.0.0.1:8500"
  datacenter: "dc1"
  token: ""
  roles:
    config_watch: false
    cert_storage: false
    service_register: false
  keys:
    config_prefix: "litegate/config/sites/"
    cert_prefix: "litegate/certs/"
    stream_prefix: "litegate/streams/"
  service:
    id: ""
    name: "litegate"
    address: ""   # 注册地址；留空时自动探测本机出口 IP
    tags: ["gateway", "edge"]
    meta:
      version: "1.0"
```

---

## 5. Litemesh

```yaml
litemesh:
  enabled: true
  address: "127.0.0.1:8787"
  token: ""
  namespace: ""
  mtls: true
  spiffe_id: ""
  mtls_port: 8443
  roles:
    config_watch: false
    cert_storage: false
    service_register: true
  keys:
    config_prefix: "litegate/config/sites/"
    stream_prefix: "litegate/config/streams/"
    cert_prefix: "litegate/certs/"
  service:
    id: ""
    name: "litegate"
    address: ""   # 注册地址；留空时自动探测本机出口 IP
    tags: ["gateway", "edge"]
    meta:
      version: "1.0"
```

---

## 6. Service Discovery

```yaml
service_discovery:
  catalogs:
    - enabled: false
      provider: "consul"          # consul / discovery
      name: ""                    # 插件发现源实例名（同类型内唯一）
      config: {}                  # 插件发现源专用键值配置
      url: "127.0.0.1:8500"
      service_name: ""
      resolve_via: ""             # consul / litemesh
      default_domain: ""
      auth_mode: "disabled"       # disabled / auto
      token: ""
      namespace: ""
      jwt_auth_url: ""
      md5_auth_url: ""

    - enabled: false
      provider: "docker"
      socket_path: "/var/run/docker.sock"
      network_mode: "internal"     # internal (容器网 IP) 或 external (主端口映射 IP)
      swarm_mode: false            # 是否开启 Swarm 模式 (默认 false 开启自适应检测)

  tag_entrypoints:
    allowed_ports: []              # 允许服务标签新开的监听端口(HTTP 入口与 TCP/UDP Stream)，如 [8080, 15432]
```

服务标签(`litegate.entrypoints.<name>.address`、`litegate.tcp.port`、`litegate.udp.port`)只能在 `tag_entrypoints.allowed_ports` 列出的端口上新开监听，且不能与本文件中的入口同名或同端口；为空时标签不能新开端口，只能引用已有入口(默认 `web`、`websecure`)。详见[服务标签使用指南](tag-dsl.md)。

> [!NOTE]
> `catalogs` 是数组。当前代码已经不是旧的 `catalog` 单对象模式。
> 外部 Discovery Provider 使用其注册名作为 `provider`，专用配置放在 `config`，并可用 `name` 区分同类型多实例。

---

## 7. Cache 与 Redis

```yaml
cache:
  local_ttl: "60s"
  proxy_cache_max_entries: 10000  # 反代内容缓存最大条目数，超出按 LRU 淘汰防 OOM
  redis:
    enabled: false
    mode: "standalone"              # standalone 或 cluster
    address: "localhost:6379"
    addr: ""                      # address 的别名
    addrs: []                     # Redis Cluster 节点，如 ["redis-1:6379", "redis-2:6379"]
    username: ""
    password: ""
    db: 1
    tls: false
    pool_size: 20
    min_idle_conns: 5
    dial_timeout: "3s"
    read_timeout: "2s"
    write_timeout: "2s"
    max_retries: 2

redis:
  enabled: false
  mode: "standalone"
  address: "localhost:6379"
  addr: ""
  addrs: []
  username: ""
  password: ""
  db: 0
  tls: false
  pool_size: 20
  min_idle_conns: 5
  dial_timeout: "3s"
  read_timeout: "2s"
  write_timeout: "2s"
  max_retries: 2
```

---

## 9. Dashboard / Metrics / Pprof

```yaml
dashboard:
  enabled: true
  port: 9999
  username: "admin"
  password: "$2a$..."
  token: ""                      # 管理 API Token (X-API-Key 头校验)
  cookie_secret: ""              # Cookie 加密密钥 (AES-256 格式密钥)
  allowed_origins: []            # 允许跨域及 WebSocket 访问的来源列表 (留空表示仅限 Same Origin)
  require_secure_cookie: false   # 是否强制只能通过 HTTPS 传输控制台会话 Cookie

metrics:
  enabled: false
  port: 9090

pprof:
  enabled: false
  port: 6060
```

### Go 运行时 (runtime)

调整 Go 垃圾回收（GC）。不配置时保持 Go 默认值，行为与以前完全相同。

```yaml
runtime:
  gc_percent: 200        # 等价于 GOGC，范围 25~1000；不写即 Go 默认的 100
  memory_limit: 1GiB     # 等价于 GOMEMLIMIT，单位 B/KiB/MiB/GiB/TiB，最小 64MiB
```

* **`gc_percent`**：存活堆增长到多少百分比时触发下一轮 GC。LiteGate 常驻内存小，默认值下高并发时每秒可能 GC 几十轮；调到 `200` 可明显减少 GC 次数（16 vCPU 上 `respond` 站点实测吞吐约 +13%），代价是内存占用随之增加。
* **`memory_limit`**：内存软上限，接近时 GC 会提前、更频繁地运行。提高 `gc_percent` 时建议同时设置，避免内存无界增长；取值应低于机器或容器内存，并为其他进程留出余量。只提高 `gc_percent` 而不设上限时，启动日志会给出警告。
* 已设置 `GOGC` / `GOMEMLIMIT` 环境变量时，环境变量优先，对应配置项被忽略并记录警告。
* 修改 `runtime` 需要重启进程，热重载会拒绝这一变更。

---

## 10. 日志

```yaml
log:
  level: "info"                  # debug / info / warn / error
  format: "console"              # console / json

  webhook:
    enabled: false
    url: "https://example.com/webhook"
    levels: ["error", "fatal", "panic"]
    headers:
      Content-Type: "application/json"

  access_log:
    enabled: true
    stdout: true
    level: info
    file_enabled: false
    file: "" # defaults to ./logs/access.log when file_enabled is true
    max_size: 100         # 可选。单个日志文件最大大小 (MB)
    max_age: 7            # 可选。旧日志文件最大保留天数
    max_backups: 30       # 可选。最大保留的旧日志文件个数
    compress: true        # 可选。是否压缩旧日志文件 (gzip)
    routing_detail: false
    webhook:
      enabled: false
      url: "http://mq-gateway:8080/access-log"
      batch_size: 100
      interval: "1s"
      headers:
        Authorization: "Bearer token"
```

---

## 11. 全局 IP 限制

```yaml
ip_restriction:
  allow_ips: []
  deny_ips: []

stream_ip_restriction:
  allow_ips: []
  deny_ips: []
```

---

## 12. MCP

```yaml
mcp:
  enabled: false
  port: 8080
  token: ""                      # SSE Bearer Token
  public_url: ""                 # 反向代理后的公开 MCP URL
```

---

## 13. Auth Providers

```yaml
auth_providers:
  google:
    enabled: true
    type: "oidc"
    issuer: "https://accounts.google.com"
    client_id: "..."
    client_secret: "..."
    scopes: ["openid", "email", "profile"]
    callback_path: "/_auth/callback/google"
    notify_url: ""
    clock_skew: "5m"
    allowed_signing_algs: ["RS256"]
    introspection_url: ""
    introspection_interval: "5m"

  github:
    enabled: true
    type: "oauth2"
    client_id: "..."
    client_secret: "..."
    scopes: ["read:user", "user:email"]
    auth_url: "https://github.com/login/oauth/authorize"
    token_url: "https://github.com/login/oauth/access_token"
    callback_path: "/_auth/callback/github"
```

字段说明：

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `type` | string | 认证协议类型，可选 `oidc` 或 `oauth2` |
| `issuer` | string | OIDC Discovery Issuer 地址（仅 OIDC 必填，网关自动拉取 `.well-known/openid-configuration`） |
| `client_id` | string | OAuth2 / OIDC Client ID |
| `client_secret` | string | OAuth2 / OIDC Client Secret |
| `scopes` | string[] | 申请授权的作用域列表（默认 `["openid", "email", "profile"]`） |
| `callback_path` | string | 授权回调路径（默认 `/_auth/callback/<provider>`） |
| `notify_url` | string | 可选。Token 事件通知 Webhook 回调地址 |
| `auth_url` | string | 非 OIDC 标准 OAuth2 服务的授权发起地址 |
| `token_url` | string | 非 OIDC 标准 OAuth2 服务的 Token 交换接口地址 |
| `clock_skew` | string | JWT 校验时钟容忍偏差，例如 `5m` |
| `allowed_signing_algs` | string[] | 允许的 JWT 签名算法列表，例如 `["RS256", "ES256"]` |
| `introspection_url` | string | RFC 7662 Token 内省接口地址 |
| `introspection_interval` | string | Token 内省刷新周期，例如 `5m` |
| `auth_params` | map | 追加或覆盖授权请求参数（如 `prompt: login`），值为空表示去掉默认值。Google 默认 `access_type: offline`、`prompt: consent`，其他 IdP 默认不带 |

---

## 14. OIDC Security

```yaml
oidc_security:
  token_allowed_ips: []
  me_allowed_ips: []
  token_one_shot: false
  cookie_secret: ""
  cookie_same_site: "lax"        # lax / strict / none
  max_concurrent_sessions: 10
  token_endpoint_enabled: false  # 开启 /_litegate/oauth/token
  refresh_allowed_ips: []        # /_litegate/oauth/refresh 调用方，默认仅本机
  allowed_redirect_hosts: []     # 允许 redirect_back 跳转的外部主机
  login_failure_limit: 20        # 同一 IP 15 分钟内登录回调失败上限，负数关闭
```

---

## 15. Real IP

```yaml
real_ip:
  # 受信任的反向代理/SLB IP列表，用于网关信任并解析上一跳传递的 X-Forwarded-For 真实客户端 IP
  trusted_proxies:
    - "127.0.0.1/32"
    - "10.0.0.5/32"
  # 允许通过 X-Selector-Sid 进行东西向服务间物理选路的可信内网微服务客户端 IP/网段列表
  selector_trusted_clients:
    - "127.0.0.1/32"
    - "10.0.0.0/8"
```

说明：

* **`trusted_proxies`**：代理信任网段，规定网关信任哪些上一跳代理。通常只配置几台前置负载均衡/SLB的特定 IP。默认为空：不信任任何上一跳，忽略 `X-Forwarded-For`，客户端 IP 即直连地址。同机前置 nginx 等代理时需显式加入 `127.0.0.1`。
* **`selector_trusted_clients`**：东西向可信物理选路客户端授权网段。仅在此网段内的真实客户端发起的请求，网关才允许提取并提升 `X-Selector-Sid` 用于实例物理隔离选路；外网非受信客户端携带的 `X-Selector-Sid` 将在网关入口处被物理强力抹除，防范外部伪造。若未配置此项，系统将优雅兜底 Fallback 指向 `trusted_proxies`。


---

## 16. 其他

```yaml
sites_dir: "./sites"
streams_dir: "./streams"
# disable_trace_id: true   # 不写时自动：performance 模式下未开启 tracing / access_log 则不生成 TraceID；显式写 true/false 以写的为准

# Cookie 会话保持加密密钥（32 字节 hex）。多节点部署需所有节点配相同值，
# 否则跨节点的粘连 Cookie 无法解密。配合 action 的 lb_policy: cookie 使用
sticky_key: ""

# OpenTelemetry 分布式链路追踪 (OTLP/HTTP)
tracing:
  enabled: false
  endpoint: "http://127.0.0.1:4318" # OTLP/HTTP 接收端地址（自动拼接 /v1/traces）
  service_name: "litegate"
  sample_ratio: 1.0                  # 采样率 0.0 - 1.0 (1.0 = 100% 全量采样)
  trust_incoming_sampled: true       # 是否信任客户端发来的 traceparent sampled 标志
  batch_size: 128
  interval: "2s"

# 被动健康检查与异常节点剔除 (Outlier Detection)
passive_health:
  consecutive_failures: 5            # 连续失败次数阈值（超过后自动剔除该节点）
  base_ejection_time: "3s"           # 首次剔除隔离时长
  max_ejection_time: "30s"           # 指数退避的最大隔离封禁时长
  ejection_reset_time: "30s"         # 节点稳定运行时衰减重置回基础隔离时长的等待期

# 外部插件动态加载目录
# plugin_config:
#   path: "./plugins"
#   watch: true
```

---

## 17. 最小示例

```yaml
http:
  port: 80
  https_port: 443

sites_dir: "./sites"
streams_dir: "./streams"

mcp:
  enabled: true
  port: 8080

dashboard:
  enabled: true
  port: 9999
  username: "admin"
  password: "$2a$..."
```

---

## 18. 扫描保护 (Scan Protection)

`scan_protection` 提供基于威胁评分机制的动态扫描阻断，能够在黑客探测敏感文件路径（如 `.git`、`.env`）或不存在的 API 时，自动封禁源 IP。

```yaml
scan_protection:
  enabled: false                      # 扫描保护总开关，默认关闭。支持看板/API 运行时动态热切
  block_duration: "1h"                # 自动封禁持续时间，支持 h/m/s
  max_404_attempts: 6                 # 观察期内允许的最大 404 越权探测次数，超过加分并进入阻断
  observation_period: "1m"            # 滑动观察窗口时间范围
  block_direct_ip: false              # 首次上线建议保持 false，无误伤再改 true。开启后直接通过 IP 访问网关（无 Host）的恶意行为将被立即阻断
  forbidden_paths:
    - ".env"
    - ".php"
    - ".jsp"
    - ".asp"
    - ".aspx"
    - "/wp-admin"
    - "/wp-content"
    - "/phpmyadmin"

  global_rules:
    - name: "block_unsupported_ext"
      match:
        path_exact:
          - ".php"
          - ".php3"
          - ".php5"
          - ".php7"
          - ".phtml"
          - ".pht"
          - ".asp"
          - ".aspx"
          - ".ashx"
          - ".asmx"
          - ".jsp"
          - ".jspx"
          - ".cgi"
          - ".cfm"
      action: "deny"
      score: 30
      reason: "unsupported_ext_probe"

    - name: "secrets_and_vcs"
      match:
        path_exact:    ["/.git", "/.svn", "/.env", "/.htpasswd"]
        path_contains: ["/.git/", "/.env.", "/id_rsa", "/.ssh/", "/.aws/credentials", "/.docker/config.json"]
      action: "deny"
      score: 30
      reason: "secret_or_vcs_probe"

    - name: "admin_tool_probe"
      match:
        path_prefix:   ["/phpmyadmin", "/pma", "/adminer", "/manager/html", "/cgi-bin/"]
        path_contains: ["/vendor/phpunit/"]
      action: "deny"
      score: 30
      reason: "admin_tool_probe"
```

字段说明：

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `enabled` | bool | 是否启用扫描保护模块。 |
| `block_duration` | string | 封禁持续时间，例如 `"1h"` 或 `"30m"`。 |
| `max_404_attempts` | int | 允许的探测最大 404 响应数限制。 |
| `observation_period` | string | 探测窗口滑动时间。 |
| `forbidden_paths` | string[] | 敏感路径后缀或前缀后缀定义。 |
| `block_direct_ip` | bool | 是否禁止直接 IP 访问。 |
| `global_rules` | array | 扫描阻断规则，包含匹配规则与执行动作。支持 `deny`, `tarpit`, `rate_limit`, `score`, `observe` 动作类型。 |

---

## 19. LiteGate Connect

Connect 让 Home 节点主动连接 Cloud，并通过 Cloud 的公网 80/443 发布 Home Site：

```yaml
connect:
  server:                         # Cloud 节点
    enabled: true
    hostname: connect.example.com
    path: /_litegate/connect/v1
    state_file: data/connect-registry.json
    health:
      enabled: false              # 可选：对发布域名执行端到端健康检查
      node_name: cloud-node-01    # 节点唯一名称（可选，默认使用主机名，容器环境建议显式指定）
      advertise_addr: 10.0.0.5    # 发布到 LiteDNS / LiteMesh 的 Cloud 地址
      advertise_port: 443
      probe_path: /healthz        # 通过 Connect 反向隧道探测
      probe_interval: 5s
      probe_timeout: 2s
      ttl: 15s                    # 仅 service_registration 开启时使用
      fail_threshold: 2
      max_concurrent_probes: 32
      dns_registration:           # 将 passing 域名写入 LiteDNS KV；默认关闭
        enabled: false
        key_prefix: litedns/v1/records/
        record_ttl: 10
        kv_ttl: 15s
      service_registration:       # 将 passing 域名注册成 LiteMesh 服务；默认关闭
        enabled: false
    peers:
      private:
        token_file: /etc/litegate/secrets/private-connect.token
        allowed_domains: ["*.private.example.com"]
        max_sites: 200
        max_connections: 4096
        sessions: 2
        max_registrations_per_minute: 30

  client:                         # Private 节点
    enabled: true
    name: private
    remote: https://connect.example.com/_litegate/connect/v1
    token_file: /etc/litegate/secrets/private-connect.token
    publish_sites: true
    publish_streams: false
    sessions: 2
    max_connections: 4096
    registration_debounce: 500ms
    exclude_domains: [connect.example.com]
```

Cloud 与 Private 通常分别使用各自配置，只启用对应一侧。完整的字段、安全边界、mTLS、多 Cloud、
Token 轮换和上线步骤见 `docs/zh-cn/user/09-advanced/connect.md`。

只开启健康检查不会发布任何数据；必须显式开启某个注册开关。`dns_registration` 会按“域名 + Cloud
节点”写入带 TTL 的 LiteDNS KV，`service_registration` 只提供给仍使用 LiteMesh 服务发现 SDK 的调用方。
两个开关彼此独立，默认均为 `false`。


## 自定义访问日志模板

```yaml
log:
  format: json
  access_log:
    enabled: true
    stdout: true
    file_enabled: true
    file: ./logs/access.log
    template: '{client_ip} - [{timestamp}] "{method} {uri}" {status} {size_bytes} "{referer}" "{user_agent}" {cost_ms}'
```

`template` 控制访问日志的终端和文件输出；留空沿用现有格式。运行日志继续由 `log.format` 控制，Webhook 和看板保留结构化数据。文件轮转、异步写入和日志级别过滤照常生效。

支持字段：`timestamp`、`client_ip`、`method`、`path`、`uri`（含查询参数）、`host`、`status`、`size_bytes`、`cost_ms`、`upstream`、`route`、`site`、`trace_id`、`referer`、`user_agent`。时间为现有结构化日志时间戳，耗时单位为毫秒，保留小数精度；空的 Referer 和 User-Agent 输出 `-`。缺失字段输出 `-`。字段值中的换行、控制字符、引号和反斜杠会转义，防止请求伪造额外日志行。模板必须为单行，未知字段或不完整占位符会在配置验证时报告错误。这是 LiteGate 的 `{字段}` 模板，不直接解析 Nginx `$变量` 格式。

修改 `log.access_log.template` 后需要重启 LiteGate；当前全局日志配置只有 `log.level` 支持热更新。通过 MCP 保存配置会进行校验并请求重载，但保存成功不表示这些启动时配置已生效。`litegate -init` 生成的示例配置也包含空模板和自定义模板示例。

### 跨站点共享的匹配条件和配置片段

`matchers` 和 `snippets` 不属于主配置。跨站点共享的定义放在 `sites/_shared.yaml`（KV 模式为站点前缀下的 `_shared.yaml` 键），详见站点配置参考中的“跨站点共享的匹配条件和配置片段”。在 `config.yaml` 顶层写这两项会在加载时报错。

## 上游 DNS 解析器

Consul/LiteMesh `config_watch` 模式下修改 `resolvers` 需要重启；文件模式会重新验证站点并拒绝删除仍被引用的解析器。ECH 发布成功后每 30 分钟全面检查 DNS，失败每分钟重试。关闭前可停止实例并执行 `litegate ech withdraw -config config.yaml` 撤回本实例管理的 HTTPS 记录，等待缓存过期后停用。ECH 公共名称的证书域名仅在运行时派生，不写回 DNS 提供商配置。

```yaml
resolvers:
  corp:
    servers: [192.168.1.53:53, 192.168.1.54:53]
    timeout: 2s
```

站点代理或命名 Service 使用 `resolver: corp` 引用。服务器必须是 IP:port，IPv6 使用 `[地址]:53`；每个服务器查询默认超时 2 秒。UDP 响应截断时使用 TCP；查询失败可尝试同视图备用服务器，NXDOMAIN / NODATA 不切换。不回退系统 DNS / hosts；选定解析器的上游不使用环境 HTTP 代理。未配置时维持原有行为。新连接重新解析，长连接可继续复用。详细配置见 [上游自定义 DNS](upstream-dns.md)。

站点在 `site:` 同级设置 `ech: ech.example.com` 或 `ech: ech.example.net`，分别选择公共域名绑定的 DNS 提供商，无需 `domains`。只有一个组时可使用 `ech: true`，多个组时必须指定公共域名；`ech: false` 关闭。每组密钥、轮换、DNS 发布和 KV 租约独立，默认 KV 前缀为 `litegate/ech/<public_name>/`。根级 key_prefix 是组前缀的父目录，组级 key_prefix 是精确前缀，不能重复。旧单组配置仍兼容，使用原路径与 `litegate/ech/default/` 前缀。站点选组可热加载；主配置的组列表修改需要重启。

第三方 ECH DNS 插件实现 `plugin.HTTPSDNSProvider` 并注册 `https_records` 能力。密钥、轮换、KV 同步、租约及重试由 LiteGate 内部管理；插件仅提交和撤回公开 HTTPS 记录。仅支持 HTTPS 的插件需要另行安排证书覆盖，其域名选择器在运行时不会参与证书 DNS-01 路由。
