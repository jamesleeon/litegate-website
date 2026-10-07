# 在同一个 443 端口承载 HTTPS 与 L4 TCP

LiteGate 可以根据 TLS ClientHello 中的 SNI，在同一个公网 TCP/443 入口上同时承载普通 HTTPS 站点与非 HTTP 的四层 TCP 服务。命中的连接可以原样透传 TLS，也可以由 LiteGate 终止 TLS，再转发到 TCP 或 Unix Domain Socket 上游。

这个能力适合以下场景：

- 公网、防火墙或负载均衡器只允许开放 443；
- 多个 HTTPS 站点已经使用 `websecure`，同时还要接入自定义 TLS、数据库前置隧道、RPC 或代理协议；
- 本机后端希望使用 Unix Socket，避免额外暴露环回 TCP 端口；
- HTTPS 与 L4 Stream 希望复用 LiteGate 的自动证书、泛域名证书、ACL、服务发现和指标体系。

> 这里的“端口共享”指一个 TCP Listener 根据 SNI 选择处理管道，不是 `SO_REUSEPORT`，也不是让两个进程同时绑定 `0.0.0.0:443`。

## 1. 工作原理

```text
客户端 TCP/443
      │
      ▼
TLS ClientHello（读取 SNI，不消耗原始字节）
      │
      ├─ db.example.com ──► L4 Stream
      │                         ├─ TLS 原样透传 ─► TCP / Unix Socket
      │                         └─ LiteGate 终止 TLS ─► 明文 TCP / Unix Socket
      │
      └─ 其他域名 ─────────► 正常 HTTPS / HTTP/2 Sites

UDP/443 ───────────────────► HTTP/3（独立的 UDP Listener，不参与 TCP SNI 分流）
```

`websecure` 启动时始终带有一个空的 SNI Mux。没有 L4 路由时走快速路径，连接直接进入 HTTPS；加入第一条路由不需要重建公网 Listener。命中 L4 路由后，LiteGate 会把检查 ClientHello 时读取的字节重新放回连接，因此后续 Stream 或上游仍能收到完整数据。

## 2. 快速开始：LiteGate 终止 TLS，转发到 Unix Socket

全局入口继续正常监听 443：

```yaml
# config.yaml
entrypoints:
  websecure:
    address: ":443"
    tls: true
    default: http
    on_non_tls: reject
    on_no_sni: reject
```

创建一个不自行监听端口、而是挂载到 `websecure` 的 Stream：

```yaml
# streams/database.yaml
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
  min_version: "1.2"
```

使用 `auto_cert: true` 的前提是全局 `auto_cert.enabled` 已开启并配置好 ACME 验证方式，或者共享证书池中已经存在可用证书。Stream 级开关表达“确保此域名有证书”，不会单独创建 ACME 账号或 DNS Provider。

这一份配置同时表达了：

- `db.example.com` 的 TCP/443 连接交给 `database` Stream；
- 由 LiteGate 完成 TLS 握手；
- 解密后的字节流发送到 `/run/litegate/database.sock`；
- 其他域名继续进入普通 HTTPS Sites；
- `hostnames` 自动作为 `auto_cert` 的证书域名，无需再写一次 `tls.domains`。

`listen: false` 是端口共享的关键。该 Stream 不再绑定自己的 `port`，而由 `websecure` 接收连接。

LiteGate 不允许同一个 Stream 同时自行监听端口并挂载 Entrypoint。若迁移期间需要
同时保留原端口和共享 443，请创建两个不同名称的 Stream，让它们指向相同的
`upstream` 或 `service_name`。不要在同一份配置中组合 `listen: true`、`port`、
`entrypoints` 和 `hostnames`；分开定义可以避免 TLS 策略、会话上限和指标入口产生歧义。

## 3. 两种 TLS 模式

### 3.1 TLS 透传：证书留在后端

如果后端自己完成 TLS 握手，Stream 不要开启 TLS 终止：

```yaml
name: private-tls-service
listen: false
entrypoints: [websecure]
hostnames: [tcp.example.com]
protocol: tcp
upstream: unix:///run/private-service/tls.sock
enabled: true
```

SNI Mux 只读取 ClientHello 进行分类，随后把完整 ClientHello 和后续密文原样转发。后端必须：

- 自己持有 `tcp.example.com` 对应证书；
- 从连接第一个字节开始执行 TLS 握手；
- 不能期待 LiteGate 已经解密数据。

