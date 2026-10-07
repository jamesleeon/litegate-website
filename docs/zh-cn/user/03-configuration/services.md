# 命名 Service 与配置分层

本文介绍站点配置中的 `services` / `serverstransports`，以及一个能力应该写在路由、中间件还是 Service 里。最后一节是从旧版本升级的注意事项。

---

## 1. 四个问题，四个位置

一条请求经过网关时，配置要回答四个问题。每个问题在配置里有一个固定的位置：

| 问题 | 写在哪里 | 典型内容 |
|---|---|---|
| **去哪里？** | 路由 `routes[].match`、`priority` | Host、路径、方法、请求头匹配 |
| **进出时做什么？** | 中间件 `middlewares`（或 action 内联字段） | CORS、鉴权、限流、WAF、改写、压缩、缓存 |
| **怎么到达后端？** | **Service** `services` | 服务发现、负载均衡、超时、重试、熔断、健康检查、上游 TLS |
| **谁来生成响应？** | action `type` | proxy、serve、template、respond、redirect …… |

判断一个配置项属于哪里，看它需不需要知道后端：

*   **不需要知道后端**，放在 serve、template 前面也成立的，是中间件。例如 CORS、限流、压缩。
*   **需要在“选实例、发请求、看结果”过程中起作用**的，是 Service。例如重试要换一个实例再试，熔断要记录某个实例的失败。

---

## 2. 最小例子

以前写法：每条路由各自写一遍上游配置。

```yaml
routes:
  - match: { path_prefix: /orders }
    action:
      type: proxy
      service_name: orders
      lb_policy: least_conn
      timeout: 5
      retry: 2
  - match: { path_prefix: /v2/orders }
    action:
      type: proxy
      service_name: orders
      lb_policy: least_conn
      timeout: 5
      retry: 2
```

新写法：把“怎么到达后端”定义一次，路由按名字引用。

```yaml
services:
  orders:
    discovery: { name: orders }
    timeout: 5s
    loadbalancer: { strategy: least_conn }
    retry: { attempts: 2 }

routes:
  - match: { path_prefix: /orders }
    action: { service: orders }
  - match: { path_prefix: /v2/orders }
    action: { service: orders }
```

两种写法效果相同，旧写法继续有效。引用同一个 Service 的路由共享健康状态与熔断状态；通过服务发现的 Service 还共享负载均衡器，静态 `servers` 由每条路由各自维护轮询计数。

---

## 3. `services` 字段

除 YAML 专用的静态地址与 DNS 解析器引用外，键名与服务发现标签 `litegate.http.services.<name>.*` 一一对应，校验规则也相同。同一个服务无论写在站点 YAML 还是服务标签里，含义都一样。

```yaml
services:
  orders:
    discovery:
      name: orders
      selector:
        match: { version: v2 }
        meta: { zone: a }
    timeout: 5s
    loadbalancer:
      strategy: least_conn
      server: { port: 8080, scheme: https }
      serverstransport: mesh
    healthcheck: { path: /health, interval: 10s }
    retry: { attempts: 2 }
    circuitbreaker: { enabled: true, timeout: 60, maxrequests: 1, tripthreshold: 3 }

  legacy:
    servers: ["http://10.0.0.1:8080", "http://10.0.0.2:8080"]
```

| YAML 键 | 对应的服务标签 | 说明 |
|---|---|---|
| `discovery.name` | `discovery.name` | 服务发现中的服务名。与 `servers` 二选一 |
| `discovery.selector.match.<key>` | 同名 | 硬边界：只选 metadata 中该键等于该值的实例 |
| `discovery.selector.meta.<key>` | 同名 | 软偏好：优先命中，无命中时回退到硬边界内的全部实例 |
| `servers` | —（仅 YAML） | 静态后端地址列表。与 `discovery.name` 二选一，不能配合 `selector` |
| `resolver` | —（仅 YAML） | 引用全局命名 DNS 解析器，见 [上游自定义 DNS](upstream-dns.md) |
| `timeout` | `timeout` | 单个请求的端到端超时，如 `30s`、`500ms` |
| `loadbalancer.strategy` | `loadbalancer.strategy` | `round_robin`、`weighted`、`weighted_round_robin`、`least_conn`、`p2c`、`ip_hash`、`cookie` 或插件策略 |
| `loadbalancer.server.port` | `loadbalancer.server.port` | 覆盖实例端口 |
| `loadbalancer.server.scheme` | `loadbalancer.server.scheme` | `http`、`https`、`h2c`、`grpc`、`grpcs` |
| `loadbalancer.serverstransport` | `loadbalancer.serverstransport` | 引用的 ServersTransport |
| `healthcheck.path` / `healthcheck.interval` | 同名 | 主动健康检查 |
| `retry.attempts` | `retry.attempts` | 失败重试次数 |
| `circuitbreaker.enabled` / `timeout` / `maxrequests` / `tripthreshold` | 同名 | 熔断：开启、打开持续秒数、半开请求数、触发的连续失败数 |

注意：这里的键名沿用标签写法（`maxrequests`、`serverstransport`），不是下划线形式。

## 4. `serverstransports` 字段

```yaml
serverstransports:
  mesh:
    tls:
      enabled: true               # 上游使用 TLS；Service 未写 scheme 时默认 https
      clientcertificate: litemesh # 使用 Litemesh 身份做双向 TLS
      insecureskipverify: false   # 跳过上游证书校验，不能与 clientcertificate 同用
```

