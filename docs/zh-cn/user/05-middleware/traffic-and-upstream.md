# 流量控制与上游治理中间件

这一组中间件处理“请求进来后到打后端之间”的保护与治理，分属两个阶段：

- **TrafficControl**（`limit_conn`）：普通 HTTP 层的并发/速率保护。
- **Upstream**（`retry`、`circuit_breaker`）：需要理解后端实例和单次尝试的治理，编译进 Proxy 内部，**只对 `proxy` action 生效**。
- **PostAuth**（`mirror`）：只复制已经过认证的流量。

> 限速（`ratelimit`）单独成篇，见 [Rate Limit 与并发连接限制](./rate-limit.md)。

---

## 1. `limit_conn` —— 并发连接限制

限制路由上**同时在处理**的请求数，防止慢客户端拖垮后端、打满连接池。

```yaml
middlewares:
  concurrency-guard:
    type: limit_conn
    config:
      limit: "100"      # 最大并发在途请求数，正整数
      key: "ip"         # global（默认）= 按路由全局；ip = 按客户端 IP
```

| 字段 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `limit` | int | 是 | 最大并发请求数，必须为正整数。 |
| `key` | string | 否 | `global`（默认）按路由整体计数；`ip` 按客户端 IP 分别计数。 |

- 超过上限返回 **`503 Service Unavailable`**，带 `Retry-After: 5`。
- 也可用内联 `action.limit_conn` / `action.limit_conn_key` 表达，二者语义相同。

> `limit_conn`（并发）与 `ratelimit`（速率）互补：速率控持续吞吐，并发控慢/卡连接，建议组合使用。

---

## 2. `retry` —— 上游失败重试

对代理到后端的**单次尝试**失败进行自动重试。

> **推荐写法：** 重试是“怎么到达后端”的问题，推荐写在 Service 中：`services.<name>.retry.attempts`。下面的 `retry` 中间件写法已弃用，仍可使用，加载时会提示一次。见 [命名 Service 与配置分层](../03-configuration/services.md)。

```yaml
middlewares:
  api-retry:
    type: retry
    config:
      attempts: "3"     # 最大尝试次数，正整数

routes:
  - name: api
    match: { path_prefix: /api }
    middlewares: [api-retry]
    action:
      type: proxy       # 必须是 proxy
      upstream: ["10.0.0.1:8080", "10.0.0.2:8080"]
```

- **只允许用于 `proxy` action**；配到 `serve`/`respond` 等 action 上会加载失败。
- 它被编译进 Action 的强类型副本，复用 Proxy 成熟的**重试预算、幂等检查、实例选择**逻辑，而不是简单地把整个 handler 重跑一遍。
- `AllowMultiple = false`，且不能与内联 `action.retry` 同时配置。

---

## 3. `circuit_breaker` —— 熔断

后端连续失败到阈值时“跳闸”，短时间内直接拒绝请求，给后端恢复窗口，避免雪崩。

> **推荐写法：** 熔断作用于单个后端实例，推荐写在 Service 中：`services.<name>.circuitbreaker.*`（键名为 `enabled`、`timeout`、`maxrequests`、`tripthreshold`）。下面的 `circuit_breaker` 中间件写法已弃用，仍可使用。

```yaml
middlewares:
  api-breaker:
    type: circuit_breaker
    config:
      enabled: "true"
      trip_threshold: "5"    # 连续失败多少次触发熔断
      timeout: "30"          # 熔断打开后的冷却时长（秒）
      max_requests: "2"      # 半开状态放行的探测请求数
```

| 字段 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `enabled` | bool | `true` | 是否启用。 |
| `trip_threshold` | int | `3` | 连续失败达到该次数则跳闸（Open）。 |
| `timeout` | int（秒） | `60` | Open 状态持续时长，到点后转入 Half-Open 试探。 |
| `max_requests` | int | `1` | Half-Open 状态允许通过的探测请求数；成功则闭合，失败则重新打开。 |

- 同样**只对 `proxy` action 生效**，`AllowMultiple = false`，不能与内联 `action.circuit_breaker` 并存。
- 熔断状态按后端实例维度维护（`ScopeUpstreamInstance`），一个实例跳闸不影响其它健康实例。

> `retry` 与 `circuit_breaker` 常配合：`retry` 吸收偶发抖动，`circuit_breaker` 应对后端持续故障。

---

## 4. `mirror` —— 流量镜像（影子流量）

把已获准的流量异步复制一份到影子后端，用于灰度验证、压测回放、迁移比对。主请求不受影响。

```yaml
middlewares:
  shadow:
    type: mirror
    config:
      target: "shadow.internal:8080"   # host:port 或完整 http(s):// 地址
      percent: "10"                     # 复制比例 0-100，默认 100
```

| 字段 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `target` | string | 是 | 影子后端地址，可为 `host:port`（默认补 `http://`）或完整 URL。 |
| `percent` | int | 否 | 复制比例，`0-100`，默认 `100`。 |

安全与稳定性保证：

- **位于 PostAuth 阶段**：只复制已经通过 WAF 与认证的请求，未授权/被拦截的流量不会进影子服务。
- 复制的请求带 `X-Forwarded-Shadow: true`，并剥离逐跳（hop-by-hop）头。
- 请求体上限 **4 MB**，超过则跳过镜像，避免 OOM。
- 并发有上限，打满时丢弃影子请求以保护主链路。
- **镜像失败绝不影响主请求**（fail-open）。

> 注意：当前实现会连同 `Cookie` / `Authorization` 一起复制给影子后端。若影子环境不可信，请确保它无法用这些凭证做副作用操作。

---

## 5. 阶段与执行位置

```text
... → Security(WAF/IP) → TrafficControl(limit_conn/ratelimit) → Authentication → PostAuth(mirror) → Response → Action/Upstream(retry/circuit_breaker)
```

`retry` 和 `circuit_breaker` 不是普通 HTTP handler，它们编译进 Proxy 的上游治理层；`limit_conn` 是标准 HTTP 中间件；`mirror` 在认证之后才复制。用 MCP 的 `lookup_route` 可以看到它们在 `Effective Pipeline` 中的最终位置。

---

## 延伸阅读
- [Rate Limit 与并发连接限制](./rate-limit.md)
- [Middleware Pipeline 与 Chain](./pipeline.md)
- [反向代理 Action](../04-actions/proxy.md)