简单的单上游透传不需要配置 `tls`。只有当一个独立 Stream 还要使用自身的 `tls_routes` 再做一层 SNI 选路时，才需要：

```text
tls:
  enabled: true
  passthrough: true
```

### 3.2 TLS 终止：证书由 LiteGate 管理

配置 `tls.enabled: true` 且不启用 `passthrough` 时，LiteGate 先完成 TLS 握手，上游收到明文字节流：

```text
tls:
  enabled: true
  auto_cert: true
```

这种模式适合后端只理解明文 TCP，或者希望证书统一由 LiteGate 管理的场景。它不是 HTTP 反向代理：LiteGate 不解析请求方法、URL 或 Header，只是在 TLS 终止后双向复制字节流。

## 4. HTTPS 与 L4 Stream 共用证书

HTTPS Sites 和终止 TLS 的 L4 Stream 使用同一个证书池。`auto_cert: true` 不等于无条件申请新证书，LiteGate 会先检查共享池：

1. 若存在该 Stream 自己的精确域名证书，先按正常流程检查续期窗口和 CA 签发者；
2. 否则查找由其他域名共享、且能覆盖该域名的有效泛域名或多 SAN 证书；
3. 校验证书 SAN、生效时间，并确保剩余有效期超出续期窗口；
4. 只有没有合格的共享覆盖证书时才申请新的精确域名证书。

例如全局已经加载有效的 `*.example.com` 时：

```yaml
hostnames: [db.example.com]
tls:
  enabled: true
  auto_cert: true
```

LiteGate 会直接复用 `*.example.com`，不会额外申请 `db.example.com`。从共享 KV 恢复的证书也会在 Stream 证书扫描前同步刷新到证书池。

标准泛域名证书只覆盖一层标签：

- `*.example.com` 可以覆盖 `db.example.com`；
- 不能覆盖 `primary.db.example.com`；
- 通常也不覆盖裸域名 `example.com`。

需要申请泛域名证书时仍应在全局 Auto-Cert DNS Provider 中显式声明，并使用 DNS-01。Stream 的 `hostnames` 负责连接选路，不会根据 `db.example.com` 自动推导并申请 `*.example.com`。

## 5. 为什么推荐在 Stream 中声明域名

推荐配置：

```yaml
name: database
listen: false
entrypoints: [websecure]
hostnames: [db.example.com]
protocol: tcp
upstream: unix:///run/litegate/database.sock
```

LiteGate 会在运行时生成等价的 `handle.stream` SNI 路由。这样域名、TLS 和 L4 治理都归属于同一个 Stream，避免在 `config.yaml` 和 `streams/*.yaml` 中重复写 `db.example.com`。

只有需要绕过 Stream 管道、直接进行原始 TCP 透传时，才建议手工配置 Entrypoint 路由：

```yaml
entrypoints:
  websecure:
    address: ":443"
    tls: true
    routes:
      - name: direct-tls-service
        match:
          sni: tcp.example.com
        handle:
          proxy: unix:///run/private-service/tls.sock
```

`handle.proxy` 始终是 TLS 透传，不会由 LiteGate 终止 TLS，也不会应用命名 Stream 的 ACL、负载均衡和会话指标。显式 Entrypoint 的精确域名或泛域名规则与自动生成规则使用同一匹配模式时，显式规则优先；`sni_regex` 始终排在所有精确域名和泛域名之后，因此显式正则不会覆盖自动生成的精确或泛域名规则。

显式 `handle.stream` 引用不存在或已禁用的 Stream、或者 `handle.proxy` 目标无法解析时，LiteGate 会记录配置错误，并拒绝命中该规则的连接，不会让它意外回落到 HTTPS 站点。

## 6. Unix Socket 的所有权与生命周期

对于：

```yaml
upstream: unix:///run/litegate/database.sock
```

LiteGate 是客户端（Dialer），不是 Socket 监听者。它不会为上游创建目录、创建 `.sock` 文件、修改权限或清理遗留文件。

每个新连接都会重新按路径 Dial：

- 后端可以晚于 LiteGate 启动，但 Socket 就绪前到来的连接会失败；
- 后端重新创建同一路径的 Socket 后，不需要重载 LiteGate；
- 修改 `upstream` 路径后，新连接使用新路径，已有连接继续使用原连接；
- 后端执行 `unlink` 到重新 `bind` 之间，新连接可能收到 `no such file or directory`；
- 文件存在但没有进程监听时，通常收到 `connection refused`；
- Socket 重新创建后权限改变，可能收到 `permission denied`；
- 当前连接 Dial 失败后不会等待后端恢复，后续新连接会重新尝试。

