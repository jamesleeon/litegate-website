<!-- GENERATED FILE — DO NOT EDIT.
     Source: internal/configdocs/docs/zh/tag-dsl.md (package internal/configdocs)
     Regenerate: go generate ./internal/configdocs/...
     Edit the source instead; a drift test fails if this copy is edited directly. -->

# LiteGate 服务标签使用指南

服务在注册时带上 `litegate.*` 标签(Litemesh / Consul metadata、Docker label、Kubernetes 注解)，网关就会自动为它生成路由，不需要写站点 YAML。本文按场景说明怎么写；每个标签的完整说明见《服务标签参考》，设计原理见《服务标签架构》。

## 1. 先选写法

| 需求 | 写法 |
| :--- | :--- |
| 一个域名(或一个路径)转发到本服务，不需要任何策略 | 快捷模式：最多 4 个标签 |
| 多个路由、中间件、IDS、超时 / 重试 / 熔断、独立端口 | 命名资源：`litegate.http.routers.*` 等 |

两种写法不能混用。一旦需要任何策略，就整体改写成命名资源。

## 2. 快捷模式

```properties
litegate.http.host=api.example.com
litegate.http.path_prefix=/api
litegate.http.strip_path=true
```

| 标签 | 含义 |
| :--- | :--- |
| `litegate.http.host` | 域名，可写多个(逗号分隔)。不写时使用 catalog 的 `default_domain`：`<服务名>.<default_domain>` |
| `litegate.http.path` | 精确路径 |
| `litegate.http.path_prefix` | 路径前缀；`path` 与 `path_prefix` 都不写时为 `/` |
| `litegate.http.strip_path` | `true` 时转发前去掉匹配的路径，需要显式写 `path` 或 `path_prefix` |

快捷模式就是一个名为 `main` 的普通 Router：同时挂到 `web`(80) 和 `websecure`(443)，转发到注册服务本身，使用默认策略。

## 3. 命名资源：最小写法

```properties
litegate.http.routers.orders.match.hosts=orders.example.com
litegate.http.routers.orders.match.path_prefix=/api
```

这两行等价于快捷模式，只是 Router 有了名字 `orders`。没写的部分都有默认值：

- `entrypoints` 不写：挂到 `web` 和 `websecure`。
- `service` 不写：没有声明 Service 时转发到注册服务本身(默认策略)；只声明了一个 Service 时用它。
- 没有 Host 条件：匹配入口上的任意 Host。

资源名只能用小写字母、数字、`-`、`_`；属性路径全小写。

## 4. 给服务加策略

策略写在 Service 上。只声明一个 Service 时，Router 不用写 `service`：

```properties
litegate.http.routers.orders.match.hosts=orders.example.com
litegate.http.services.orders.timeout=30s
litegate.http.services.orders.retry.attempts=2
litegate.http.services.orders.healthcheck.path=/healthz
litegate.http.services.orders.healthcheck.interval=10s
litegate.http.services.orders.circuitbreaker.enabled=true
litegate.http.services.orders.loadbalancer.strategy=least_conn
```

- `timeout` 是单个请求的端到端超时(`30s`、`500ms`)，WebSocket 等升级请求只用它限制握手。
- Service 永远描述注册这些标签的服务本身。`discovery.name` 可以不写；写了就必须等于注册服务名。

## 5. 多个路由

一个服务可以有多个 Router，各自匹配、各自挂中间件：

```properties
litegate.http.routers.shop.match.hosts=shop.example.com
litegate.http.routers.admin.match.hosts=shop.example.com
litegate.http.routers.admin.match.path_prefix=/admin
litegate.http.routers.admin.priority=100
litegate.http.routers.admin.middlewares=shop-admin-limit
litegate.http.middlewares.shop-admin-limit.ratelimit.qps=20
```

`priority` 越大越先匹配；优先级相同时，路径越具体越先匹配。

声明了多个 Service 时，每个 Router 必须写 `service`，而且名字必须已声明；拼错会报错并提示最接近的名字，不会悄悄换成默认策略。

## 6. Router 匹配

`rule` 与结构化 `match.*` 二选一：