---

## 5. 引用规则

*   `action.service` 引用的 Service 必须在同一站点的 `services` 中定义，否则加载失败。
*   引用 Service 时可以省略 `type`，默认为 `proxy`。
*   **一条路由的后端只有一个配置来源。** 引用了 `service` 的路由不能再内联上游字段：`service_name`、`upstream`、`lb_policy`、`timeout`、`retry`、`circuit_breaker`、`health_check`、`route_selector`、`route_meta`、`service_port`、`proto`、`insecure_skip_verify`、`mtls`，否则加载失败。
*   `strip_prefix`、`headers` 等不属于 Service 的字段照常写在 action 里：

```yaml
routes:
  - match: { path_prefix: /api/orders }
    middlewares: [web-cors]
    action:
      service: orders
      strip_prefix: /api
```

---

## 6. 什么时候用哪种写法

| 场景 | 建议 |
|---|---|
| 一个后端只被一条路由使用 | 内联写法或 Service 都可以 |
| 多条路由指向同一个后端 | 用 Service，只定义一次，状态共享 |
| 需要重试、熔断、健康检查、上游 TLS | 用 Service，这些都是“怎么到达后端”的问题 |
| 服务通过标签注册到 Consul / LiteMesh | 继续用标签；标签里的 service 与 YAML 的 service 是同一个模型 |

### 命名中间件与内联字段

以下命名中间件与对应的 action 内联字段完全等价，在执行链中的位置也相同，可以按复用需要任选一种：

| 命名中间件类型 | 等价的内联字段 |
|---|---|
| `rewrite` | `action.rewrite` |
| `compress` | `action.compress` |
| `remote_auth` | `action.remote_auth` |

以下两个中间件类型**已弃用**，仍可使用，加载时会提示一次。请改用 Service：

| 已弃用 | 改用 |
|---|---|
| `retry` 中间件 | `services.<name>.retry.attempts` |
| `circuit_breaker` 中间件 | `services.<name>.circuitbreaker.*` |

同一能力不能同时用命名中间件和内联字段配置两次，否则加载失败。

---

## 7. 查看最终执行链

路由最终按什么顺序执行哪些处理，可以直接查看，不需要推断：

*   **Dashboard 接口**：`GET /api/routing/pipeline?site=<域名>&route=<路由名>`，返回按从外到内排列的步骤，包括来源（内联 / 命名）和阶段。
*   **MCP**：`lookup_route` 工具输出中的 `Effective Pipeline`。

执行链与实际运行来自同一份编译结果，两者一定一致。

---

## 8. 从旧版本升级

**替换二进制即可，现有站点配置、服务标签和 Kubernetes 资源都不需要修改。** 升级前请检查下面几项。

### 8.1 需要检查配置的变化

**CORS 安全修复**（详见 [CORS](../05-middleware/cors.md)）：

*   `cors.enabled: true` 不再自动开启凭证（Cookie）。如果依赖它携带 Cookie，请明确列出来源并设置 `allow_credentials: true`。
*   `allowed_origins: "*"`（或 `enabled: true` 未填来源）与 `allow_credentials: true` 同时出现时**加载失败**。请改为列出可信来源。
*   只有带 `Access-Control-Request-Method` 的 `OPTIONS` 才被当作预检直接应答；其他 `OPTIONS`（如 WebDAV）交给 action 处理。
*   路由配置了 CORS 后，后端返回的 `Access-Control-*` 响应头会被网关策略替换。

**proxy action 中的 `service:` 键**：以前在 proxy action 中误写的 `service:` 会被忽略，现在它表示引用 Service，找不到时加载失败。其他类型 action（包括插件）中的 `service:` 仍作为插件参数原样传递。

### 8.2 只影响显示、不影响行为的变化

*   **执行链显示位置更准确。** 命名的 `rewrite`、`compress`、`remote_auth`、`retry`、`circuit_breaker` 现在显示在实际生效的位置。以前的显示与实际执行顺序不一致，执行顺序本身没有变化。
*   **中间件列表中的 chain 可能展开。** 如果路由引用了上一条中的中间件（包括通过 chain 引用），Dashboard 中该路由的中间件列表会显示 chain 展开后的中间件名。
*   **MCP 生成的站点 YAML 键顺序变化**，内容不变。

### 8.3 升级检查清单

1.  搜索站点配置中的 `allow_credentials: true`，确认对应的 `allowed_origins` 是明确的来源列表。
2.  搜索依赖 `cors.enabled: true` 携带 Cookie 的路由，补上来源与 `allow_credentials: true`。
3.  确认 proxy action 中没有遗留的 `service:` 键。
4.  （可选）把重复的上游配置整理为 `services`，把 `retry` / `circuit_breaker` 中间件改为 Service 配置。
5.  启动后查看日志中的弃用提示，并用 `/api/routing/pipeline` 抽查关键路由的执行链。

---

## 延伸阅读

- [站点配置参考](site-config.md)
- [服务标签参考](tag-reference.md)
- [Middleware Pipeline、Chain 与命名能力](../05-middleware/pipeline.md)
- [流量控制与上游治理](../05-middleware/traffic-and-upstream.md)