这是 L4 字节流转发，Dial 失败时不会像 HTTP 反向代理一样返回 `502`；客户端通常只会看到连接关闭或重置。

Linux 推荐使用共同用户组和最小权限：

```bash
install -d -o database -g litegate -m 0750 /run/litegate
# 后端创建 socket 后：
chown database:litegate /run/litegate/database.sock
chmod 0660 /run/litegate/database.sock
```

LiteGate 用户需要对父目录具有执行/遍历权限，并对 Socket 文件具有连接所需的权限。容器部署时，两端必须挂载同一个 Unix Socket 卷；Unix Socket 不能跨主机，也不能跨互不共享文件系统的容器命名空间。

路径必须是静态绝对路径，最长 107 字节。不支持 HTTP Unix upstream 使用的 `{host}` 模板，也不支持 UDP Stream。

## 7. 客户端真实地址与 PROXY Protocol

Unix Socket 后端无法从操作系统的对端地址得到公网客户端 IP。如后端支持 PROXY protocol，可以在 Stream 上启用：

```yaml
proxy_protocol: true
proxy_protocol_version: 2
```

LiteGate 会先写入 PROXY protocol 头，再发送 TLS 密文或已解密的应用字节。后端必须明确开启对应版本的解析；否则它会把 PROXY 头当作应用数据，导致协议错误。

不要同时在自动生成的 Entrypoint 路由上配置 `handle.proxy_protocol`。连接交给命名 Stream 时，PROXY protocol 应由 Stream 统一发送。

## 8. 热更新行为

| 变更 | 是否需要重启 | 对已有连接的影响 |
| :--- | :--- | :--- |
| 从零新增第一条 attached Stream 路由 | 否 | 已接受连接继续原处理路径，新连接使用新路由 |
| 修改 `hostnames` | 否 | 新连接使用新路由表 |
| 修改 TCP 或 Unix Socket `upstream` | 否 | 已有会话保持原上游，新会话使用新地址 |
| 新增、删除 attached Stream | 否 | 不重绑公网 443 |
| 修改 `inspect.timeout`、`max_pending`、`per_ip_pending` | 否 | 新检查使用新预算 |
| 修改 `inspect.dispatch_queue` | 是 | 内部 channel 容量无法原地调整 |
| 原地修改 `websecure` Listener 地址或底层监听属性 | 通常是 | 需要重建监听管道 |

路由表更新是原子操作，但不会迁移已经建立的长连接。这是四层代理的预期行为。

一旦 `websecure` 上存在至少一条显式或自动生成的 SNI 路由，ClientHello 检查会对该入口的所有新连接生效，包括最终进入普通 HTTPS Site 的连接。LiteGate 从无路由切换到该模式时会输出一条 Info 日志，并列出当前检查预算。默认 `inspect.timeout` 为 `5s`、`max_pending` 为 `2048`、`per_ip_pending` 为 `16`。`per_ip_pending` 限制的是同一来源 IP 正在进行的 ClientHello 检查数，不是已建立连接数；但 CDN 回源、NAT 或企业统一出口可能在握手突发时共享同一来源 IP，应按实际峰值调高并监控拒绝指标。

如果 attached Stream 的 `hostnames` 与同一 Entrypoint 上的 HTTPS Site 域名重叠，L4 Stream 会在 TLS 终止前接管连接。LiteGate 会在启动和热更新时输出冲突日志，但不会自行猜测应保留哪一方；上线前应消除这类重叠。

## 9. 协议限制

### 客户端首包必须是 TLS ClientHello

按域名分流依赖 ClientHello SNI，因此目标协议必须从连接第一个字节开始使用 TLS，并且客户端必须发送 SNI。

以下协议不能直接按这种方式共享 443：

- 明文 SSH、Redis 或其他非 TLS 协议；
- 先进行应用协议协商、再升级 TLS 的协议；
- 原生 MySQL TLS：服务端先发送握手包，客户端之后才请求 TLS；
- PostgreSQL SSLRequest：客户端先发送 PostgreSQL 协议请求，服务端确认后才开始 TLS。

仅仅在 MySQL/PostgreSQL 客户端中勾选“启用 SSL”并不能把它变成 Raw TLS 隧道。可选方案：