```properties
# 结构化写法
litegate.http.routers.orders.match.hosts=orders.example.com
litegate.http.routers.orders.match.path_prefix=/api
litegate.http.routers.orders.match.methods=GET,POST
litegate.http.routers.orders.match.headers.X-App=console
litegate.http.routers.orders.match.query.version=v2

# Rule 写法
litegate.http.routers.orders.rule=Host(`orders.example.com`) && PathPrefix(`/api`)
```

`match.path` 与 `match.path_prefix` 二选一。Host、路径和 `rule` 都不写时，路径前缀默认是 `/<服务名>`，避免多个服务争抢根路径；要接管根路径请显式写 `match.path_prefix=/`。

## 7. 中间件

写法 `litegate.http.middlewares.<名称>.<类型>.<属性>=<值>`，属性与站点 YAML 中同类型中间件的 `config` 相同：

```properties
litegate.http.middlewares.strip-api.strip_prefix.prefixes=/api
litegate.http.middlewares.limit.ratelimit.qps=150
litegate.http.middlewares.cors-api.cors.allowed_origins=https://app.example.com
litegate.http.routers.orders.middlewares=strip-api,limit,cors-api
```

- 中间件必须在标签里定义，才能被 Router 引用，按列出的顺序执行。
- 中间件名在同一个域名下是共享的：两个服务在同一域名下用同一个名字、配置却不同，该中间件会被判为失效。请用带服务前缀的名字，如 `orders-limit`。

## 8. 实例选择与 IDS

Service 的 selector 决定用哪些实例：

```properties
litegate.http.services.shared-app.discovery.selector.match.sid=c1
litegate.http.services.shared-app.discovery.selector.meta.version=v2
```

- `selector.match.<key>` 是硬边界：只用 metadata 中 `<key>` 等于该值的实例。
- `selector.meta.<key>` 是软偏好：有命中的实例就用它们，没有就回退到完整的硬匹配集合。

实例在注册时声明自己的身份。Provider 能上报 metadata 时直接写 `sid=c1`，否则写 `litegate.instance.labels.sid=c1`(硬匹配) / `litegate.instance.meta.version=v2`(软偏好)。实例标签可以每个实例不同；路由与资源标签必须在所有实例上一致。

IDS 是 Router 的属性。多个 Router 可以用不同的 operation 共享同一个服务：

```properties
litegate.http.routers.login.match.path=/login
litegate.http.routers.login.ids.provider=session
litegate.http.routers.login.ids.operation=login

litegate.http.routers.api.match.path_prefix=/api
litegate.http.routers.api.ids.provider=session
litegate.http.routers.api.ids.operation=resolve
```

IDS 返回的 selector 只能在该服务的实例里继续缩小范围；与 Service 的硬 selector 同键不同值时请求被拒绝。`ids.failpolicy` 默认 `deny`。

## 9. 入口与独立端口

Router 可以按名称引用 config.yaml 中的任何入口：

```properties
litegate.http.routers.internal.entrypoints=admin
```

标签也可以新开一个 HTTP 监听，但端口必须列在网关的 `service_discovery.tag_entrypoints.allowed_ports` 中，且不能与 config.yaml 的入口同名或同端口：

```properties
litegate.entrypoints.api-8080.address=:8080
litegate.http.routers.api.entrypoints=api-8080
litegate.http.routers.api.match.path_prefix=/
```

config.yaml 中需要：

```yaml
service_discovery:
  tag_entrypoints:
    allowed_ports: [8080]
```

## 10. 校验

- 写错的标签不会被静默忽略：未知属性、无效引用、冲突配置都会让该实例整体被拒绝，并给出"did you mean"建议。
- dashboard 的服务标签页按实例列出每个标签的分类与诊断。
- 用 MCP 生成标签时：先 `get_tag_reference` 或 `explain_tag`，最终标签集必须经过 `preview_service_tags`，修复所有 error、确认 warning 后才能应用。

## 11. 已移除的写法

`litegate.ingress.*`、`litegate.route.*`、`litegate.router.*`、`litegate.service.*`、`litegate.upstream.*`、`litegate.middleware.*`、`litegate-http-*` 等旧写法已全部移除，带有它们的实例会被拒绝。


