<!-- GENERATED FILE — DO NOT EDIT.
     Source: internal/configdocs/docs/zh/tag-reference.md (package internal/configdocs)
     Regenerate: go generate ./internal/configdocs/...
     Edit the source instead; a drift test fails if this copy is edited directly. -->

# LiteGate 服务标签参考

本文由 `internal/loader/tag_reference.go` 从解析器的属性表生成，列出网关接受的全部标签。用法与示例见《服务标签 DSL》。

## 两种写法

| 写法 | 标签 | 适用 |
| :--- | :--- | :--- |
| 快捷模式 | `litegate.http.host/path/path_prefix/strip_path` | 一个服务一个路由，不需要任何策略 |
| 命名资源 | `litegate.entrypoints.*`、`litegate.http.routers.*`、`litegate.http.services.*`、`litegate.http.middlewares.*`、`litegate.http.serverstransports.*` | 多路由、中间件、IDS、超时重试等策略 |

两种写法不能混用。属性路径全小写；资源名只能用小写字母、数字、`-`、`_`。未知属性、无效引用、冲突配置都会让该实例整体被拒绝(fail closed)，诊断显示在 dashboard 与 MCP `preview_service_tags`。

## 快捷模式

| 标签 | 值 | 含义 |
| :--- | :--- | :--- |
| `litegate.http.host` | Host 列表 | 不写时使用 catalog 的 `default_domain`(`<服务名>.<default_domain>`) |
| `litegate.http.path` | path | 精确路径；与 path_prefix 互斥 |
| `litegate.http.path_prefix` | path | 路径前缀；path 与 path_prefix 都不写时为 `/`。也可写作 `litegate.http.pathprefix` |
| `litegate.http.strip_path` | bool | 转发前剥离匹配的路径 |

快捷模式编译为一个名为 `main` 的普通 Router，默认值与命名 Router 相同：挂到 `web` 与 `websecure`，Service 为注册服务的默认策略。需要任何策略时改用命名资源。

## 默认值

| 省略 | 效果 |
| :--- | :--- |
| `routers.<name>.entrypoints` | 挂到 `web` 与 `websecure` |
| `routers.<name>.service` | 唯一声明的 Service；未声明时为注册服务的默认策略；声明多个时必须写明 |
| Host 条件 | 匹配入口上的任意 Host |
| Host 与路径条件都没有(且无 rule) | 路径前缀为 `/<服务名>`(服务名中的 `-` 变为 `/`)，避免多个服务争抢根路径 |
| `services.<name>.discovery.name` | 注册服务本身 |

## EntryPoint

前缀 `litegate.entrypoints.<name>.`

| 属性 | 值 | 含义 |
| :--- | :--- | :--- |
| `address` | [ip]:port | 新开一个 HTTP 监听。端口必须列在 service_discovery.tag_entrypoints.allowed_ports，且不能与 config.yaml 的入口同名或同端口。 |
| `protocols` | http | 可省略；标签定义的入口只支持 http。 |
| `tls.enabled` | bool | 该监听是否终止 TLS。 |

## HTTP Router

前缀 `litegate.http.routers.<name>.`

| 属性 | 值 | 含义 |
| :--- | :--- | :--- |
| `entrypoints` | list | 挂载的入口，默认 web,websecure。可引用 config.yaml 中的任何入口。 |
| `rule` | rule | Traefik 风格规则，如 Host(`a.com`) && PathPrefix(`/api`)；与 match.* 互斥。 |
| `priority` | int | 数值越大越先匹配。 |
| `middlewares` | list | 按顺序执行的中间件名。 |
| `service` | name | 可省略：只有一个 Service 时用它，没有时用注册服务的默认策略。写了就必须已声明。 |
| `match.hosts` | list | Host 列表；不写 Host 时匹配入口上的任意 Host。 |
| `match.path` | path | 精确路径；与 match.path_prefix 互斥。 |
| `match.path_prefix` | path | 路径前缀。 |
| `match.pathprefix` | path | match.path_prefix 的兼容写法；两者都写且值不同时报错。 |
| `match.methods` | list | HTTP 方法列表。 |
| `match.headers.<header>` | value | 请求头等值匹配，头名保留大小写。 |
| `match.query.<param>` | value | 查询参数等值匹配。 |
| `ids.provider` | name | IDS 插件名；写了即启用 IDS。 |
| `ids.operation` | name | 传给插件的操作，如 login、resolve、logout。 |
| `ids.failpolicy` | deny \| allow | 插件失败时的处理，默认 deny；allow 只在安全时放行。 |
| `ids.allowedheaders` | list | 允许插件投影到上游的请求头。 |
| `ids.options.<key>` | value | 传给插件的参数，键保留大小写。 |
| `observability.accesslogs` | bool | false 关闭该路由的访问日志。 |
| `observability.tracing` | bool | 该路由的边缘 Span 必定采样上报（不受 sample_ratio 影响），需全局 tracing.enabled。 |
| `observability.status.enabled` | bool | 开启该路由的内置状态页。 |
| `observability.status.path` | path | 状态页路径，默认 /_status。 |
| `observability.status.showinstances` | bool | 状态页是否列出实例。 |

