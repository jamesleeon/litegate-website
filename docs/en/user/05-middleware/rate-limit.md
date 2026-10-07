# Rate Limit

`rate_limit` is LiteGate's primary traffic shaper, protecting downstream services against high-concurrency request surges. It is configured **per route, on the route's `action`**.

---

## 1. Core Concepts

LiteGate uses a token-bucket limiter (`golang.org/x/time/rate`):

- **`rate_limit`** (number): the steady-state requests-per-second (QPS) allowed through this route. The burst capacity is set automatically and equals this value.
- **`rate_limit_policy`** (string): `static` (default) or `adaptive`.

> There is no separate site-level rate-limit field. To apply a broad limit across a whole host, set `rate_limit` on a catch-all `/` route.

---

## 2. Static Rate Limiting

Set `rate_limit` directly on the route's `action`:

```yaml
routes:
  - name: heavy-api
    match:
      path_prefix: /api/compute
    action:
      type: proxy
      upstream:
        - "localhost:8080"
      rate_limit: 5          # 5 requests/second for this route
```

Site-wide throttling (apply to everything under the host via a catch-all route):

```yaml
domain: example.com
routes:
  - name: global-limit
    match:
      path_prefix: /
    action:
      type: proxy
      upstream:
        - "localhost:8080"
      rate_limit: 50         # 50 requests/second across this host
```

---

## 3. Adaptive Rate Limiting

Set `rate_limit_policy: adaptive`. The gateway monitors host CPU/memory and dynamically lowers the effective limit under high load. `rate_limit` acts as the hard upper bound.

```yaml
action:
  type: proxy
  upstream:
    - "localhost:8080"
  rate_limit: 100
  rate_limit_policy: adaptive
```

---

## 4. Failure Response

When a request exceeds the configured limit, LiteGate rejects it immediately with HTTP **`429 Too Many Requests`**.

---

## 5. Concurrent Connection Limit (`limit_conn`)

While `rate_limit` caps requests-per-second, `limit_conn` caps the number of **simultaneously in-flight** requests on a route — protecting backends against slow-client exhaustion and connection-pool saturation.

```yaml
action:
  type: proxy
  upstream: ["127.0.0.1:8080"]
  limit_conn: 100            # at most 100 concurrent in-flight requests
  limit_conn_key: "ip"       # "ip" = per client IP; omit/empty = global per route
```

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `limit_conn` | int | `0` (off) | Max concurrent requests |
| `limit_conn_key` | string | global | `ip` limits per client IP; empty limits globally for the route |

- On exceeding the limit, LiteGate returns **`503 Service Unavailable`** with a `Retry-After: 5` header.
- Counters are isolated per `site + route`, so two sites sharing a route name don't interfere.

> `limit_conn` (concurrency) and `rate_limit` (rate) are complementary — combine them: a rate cap for sustained load, a concurrency cap for slow/stuck connections.

---

## 6. Best Practices

1. **Layered throttling**: Put a broad `rate_limit` on a catch-all `/` route as a first line of defense, and tighter limits on expensive endpoints (e.g. `/api/compute`).
2. **Combine with IP rules**: Pair rate limiting with [IP Restriction](./ip-restriction.md) (`allow_ips` / `deny_ips`) to block or isolate bad actors before they consume the route budget.
3. **Pair rate + concurrency**: Use `rate_limit` for throughput and `limit_conn` for in-flight concurrency together for layered backend protection.