- **PostgreSQL 17+**：客户端设置 `sslnegotiation=direct` 后首包即为带 ALPN `postgresql` 的 ClientHello，可以用 [`match.alpn`](../03-configuration/entrypoints.md#按-alpn-匹配) 直接共享 443，无需额外客户端；
- **其他数据库或旧版 PostgreSQL**：推荐 [Forward](forward-and-connect.md)，客户端本地监听数据库端口，经 443 TLS 隧道接入服务端 Stream，详见[云 RDS 安全代理到本地](../../rds-forward-guide.md)；
- 也可以使用 stunnel 等从首字节开始的 TLS 包装层，或改用独立端口。

### SNI、ECH 与无 SNI 客户端

- 直接按 IP 连接或未发送 SNI 的客户端不能按域名选择 Stream；
- `on_no_sni: reject` 会直接拒绝这类连接；
- ECH 隐藏内层 ClientHello 后，网关只能看到可见的外层名称，不能依赖隐藏域名分流；
- `hostnames` 支持精确域名和 `*.example.com`，不接受全局 `*`。

### HTTP/3

该能力共享的是 TCP/443。HTTP/3 使用 UDP/443，由独立 Listener 处理，不经过 TCP SNI Stream 路由，也不能转发到 Unix stream socket。

## 10. 与 Nginx Stream 的关系

LiteGate 的能力范围大致对应 Nginx 的 `stream`、`ssl_preread` 和 Unix Socket upstream：

| 能力 | Nginx | LiteGate |
| :--- | :--- | :--- |
| 不终止 TLS 读取 SNI | `ssl_preread` | `websecure` SNI Mux |
| HTTPS 与其他 TLS TCP 共用外部 443 | Stream 外层分流后转给不同监听端 | 未命中路由直接进入内置 HTTPS 管道 |
| TLS 透传 | 支持 | 支持 |
| Stream TLS 终止 | 支持 | 支持 |
| Unix Socket 上游 | 支持 | 支持 |
| 域名与 L4 配置归属 | 通常通过 `map`、`upstream`、`server` 组合 | Stream 自身声明 `entrypoints + hostnames` |
| HTTPS/L4 证书复用 | 依赖具体证书配置方式 | 统一证书池、Auto-Cert 与泛域名覆盖检查 |
| 首条路由在线加入 | 通常通过配置 reload | 原子热更新，不重绑 443 |

这属于能力对标，不代表配置语法兼容，也不代表两者的负载均衡、健康检查或重试语义完全相同。

- [Nginx `ssl_preread` 官方文档](https://nginx.org/en/docs/stream/ngx_stream_ssl_preread_module.html)
- [Nginx Stream Proxy 官方文档](https://nginx.org/en/docs/stream/ngx_stream_proxy_module.html)

## 11. 排错速查

| 现象 | 常见原因 | 检查方向 |
| :--- | :--- | :--- |
| TLS 握手后立即断开 | Unix Socket 不存在或无人监听 | Stream 日志、`litegate_stream_dial_failures_total`、Socket 路径 |
| 后端收到 `0x16 0x03...` | 当前是 TLS 透传，后端却期待明文 | 开启 Stream TLS 终止，或让后端处理 TLS |
| 后端收到 `PROXY TCP4...` 后报协议错 | 开启了 PROXY protocol，但后端未解析 | 后端启用相同版本或关闭该配置 |
| `permission denied` | Socket/父目录属组或权限错误 | `namei -l`、`stat`、进程用户与组 |
| `no such file or directory` | 后端未启动、重建窗口或容器未共享卷 | 后端 readiness、挂载路径 |
| 域名仍进入 HTTPS Site | SNI 未携带、hostname 不匹配或 Stream 未启用 | 客户端 SNI、Stream 状态、生成路由日志 |
| 为子域名申请了单独证书 | 现有泛域名证书无效、未加载或覆盖层级不符 | SAN、有效期、证书池与 wildcard 层级 |
| MySQL/PostgreSQL 客户端无法握手 | 使用的是协议内 TLS 升级，不是首包 Raw TLS | 增加 TLS 包装层或改用独立端口 |

## 12. 相关文档

- [443 端口 L4 SNI 分流与 L7 组合实战](sni-routing-recipes.md)
- [Entrypoints（监听入口）](../03-configuration/entrypoints.md)
- [Stream 配置参考](../03-configuration/stream-config.md)
- [Auto-Cert](../06-certificates/auto-cert.md)
- [On-Demand TLS](../06-certificates/on-demand-cert.md)
- [Metrics](../08-observability/metrics.md)
