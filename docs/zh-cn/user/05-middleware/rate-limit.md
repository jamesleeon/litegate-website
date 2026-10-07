# Rate Limit (流量限速)

`rate_limit` 是 LiteGate 保护后端免受突发流量冲击的核心手段。它既可以配置在路由的 `action` 上，也可以通过命名 `ratelimit` middleware 在多条路由间共享额度。

---

## 1. 核心概念

LiteGate 使用令牌桶限流器(`golang.org/x/time/rate`):

- **`rate_limit`**(数字):该路由允许通过的每秒请求数(QPS)。突发容量自动设置,等于该值。
- **`rate_limit_policy`**(字符串):`static`(默认)或 `adaptive`。

两种写法的桶作用域不同：

- `action.rate_limit` 使用 `站点 + 路由名` 作为桶 key，只限制当前路由。
- 命名 `ratelimit` middleware 使用 `站点 + middleware 名` 作为桶 key；同一站点内引用它的路由共享一个总额度。

二者可以有意叠加，实现“共享总额度 + 路由局部额度”；请求必须同时通过两层限制。不要在同一路由的 `middlewares` 中重复引用同一个名称，加载器会将其视为配置错误。

---

## 2. 静态限速

直接在路由的 `action` 上设置 `rate_limit`:

```yaml
routes:
  - name: heavy-api
    match:
      path_prefix: /api/compute
    action:
      type: proxy
      upstream:
        - "localhost:8080"
      rate_limit: 5          # 该路由每秒 5 个请求
```

多路由共享总量限速（通过命名 middleware）：

```yaml
middlewares:
  site-total-limit:
    type: ratelimit
    config:
      qps: "50"

routes:
  - name: api
    match:
      path_prefix: /api
    action:
      type: proxy
      upstream:
        - "localhost:8080"
    middlewares: [site-total-limit]

  - name: assets
    match:
      path_prefix: /assets
    action:
      type: proxy
      upstream:
        - "localhost:8080"
    middlewares: [site-total-limit] # 与 /api 共同使用 50 QPS
```

---

## 3. 自适应限速 (Adaptive)

设置 `rate_limit_policy: adaptive`。网关会监控主机 CPU/内存,高负载时动态下调实际限流阈值,`rate_limit` 作为硬上限。

```yaml
action:
  type: proxy
  upstream:
    - "localhost:8080"
  rate_limit: 100
  rate_limit_policy: adaptive
```

---

## 4. 触发限流后的响应

请求超过限制时,LiteGate 立即返回 HTTP **`429 Too Many Requests`**。

---

## 5. 并发连接限制 (`limit_conn`)

`rate_limit` 限的是每秒请求数,`limit_conn` 限的是路由上**同时在处理**的请求数——防止慢客户端拖垮后端、连接池被打满。

```yaml
action:
  type: proxy
  upstream: ["127.0.0.1:8080"]
  limit_conn: 100            # 最多 100 个并发在途请求
  limit_conn_key: "ip"       # "ip" = 按客户端 IP;留空 = 按路由全局
```

| 字段 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `limit_conn` | int | `0`(关闭) | 最大并发请求数 |
| `limit_conn_key` | string | 全局 | `ip` 按客户端 IP 限制;留空按路由全局限制 |

- 超过上限时,LiteGate 返回 **`503 Service Unavailable`**,并带 `Retry-After: 5` 响应头。
- 计数按 `站点 + 路由` 隔离,两个站点用同名路由互不干扰。

> `limit_conn`(并发)与 `rate_limit`(速率)互补,建议组合使用:用速率限制控持续吞吐,用并发限制控慢/卡连接。

---

## 6. 最佳实践

1. **分层限速**:在 catch-all 的 `/` 路由上设一个较大的 `rate_limit` 作为第一道防线,在 `/api/compute` 等高成本接口上设更严的限制。
2. **结合 IP 规则**:配合 [IP 限制](./ip-restriction.md)(`allow_ips` / `deny_ips`),在恶意来源消耗路由配额前就拦掉。
3. **速率 + 并发并用**:`rate_limit` 控吞吐、`limit_conn` 控在途并发,两者叠加形成对后端的分层保护。
