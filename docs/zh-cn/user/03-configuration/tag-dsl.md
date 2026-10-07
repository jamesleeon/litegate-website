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
- 用 MCP 生成标签时：先 `get_tag_reference` 或 `explain_tag`，最终标签集必须经过 `preview_service_tags`，诊断为空才能应用。

## 11. 已移除的写法

`litegate.ingress.*`、`litegate.route.*`、`litegate.router.*`、`litegate.service.*`、`litegate.upstream.*`、`litegate.middleware.*`、`litegate-http-*` 等旧写法已全部移除，带有它们的实例会被拒绝。