## 注册服务的限流与熔断

在 orders 服务的每个实例上注册相同的资源标签。限流按客户端 IP，在一分钟滑动日志窗口内最多放行 100 次请求；熔断按后端地址分别统计最近 30 秒完成的调用，至少 20 个样本且失败率达到 0.5 时打开。限流 window 接受时长（1m）或整数毫秒；熔断 window 使用整数秒（30）。实例注销在发现更新到达网关后才从候选集中移除，传播期间的调用仍可能失败；后端实际失败仍应计入熔断。不要混用命名资源和快捷标签。

```properties
litegate.http.routers.orders.match.hosts=api.example.com
litegate.http.routers.orders.match.path_prefix=/orders
litegate.http.routers.orders.service=orders
litegate.http.routers.orders.middlewares=orders-limit
litegate.http.middlewares.orders-limit.ratelimit.qps=100
litegate.http.middlewares.orders-limit.ratelimit.key=ip
litegate.http.middlewares.orders-limit.ratelimit.algorithm=sliding_window_log
litegate.http.middlewares.orders-limit.ratelimit.window=1m
litegate.http.services.orders.circuitbreaker.enabled=true
litegate.http.services.orders.circuitbreaker.strategy=failure_rate
litegate.http.services.orders.circuitbreaker.window=30
litegate.http.services.orders.circuitbreaker.minimumrequests=20
litegate.http.services.orders.circuitbreaker.failureratio=0.5
```

通过 MCP 生成时，先读取 `get_config_guide(topic="traffic")`，再运行 `preview_service_tags`：修复所有 error，确认 warning 后应用。YAML 配置先运行 `validate_site_config`，再运行 `save_site_config`。

## 运维管理的公共资源

在主配置中声明公共资源：

```yaml
resources:
  middlewares:
    security:
      type: headers
      properties:
        response.X-Content-Type-Options: nosniff
  serverstransports:
    backend:
      dialtimeout: 2s
      responseheadertimeout: 10s
      tls:
        enabled: true
        servername: backend.example.com
  tlsoptions:
    modern:
      min_version: "1.3"
```

使用 `litegate.http.routers.api.middlewares=security@file`、`litegate.http.services.app.loadbalancer.serverstransport=backend@file` 和 `litegate.http.routers.api.tls.options=modern@file` 显式引用。普通名称只查当前服务的局部定义；同名局部资源不能覆盖 `@file`。其他后缀、缺失资源和带限定后缀的声明名称都会被拒绝。局部中间件按 Provider 实例、命名空间和服务隔离，共用 Host 的不同服务也不会互相覆盖。公共中间件使用与标签 DSL 相同的类型和属性。

TLS options 要求入口已经启用 TLS，并在同一 Host 的所有端口生效。有效策略发生冲突时，整套候选配置被拒绝。公共 options 不允许绑定到 catch-all Host；已有旧式 catch-all TLS 配置保持支持，但不能绕过具体 Host 的客户端证书要求。更新策略会保留站点自定义证书和缓存身份。可配置协议版本、TLS 1.2 密码套件及可选或强制客户端认证；不提供命名证书解析器，也不改变统一 ACME 配置。

运维定义的上游 transport 可使用 `tls.rootca_file`；TLS options 可使用 `client_ca_file` 和 `client_crl_file`。工作负载标签只接受 PEM 证书内容，不接受网关文件路径。准备候选配置时捕获信任文件，提交时不会重新读取；修改信任文件后需重新加载主配置。无效更新，包括删除仍被引用的资源，会保留整套已接受配置。MCP 预览使用运行时已接受的资源解析器。

站点 YAML 也可在 `services.<name>.loadbalancer.serverstransport` 引用公共 transport，在路由的 `middlewares` 列表引用公共中间件，并通过 `tls.options` 引用公共 TLS 策略。

## Docker 与 Swarm 故障行为

