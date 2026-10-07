<!-- GENERATED FILE — DO NOT EDIT.
     Source: internal/configdocs/docs/zh/tag-architecture.md (package internal/configdocs)
     Regenerate: go generate ./internal/configdocs/...
     Edit the source instead; a drift test fails if this copy is edited directly. -->

# LiteGate 服务标签架构

本文说明服务标签为什么这样设计、网关如何把标签变成路由，以及标签与站点 YAML 的分工。怎么写见《服务标签使用指南》，每个标签的说明见《服务标签参考》。

## 1. 为什么用标签

站点 YAML 由网关管理员维护；服务标签由服务自己在注册时携带。服务上线、扩容、下线时，路由随注册信息自动出现和消失，不需要改网关配置。标签适合"这个服务通过哪个域名、哪个路径对外"这类由服务自己决定的事；网关级的事(证书、监听端口、全局安全策略)仍由 config.yaml 与站点 YAML 决定。

## 2. 设计原则

1. **两种写法，互不混用。** 快捷模式(4 个键)覆盖最常见的"一个域名转发到本服务"；命名资源覆盖其余一切。
2. **能推导的就不用写。** 入口默认 `web` + `websecure`，Service 默认是注册服务本身，Host 不写匹配任意 Host。
3. **写错就拒绝，而不是静默忽略。** 未知属性、无效引用、冲突配置会让该实例整体被拒绝(fail closed)，并给出"did you mean"建议。这是为了避免 Traefik 式"标签拼错、行为诡异、查半天"的问题。
4. **只有一个判定来源。** 运行时、dashboard 的标签分类、MCP 的 `explain_tag` / `preview_service_tags` 调用同一个解析器；标签参考也从解析器的属性表生成。三者不会给出不同结论。

## 3. 资源模型

```text
EntryPoint                    listener address and protocol (config.yaml, or a restricted tag definition)
  ├── HTTP Router             matches Host / path / method / header / query, references the resources below
  │     ├── Middlewares       request and response processing (rate limit, CORS, strip prefix, ...)
  │     ├── IDS               identity and tenant decisions, returns an instance selector
  │     └── HTTP Service      the registering service: instance selection, load balancing, timeout, retry, circuit breaker, health checks
  │           └── ServersTransport   TLS / mTLS to the upstream
  └── L4 Stream               TCP / UDP proxy: port binding, optional TLS termination, direct stream forwarding
```

- **EntryPoint** 是监听地址与协议，来自 config.yaml，或受限的标签定义。
- **Router** 匹配 Host / 路径 / 方法 / 头 / 参数，并引用中间件、IDS 与 Service。
- **Middlewares** 处理请求与响应(限流、CORS、剥离前缀……)；**IDS** 做身份与租户决策并返回实例 selector。
- **Service** 是注册服务本身：选实例、负载均衡、超时、重试、熔断、健康检查；**ServersTransport** 是到上游的 TLS / mTLS。
- **Router 负责"哪些请求"，Service 负责"怎么转发"。** Host 属于 Router，超时与重试属于 Service。
- **Service 永远是注册服务本身。** 标签不能把流量转给别的服务；`discovery.name` 只能等于注册服务名。
- **IDS 只能缩小范围。** IDS 返回的 selector 只在该 Service 的实例中继续筛选，与 Service 硬 selector 冲突时请求被拒绝。
- **L4 Stream** 处理非 HTTP 的四层 TCP/UDP 流量：通过标签声明监听端口与可选 TLS 设置，直接转发至注册服务实例，不经过七层 HTTP 路由与中间件。

## 4. 标签如何变成路由

```text
instance tags / metadata
  → instance tags (litegate.instance.*, plain metadata) are set aside; they never define routes
  → shortcut: compiled to a Router named main
    named resources: parsed and validated by ParseTagResources
  → CompileTagResources: one route per Router × entrypoint (e.g. orders@web, orders@websecure)
  → L4 stream tags (litegate[.<group>].tcp/udp.*): compiled to dynamic StreamConfig
  → entrypoint policy: config.yaml entrypoints by name; new ports only within allowed_ports
  → merged into catalog sites by domain, and with a site YAML of the same domain
```

也就是：实例标签先被分出去，不参与路由定义；快捷模式编译成名为 `main` 的 Router，命名资源由解析器校验；每个 Router 在每个入口上生成一条路由(如 `orders@web`、`orders@websecure`)；四层 Stream 标签按协议与端口聚合成动态 StreamConfig 并注册实例；入口只能引用 config.yaml 中的入口，新开端口须在 `allowed_ports` 内；最后按域名合并到站点，并与同名的 YAML 站点合并。

同一服务的所有实例必须携带相同的路由与资源标签。实例之间不一致时，dashboard 会高亮漂移的键，网关只采用其中一份声明，直到实例标签收敛。

## 5. 路由标签与实例标签

| | 路由与资源标签 | 实例标签 |
| :--- | :--- | :--- |
| 键 | 快捷模式 4 键、`litegate.entrypoints.*`、`litegate.http.*`、`litegate[.<group>].tcp/udp.*` | `litegate.instance.*`、普通 metadata(如 `sid=c1`) |
| 描述 | 这个服务怎么对外(七层路由或四层流) | 这个实例是谁 |
| 各实例之间 | 必须一致 | 可以不同 |
| 被谁使用 | 编译成路由或流代理 | 请求时被 selector / IDS 匹配 |

