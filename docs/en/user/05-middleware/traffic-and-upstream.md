# Traffic Control and Upstream Governance Middleware

This group protects and governs requests between arrival and the backend, across these phases:

- **TrafficControl** (`limit_conn`): concurrency/rate protection at the plain HTTP layer.
- **Upstream** (`retry`, `circuit_breaker`): governance that must understand backend instances and individual attempts; compiled into the proxy and **effective only on the `proxy` action**.
- **PostAuth** (`mirror`): copies only traffic that has already been authenticated.

> Rate limiting (`ratelimit`) has its own page: [Rate limiting and concurrent connection limits](./rate-limit.md).

---

## 1. `limit_conn` — concurrent request limit

Limits how many requests a route is **processing at the same time**, so slow clients can't drag down the backend or exhaust connection pools.

```yaml
middlewares:
  concurrency-guard:
    type: limit_conn
    config:
      limit: "100"      # maximum in-flight requests, a positive integer
      key: "ip"         # global (default) = per route; ip = per client IP
```

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `limit` | int | Yes | Maximum concurrent requests; must be a positive integer. |
| `key` | string | No | `global` (default) counts per route; `ip` counts per client IP. |

- Over the limit returns **`503 Service Unavailable`** with `Retry-After: 5`.
- `limit_conn` can also be written inline on a route with the same meaning.

> `limit_conn` (concurrency) and `ratelimit` (rate) complement each other: rate limits control sustained throughput, concurrency limits control slow or stuck connections. Use both.

---

## 2. `retry` — retry failed upstream attempts

Automatically retries a failed **single attempt** to the backend.

> **Recommended form:** retrying is about "how to reach the backend", so write it in the Service: `services.<name>.retry.attempts`. The `retry` middleware below is deprecated; it still works and logs a notice once at load time. See [Named services and configuration layers](../03-configuration/services.md).

```yaml
site: api.example.com
middlewares:
  api-retry:
    type: retry
    config:
      attempts: "3"     # maximum attempts, a positive integer

/api:
  use: [api-retry]
  proxy: 10.0.0.1:8080, 10.0.0.2:8080   # must be proxy
```

- **Allowed only on the `proxy` action**; on `serve`/`respond` and other actions loading fails.
- It compiles into the Action's typed copy and reuses the proxy's **retry budget, idempotency checks and instance selection**, rather than rerunning the whole handler.
- `AllowMultiple = false`, and it cannot be stacked with inline `retry` or the Service's `retry`.
- Idempotent methods (GET, HEAD, PUT, DELETE, OPTIONS, TRACE) may be retried after an error; non-idempotent methods such as POST are retried only when it is certain the request was never delivered or processed (for example, the connection was never established, or gRPC `UNAVAILABLE`).
- Retries use exponential backoff, and each route's retries are budgeted (about 20% of requests in a rolling 1-second window, at least 10), so an upstream outage isn't amplified.

---

## 3. `circuit_breaker` — circuit breaking

When a backend keeps failing up to a threshold, the breaker "trips" and rejects requests directly for a while, giving the backend time to recover and preventing cascades.

> **Recommended form:** breakers act on individual backend instances, so write them in the Service: `services.<name>.circuitbreaker.*` (keys `enabled`, `timeout`, `maxrequests`, `tripthreshold`). The `circuit_breaker` middleware below is deprecated but still works.

```yaml
middlewares:
  api-breaker:
    type: circuit_breaker
    config:
      enabled: "true"
      trip_threshold: "5"    # consecutive failures that trip the breaker
      timeout: "30"          # cool-down after opening (seconds)
      max_requests: "2"      # probe requests allowed while half-open
```

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `enabled` | bool | `true` | Whether it is enabled. |
| `trip_threshold` | int | `3` | Consecutive failures that open the breaker. |
| `timeout` | int (seconds) | `60` | How long it stays Open before moving to Half-Open. |
| `max_requests` | int | `1` | Probe requests allowed in Half-Open; success closes it, failure opens it again. |

- Also **effective only on the `proxy` action**, `AllowMultiple = false`, and cannot coexist with inline or Service breaker configuration.
- The sliding-window failure-rate strategy (`strategy`, `window_seconds`, `minimum_requests`, `failure_ratio`) is also supported; see [Circuit breaker](../09-advanced/circuit-breaker.md).
- A local breaker rejection happens before the request is sent, so another instance can be chosen without backoff, and it doesn't count as an upstream passive health check failure.
- Breaker state is kept per backend instance (`ScopeUpstreamInstance`); one tripped instance doesn't affect other healthy instances.

> `retry` and `circuit_breaker` work well together: `retry` absorbs occasional glitches, `circuit_breaker` handles sustained backend failures.

---

## 4. `mirror` — traffic mirroring (shadow traffic)

Copies permitted traffic asynchronously to a shadow backend for canary verification, load replay or migration comparisons. The main request is unaffected.

```yaml
middlewares:
  shadow:
    type: mirror
    config:
      target: "shadow.internal:8080"   # host:port or a full http(s):// address
      percent: "10"                     # copy ratio 0-100, default 100
```

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `target` | string | Yes | Shadow backend: `host:port` (`http://` is added) or a full URL. |
| `percent` | int | No | Copy ratio `0-100`, default `100`. |

Safety and stability guarantees:

- **Runs in PostAuth**: only requests that passed WAF and authentication are copied; unauthorized or blocked traffic never reaches the shadow service.
- Copied requests carry `X-Forwarded-Shadow: true`, with hop-by-hop headers removed.
- Request bodies over **4 MB** are not mirrored, avoiding OOM.
- Concurrency is capped; when full, shadow requests are dropped to protect the main path.
- **A mirroring failure never affects the main request** (fail-open).

> Note: the current implementation copies `Cookie` / `Authorization` to the shadow backend as well. If the shadow environment isn't trusted, make sure it cannot perform side effects with those credentials.

---

## 5. Phases and placement

```text
... → Security(WAF/IP) → TrafficControl(limit_conn/ratelimit) → Authentication → PostAuth(mirror) → Response → Action/Upstream(retry/circuit_breaker)
```

`retry` and `circuit_breaker` are not ordinary HTTP handlers; they compile into the proxy's upstream governance layer. `limit_conn` is a standard HTTP middleware, and `mirror` copies only after authentication. MCP's `lookup_route` shows their final positions in the `Effective Pipeline`.

---

## Further reading

- [Named services and configuration layers](../03-configuration/services.md)
- [Circuit breaker](../09-advanced/circuit-breaker.md)
- [Rate limiting and concurrent connection limits](./rate-limit.md)
- [Middleware pipeline and chain](./pipeline.md)
- [Reverse proxy action](../04-actions/proxy.md)