Swarm 的 Service 声明与运行中的 Task 独立。已声明的 HTTP 服务缩容到零时，网关保留 Router 并发布空后端池，普通请求和升级请求均返回 **503**。不健康的实例，以及明确要求等待主动健康检查的启动实例，也属于无可用后端。已经选中实例后发生的连接失败仍返回 **502**。删除 Swarm Service 会删除声明及 Router。独立 Docker 模式继续发现运行中的容器，移除或停止最后一个容器会移除该容器的声明。

Docker 与 Swarm 从完整来源快照同时发布标签和实例。服务列表、Task 列表或容器检查遇到临时错误时，保留上一次成功快照，不发布部分删除；容器检查明确返回 404 时按实例消失处理。独立容器保留各自的资源声明，滚动更新期间不同实例的标签冲突仍分别处理。无效资源标签会拒绝对应路由，不会制造虚假实例。

在独立 Docker 模式成功解析宿主映射端口后，每个 HTTP Service 的 `loadbalancer.server.port` 表示**容器端口**。网关将它分别映射到对应的宿主地址及端口，支持 IPv6。某个端口没有映射时，会从该 Service 排除实例并生成诊断，不会借用另一个 Service 的端口映射。如果 Provider 无法解析宿主映射而整体回退到容器直连，则保留已有的直连行为。端口映射来源信息仅在内部保存，工作负载元数据不能伪造它。

主动健康检查默认保留乐观启动行为以兼容现有配置。启用主动检查并设置 `healthcheck.initialready=false` 后，首次探测成功且达到配置的恢复阈值前不会接收流量。诊断将来源声明和实例分别展示，因此零实例服务仍可检查其声明。


# Swarm Service VIP

在 Service 标签中设置 `litegate.swarm.lbswarm=true` 使用 Service VIP。必须用 `litegate.docker.network` 或 catalog 的 `swarm_network` 显式选择网络；Provider 验证网络匹配并排除 ingress。DNSRR、缺少匹配 VirtualIP 或无效网络选择均禁止回退到 Task IP，诊断保留在声明中。零运行 Task 保留路由和空后端池，返回 503。`false` 保持默认 Task 地址模式；普通容器不支持 Service VIP。

VIP 隐藏各个 Task，因此静态实例选择器、元数据选择器和灰度策略会拒绝路由编译。请求时选择器（包括 IDS 的 `selector_merge_policy: override`）、元数据、标签偏好和灰度策略，在普通请求及 upgrade 请求中均返回 503，即使 Service 元数据看起来匹配也不会放行。IDS 决策仍先于端点选择执行。
## HTTP Service 组合

命名 Service 可以是叶节点、加权组或故障转移组。组引用其他命名 Service；循环、缺失引用、重复子节点、混合类型和非正权重会拒绝配置。加权槽位必须同时配置名称和权重：

```text
litegate.http.routers.graph.match.hosts=graph.example.com
litegate.http.routers.graph.service=root
litegate.http.services.root.weighted.services.a.name=one
litegate.http.services.root.weighted.services.a.weight=1
litegate.http.services.root.weighted.services.b.name=two
litegate.http.services.root.weighted.services.b.weight=3
litegate.http.services.one.loadbalancer.server.port=8080
litegate.http.services.two.loadbalancer.server.port=8081
```

权重选择子组，不随副本数量变化。故障转移可把四个加权字段替换为 `litegate.http.services.root.failover.service=one` 和 `litegate.http.services.root.failover.fallback=two`。主分支为空或不健康时直接选择备用，不消耗实际尝试；连接失败或配置的重试状态码只在根节点重试预算和现有请求体重放规则内切换分支。每个叶节点拥有独立端口、传输、健康检查和负载均衡池。实际连接失败保留 502；没有可用叶节点返回 503。

标签叶节点只使用注册该标签的工作负载来源。站点 YAML 叶节点可使用静态 `servers`，或明确的 Docker 来源 `discovery: {provider: docker, namespace: default, name: backend}`。可选 `instance: "0"` 指定已配置 Docker provider 实例；来源歧义会拒绝请求。目前不支持其他显式来源 provider。首次发现尚未完成时保留路由并返回 503，成功发现后恢复。