Service 的 `discovery.selector.match.<key>` 与实例的 `<key>=<value>`(或 `litegate.instance.labels.<key>`)配对；`selector.meta.<key>` 与 `litegate.instance.meta.<key>` 配对。

## 6. 请求链路

```text
request → entrypoint (web / websecure / ...)
        → site by Host
        → route within the site: higher priority first, then the more specific path; a route only accepts requests from its own entrypoints
        → Middlewares → IDS
        → Service: hard selector gives the base set; the meta preference's matches if any, otherwise the base set
        → load balancer picks an instance → forward (timeout / retry / circuit breaker)
```

即：先按入口与 Host 找到站点；站点内 priority 高者优先，其次路径越具体越优先，且路由只接受从自己入口进来的请求；依次经过中间件与 IDS；Service 用硬 selector 得到基础集合，meta 偏好有命中就用命中集，否则用基础集合；最后负载均衡选出实例并转发。

## 7. 四层 (L4) Stream 代理

对于数据库（MySQL、PostgreSQL）、缓存（Redis）、IoT 等非 HTTP 协议，服务不需要定义七层 HTTP Router 与中间件，而是直接使用四层 Stream 标签。

### 7.1 标签语法与分组

```properties
# 单端口最小写法
litegate.tcp.port=3306

# 多端口与 TLS 终止
litegate.mysql.tcp.port=3306
litegate.mysql.tcp.tls.enabled=true
litegate.mysql.tcp.tls.domains=db.example.com
litegate.dns.udp.port=5353
```

- **协议与端口**：`litegate[.<group>].tcp.port` 与 `litegate[.<group>].udp.port` 在指定端口监听并将原始连接转发到注册服务实例。
- **多端口分组**：当同一个服务需要暴露多个四层端口（例如同时暴露业务端口与管理/探针端口）时，通过可选的 `<group>` 区分（如 `mysql`、`dns`）。
- **TLS 终止**：支持配置 `litegate[.<group>].tcp.tls.enabled=true`，可选 `auto_cert`、`domains`、`cert_file`、`key_file`、`min_version`。UDP 协议不支持 TLS 终止。

### 7.2 编译与生命周期

```text
L4 connection → listener (dedicated port or shared 443 SNI)
              → StreamConfig by protocol and port
              → optional TLS termination (auto_cert / cert_file)
              → stream connection pool → forward to service endpoint
```

- **聚合为 StreamConfig**：解析器按 `协议 + 端口` 聚合同一服务的所有实例，生成命名为 `auto-<服务名>-<协议>-<端口>` 的动态流配置。
- **服务发现隔离**：实例端点注册到以 `stream:<协议>:<端口>` 为标识的发现缓存中，与 HTTP 站点的连接池相互隔离。
- **冲突 Fail-Closed**：同一端口上不同实例声明了不一致的 TLS 配置时，网关会记录错误并直接跳过该端口流（Fail-Closed），避免出现未预期的明文暴露或安全降级。
- **端口共享**：除独立端口监听外，在已配置 SNI Mux 的全局入口（如 `websecure` 443 端口）上，支持根据 TLS ClientHello 中的 SNI 域名将流量分流到对应 Stream，与七层 HTTPS 共享公网入口。

## 8. 标签与站点 YAML

| 能力 | 服务标签 | 站点 YAML |
| :--- | :--- | :--- |
| 转发到注册服务 | 支持 | 支持 |
| 转发到其他服务、静态文件、重定向、模板等其他动作 | 不支持 | 支持 |
| Host / 路径 / 方法 / 头 / 参数匹配 | 支持 | 支持 |
| 中间件 | 支持，须在标签内定义 | 支持 |
| 超时、重试、熔断、健康检查、负载均衡 | 支持(Service 属性) | 支持 |
| 站点证书、IP 限制、强制 HTTPS 等站点级设置 | 不支持 | 支持 |
| 新开监听端口 | 仅限 allowed_ports | 由 config.yaml 定义 |
| 四层 TCP/UDP 流代理 | 支持 (tcp.port / udp.port) | 支持 (streams/*.yaml) |

同一个域名同时有站点 YAML 和标签路由时，两者合并为一个站点：

- 路由合并后统一排序：priority 高者优先，其次路径越具体越优先。所以 YAML 的 `/` 不会遮住标签的 `/api`。
- 站点级设置(证书、IP 限制、标题等)以 YAML 为准。
- 中间件同名但配置不同时以 YAML 为准，标签中的定义被忽略并记录错误日志。

## 9. 常见问题

| 现象 | 原因 |
| :--- | :--- |
| 实例在 dashboard 显示诊断，没有生成路由 | 有未知属性、无效引用或冲突配置，整个实例被拒绝。按"did you mean"修正 |
| 443 上没有路由 | 显式写了 `entrypoints=web`；去掉即可同时挂 `web` 和 `websecure` |
| 中间件时有时无 | 同一域名下两个服务用了同名、配置不同的中间件。中间件名按域名共享，请加服务前缀 |
| 部分请求走到另一个服务 | 两个服务声明了相同的匹配条件；priority 高者生效，相同时按服务名确定一个 |
| 没写路径却只匹配 `/<服务名>` | Host、路径、rule 都没写时，路径前缀默认 `/<服务名>`。要接管根路径写 `match.path_prefix=/` |
| 新端口没监听 | 端口不在 `service_discovery.tag_entrypoints.allowed_ports` 中 |
| 四层端口未监听或被拒绝 | 实例间 TLS 配置冲突、auto_cert 缺少 domains，或端口已被系统占用 |