## HTTP Service

前缀 `litegate.http.services.<name>.`

| 属性 | 值 | 含义 |
| :--- | :--- | :--- |
| `discovery.name` | name | 可省略；写了必须等于注册服务名(Service 永远描述注册服务本身)。 |
| `discovery.selector.match.<key>` | value | 硬边界：只选 metadata 中 `<key>` 等于该值的实例。 |
| `discovery.selector.meta.<key>` | value | 软偏好：优先命中的实例，没有命中时回退到完整硬匹配集合。 |
| `timeout` | duration | 单个请求的端到端超时，如 30s、500ms；升级请求只限制握手。 |
| `loadbalancer.strategy` | strategy | 负载均衡策略：round_robin、weighted、weighted_round_robin、least_conn、p2c、ip_hash、cookie 或插件注册的策略。 |
| `loadbalancer.server.port` | port | 覆盖实例端口；0 或不写使用实例上报的端口。 |
| `loadbalancer.server.scheme` | http \| https \| h2c \| grpc \| grpcs | 上游协议。 |
| `loadbalancer.serverstransport` | name | 引用的 ServersTransport。 |
| `healthcheck.path` | path | 主动健康检查路径。 |
| `healthcheck.interval` | duration | 主动健康检查间隔。 |
| `retry.attempts` | int | 失败重试次数。 |
| `circuitbreaker.enabled` | bool | 开启熔断。 |
| `circuitbreaker.timeout` | seconds | 熔断打开持续时间，默认 60。 |
| `circuitbreaker.maxrequests` | int | 半开状态允许的请求数，默认 1。 |
| `circuitbreaker.tripthreshold` | int | 触发熔断的连续失败次数，默认 3。 |

## ServersTransport

前缀 `litegate.http.serverstransports.<name>.`

| 属性 | 值 | 含义 |
| :--- | :--- | :--- |
| `tls.enabled` | bool | 上游使用 TLS；未写 scheme 时默认 https。 |
| `tls.insecureskipverify` | bool | 跳过上游证书校验，不能与 clientcertificate 同用。 |
| `tls.clientcertificate` | litemesh | 使用 Litemesh 身份做双向 TLS。 |

## HTTP Middleware

写法 `litegate.http.middlewares.<name>.<type>.<property>=<value>`，属性与站点 YAML 中同类型中间件的 `config` 完全相同，由中间件自身校验。内置类型：`api_key`、`basic_auth`、`chain`、`circuit_breaker`、`compress`、`cors`、`headers`、`jwt_auth`、`limit_conn`、`mirror`、`ratelimit`、`redirect_regex`、`redirect_scheme`、`remote_auth`、`replace_path_regex`、`retry`、`rewrite`、`strip_prefix`。一个中间件只能有一个类型。`retry`、`circuit_breaker` 已弃用（仍可用，加载时提示），请改用 Service 的 `retry.attempts`、`circuitbreaker.*`。

## 其他标签

| 标签 | 范围 | 含义 |
| :--- | :--- | :--- |
| `litegate.enable` | provider | Docker/Swarm：显式开关该容器是否被发现(true/false)。不写时有任何 litegate.* 标签即被发现。 |
| `litegate.docker.network` | provider | Docker/Swarm：用哪个网络的地址访问该容器。 |
| `litegate.docker.usehostport` | provider | Docker：通过宿主机映射端口访问该容器(Swarm 不支持)。 |
| `litegate.instance.labels.<key>` | instance | 实例身份标签：被 discovery.selector.match 与 IDS 硬匹配。Provider 能直接上报 metadata 时写 `<key>=<value>` 即可。 |
| `litegate.instance.meta.<key>` | instance | 实例偏好元数据：被 discovery.selector.meta 软匹配，未命中时回退。 |
| `litegate.instance.weight` | instance | 实例负载均衡权重(正整数)。 |
| `litegate.instance.gray` | instance | 标记该实例为灰度实例。 |
| `litegate.instance.version` | instance | 实例版本，写入 endpoint 的 version 元数据。 |
| `litegate.instance.debugheaders` | instance | 诊断：在响应中暴露所选上游地址等调试头(true/false)。 |
| `litegate[.<group>].tcp.port / udp.port` | stream | 四层代理：网关在该端口监听并转发到实例注册的端口；端口须在 allowed_ports 中。 |
| `litegate[.<group>].tcp.tls.enabled / auto_cert / domains / cert_file / key_file / min_version` | stream | 四层 TCP 监听的 TLS 终止设置。 |

实例标签(`litegate.instance.*`)可以每个实例不同；路由与资源标签必须在同一服务的所有实例上一致。

## 已移除

`litegate.ingress.*`、`litegate.route.*`、`litegate.router.*`、`litegate.service.*`、`litegate.upstream.*`、`litegate.middleware.*`、`litegate.ids.*`、`litegate.site.*`、`litegate.entrypoint.*`、`litegate.io.*`、`litegate-http-*` 以及上表之外的 `litegate.http.*` 都已移除。带有这些标签的实例会被整体拒绝。