组的 `discovery.selector.match` 是所有后代叶节点的硬条件，叶节点可增加自身条件。最终 IDS 条件与硬条件取交集，即使启用了 override。主分支自身条件不会继承给同级备用分支；需要共同租户边界时必须在根节点明确声明。硬条件中的每个变量必须解析为非空值；未知、缺失或格式错误的占位符使整个请求失败，不允许通过备用分支绕过。

组合支持普通 HTTP 和 HTTPS。升级请求返回 503；gRPC 和 gRPC-Web 返回 RPC unavailable（状态 14），不访问上游。粘性 Cookie 和子节点重试、超时策略会被拒绝；统一超时和重试策略配置在根节点。IDS 只评估一次，允许重放时只缓冲一次请求体，最终响应钩子只执行一次。上游重定向直接返回客户端。
# 命名 TCP 与 UDP 资源

命名四层资源编译到现有 stream 引擎。名称隔离于 provider、namespace 和注册服务；Service 使用该服务当前的实例、零实例声明或带类型的 Swarm VIP，不能指向其他注册服务。未知属性和引用会拒绝候选配置。

```text
# 明文 TCP
litegate.entrypoints.database.address=:8090
litegate.entrypoints.database.protocols=tcp
litegate.tcp.routers.database.entrypoints=database
litegate.tcp.routers.database.service=db
litegate.tcp.services.db.loadbalancer.server.port=8090
# UDP
litegate.entrypoints.datagrams.address=:8091
litegate.entrypoints.datagrams.protocols=udp
litegate.udp.routers.datagrams.entrypoints=datagrams
litegate.udp.routers.datagrams.service=udp
litegate.udp.services.udp.loadbalancer.server.port=8091
# TLS 透传
litegate.entrypoints.sharedtls.address=:8444
litegate.entrypoints.sharedtls.protocols=tcp
litegate.tcp.routers.secure.entrypoints=sharedtls
litegate.tcp.routers.secure.service=tlsbackend
litegate.tcp.routers.secure.match.sni=one.acceptance.invalid
litegate.tcp.routers.secure.tls.enabled=true
litegate.tcp.routers.secure.tls.passthrough=true
litegate.tcp.services.tlsbackend.loadbalancer.server.port=8443
```

网关须配置 `service_discovery.tag_entrypoints.allowed_ports: [8090, 8091, 8444]`。TCP/UDP 标签监听仅允许 `:port` 或 `0.0.0.0:port`；后端端口单独配置，Docker 宿主映射模式分别使用 TCP 或 UDP 映射。全局 stream IP 限制仍然生效。

不同注册服务的 TLS 透传路由可共用一个 TCP 监听。精确 SNI 优先，其次是最具体的通配符；缺失或未匹配的 SNI 拒绝连接，不访问后端。ClientHello 和后续字节原样转发。重复 SNI、同端口混合明文与 TLS、多条明文或 UDP 路由、operator/静态/HTTP 监听冲突均拒绝发布，保留上一代已接受配置。声明删除移除路由；零实例声明保留路由并拒绝新流量，恢复后选择当前实例。

UDP 实例更新或归零会关闭旧会话，固定客户端源端口也会重新选择后端。已建立的 TCP 会话可以继续使用原实例；新连接解析当前实例池。

命名资源仍依赖入口或端口时，删除 allowed_ports 授权、移除 operator 入口或放宽其拒绝策略，会拒绝整个主配置候选并保留已接受的一代配置。应先删除依赖声明。主配置变更需要现有的显式 reload 操作；单独编辑主配置文件不会触发加载。

命名标签不支持 TLS 终止、证书文件路径、certresolver、四层中间件/IDS 策略或服务组合，配置这些字段会报错。现有 operator TLS 配置不变。仅当 operator 入口的 `default`、`on_non_tls`、`on_no_sni` 均为 `reject`、地址是 TCP 网络监听、SNI 不与 HTTP 或静态 stream 重叠时，才能附着 TCP TLS 透传路由；含正则或 catch-all 路由的 operator 入口不接受附着。UDP 不能附着 TCP 入口，且拒绝所有 TLS/SNI 属性，包括 false 值。
