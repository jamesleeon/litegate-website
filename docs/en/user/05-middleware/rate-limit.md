<!-- GENERATED FILE — DO NOT EDIT.
     Source: internal/configdocs/docs/en/rate-limit.md (package internal/configdocs)
     Regenerate: go generate ./internal/configdocs/...
     Edit the source instead; a drift test fails if this copy is edited directly. -->

# Rate limiting (V2 configuration)

Rate limiting controls request throughput to protect upstreams from overload. LiteGate supports four rate limiting algorithms:
- **Token Bucket (`token_bucket`, default)**: Allows brief burst capacity while sustaining a steady long-term average rate. Recommended for core API traffic shaping and avalanche prevention. Supports arbitrary `<= 1s` and `> 1s` windows, replenishing tokens uniformly at `rate / window`.
- **Sliding Window Counter (`sliding_window`)**: Approximates rolling windows with linear weighting in $O(1)$ memory. Smooths transitions under normal traffic, but because it is an approximation, worst-case bursts (clustered at window edges) across an arbitrary rolling window can still approach up to 200%. Recommended for high-concurrency API traffic shaping and general abuse mitigation.
- **Exact Sliding Window Log (`sliding_window_log`)**: Records precise request timestamps, strictly guaranteeing that total requests in any arbitrary rolling window never exceed the configured limit. Ideal for billing/metering and high-security SaaS API quotas (backed by Redis ZSET).
- **Fixed Window (`fixed_window`)**: Resets counters within discrete time windows with minimal overhead. Suitable for coarse-grained frequency limits.

## Shared route budgets and client IP budgets

Configure rate limiting on V2 path routes:

```yaml
site: api.example.com
/api:
  proxy: localhost:8080
  rate_limit: 100
/upload:
  proxy: localhost:8080
  rate_limit: {rate: 10, key: ip}
/quota:
  proxy: localhost:8080
  rate_limit: {rate: 60, key: ip, algorithm: sliding_window, window: 1m}
```

Numeric limits share a budget within a site and route, equivalent to `{rate: 100, key: route}`. `key: ip` allocates one limiter per client IP. Only `route` and `ip` are supported; header and tenant expressions are not supported. Forwarded addresses honor global `trusted_proxies`. At the process-wide 100000 client-bucket cap, new clients share the route fallback bucket.

| Field | Default | Description |
|---|---|---|
| `rate_limit` | `0` (disabled) | Limit number, or `{rate: number, key: route/ip, algorithm: ..., window: ...}` |
| `rate_limit_key` | `route` | Key scope: `route` or `ip` |
| `rate_limit_algorithm` | `token_bucket` | Limiter algorithm: `token_bucket`, `sliding_window`, `sliding_window_log`, or `fixed_window` |
| `rate_limit_window` | `1s` | Window duration (e.g. `500ms`, `1s`, `10s`, `1m`, must be integer milliseconds, min 1ms). Supported by all algorithms |
| `rate_limit_policy` | `static` | `static` or `adaptive` (`adaptive` only supports `token_bucket` and the default 1s window) |

Under the token bucket algorithm, regardless of whether `window` is greater than, equal to, or less than 1s (e.g. `{rate: 10, window: 500ms}` or `{rate: 100, window: 1m}`), the burst capacity is automatically set to `ceil(rate)`, and tokens refill at `rate / window.Seconds()` (e.g. 10 tokens per 500ms refilled at 20 QPS; 100 tokens per minute refilled at ~1.67 QPS). This permits initial bursts up to `rate` while strictly bounding the long-term inflow rate. When `window` is omitted, standard 1-second QPS mode applies (fractional rates like `0.5` average one request every two seconds). Sliding and fixed windows enforce the limit per `window` duration. Rejected requests receive **429 Too Many Requests**. Numeric `0` disables limiting.

Per-IP limits use the client address resolved at ingress, never the raw request header. XFF is honored only when the direct peer belongs to `real_ip.trusted_proxies` (or a Unix ingress protected by filesystem permissions). All same-name fields form one chain, scanned right to left for the first untrusted IP; IPv4/IPv6 representations are canonicalized. Invalid or empty boundary hops fall back to the direct peer. The front proxy must overwrite incoming XFF or append the client IP it actually observes on the right of the complete chain. A gateway cannot authenticate client-supplied addresses blindly passed through by its trusted proxy. Do not trust public client networks, `0.0.0.0/0` or `::/0`.

## Algorithm Selection Guide

| Algorithm Key | Name | Characteristics & Advantages | Typical Use Cases |
|---|---|---|---|
| `token_bucket` | Token Bucket (default) | Allows configurable bursts; smooth token replenishment; long-term stable QPS | Gateway general traffic shaping, high-concurrency API protection |
| `sliding_window` | Sliding Window Counter | Weighted linear estimation in $O(1)$ memory; worst-case edge bursts can still approach ~200% | General minute/hour quotas, high-concurrency abuse mitigation |
| `sliding_window_log` | Exact Sliding Window Log | Strict timestamp logging; strictly guarantees no excess requests in any rolling window | Billing/metering, strict SaaS tier quotas, financial APIs |
| `fixed_window` | Fixed Window | Discrete time slicing; instant counter reset; lightweight execution | SMS/verification codes, coarse rate limits |

```yaml
site: api.example.com
/sms/send:
  proxy: localhost:8080
  rate_limit: {rate: 5, key: ip, algorithm: fixed_window, window: 1m}
/openapi:
  proxy: localhost:8080
  rate_limit: {rate: 1000, key: ip, algorithm: sliding_window, window: 1h}
/billing:
  proxy: localhost:8080
  rate_limit: {rate: 100, key: ip, algorithm: sliding_window_log, window: 1m}
```

## Shared middleware budget

```yaml
site: api.example.com
middlewares:
  total-budget:
    type: ratelimit
    config: {qps: "50", key: route, algorithm: sliding_window, window: 1s}
/api:
  use: total-budget
  proxy: localhost:8080
  rate_limit: 10
/assets:
  use: total-budget
  proxy: localhost:8080
```

Routes referencing the same middleware within a site share its 50 QPS budget; `/api` also has its own 10 QPS budget. Middleware and route buckets remain independent even when names match. Use `config.key: ip` for a shared budget per client. Named middleware accepts `qps`, `key`, `algorithm`, and `window`. Do not repeat a middleware reference on one route.

A catch-all route does not wrap other matching routes. Apply a shared middleware to every route that needs a site-wide budget.

## Adaptive limits and reloads

```yaml
site: api.example.com
/api/compute:
  proxy: localhost:8080
  rate_limit: 100
  rate_limit_policy: adaptive
```

`rate_limit_policy` defaults to `static`. Adaptive limiting uses host **CPU**, not memory. Every two seconds, CPU above 80% reduces the effective rate by 20%; CPU below 50% increases it by 10%. The floor is `min(maximum, max(1, maximum * 0.1))`. Reloading updates the ceiling, floor and burst; a lower ceiling applies immediately, while a higher ceiling retains load throttling and recovers gradually. Adaptive limits are local, only support `token_bucket` with the default 1s window, do not use Redis, and cannot use `key: ip`.

## Distributed limits and fallback

Enable Redis in the gateway global configuration, separate from the site YAML:

```yaml
redis:
  enabled: true
  mode: standalone
  address: localhost:6379
  db: 0
```

Static route and middleware limits automatically use Redis, including IP buckets. All four algorithms support Redis distributed mode:
- **`token_bucket`**: Millisecond-precision atomic token refills (`tokens`, `last_update`), with dynamic TTL extending according to refill duration.
- **`sliding_window`**: Weighted sliding window counter evaluation in $O(1)$ memory (`curr`, `prev`, `win`).
- **`sliding_window_log`**: Redis ZSET-backed millisecond sliding window log for exact rolling quota enforcement.
- **`fixed_window`**: Atomic `INCR` with window millisecond `PEXPIRE`. The Lua script passes the complete key directly via `KEYS[1]`, natively compatible with Redis Cluster slot routing.

Redis operations have a 200 ms budget and a shared concurrency cap of 64 per client. Three consecutive failures open a dependency circuit for five seconds; one request probes recovery. Errors, an open circuit or saturation fall back to a local limiter matching the configured algorithm on each gateway node.

**Fallback does not preserve a strict cluster-wide quota**: Multiple nodes each enforce local limits. Local fallback limiters do not account for successful Redis requests. This Redis circuit is separate from upstream Service circuit breaking.

## State Retention Lifecycle & Redis Time Synchronization

1. **State Retention (TTL)**: Both in-memory limiter caches and Redis keys dynamically calculate idle retention considering both window duration and token replenishment time (`burst / fill_rate`), setting TTL to `max(600s, max(window, fill_time) * 2)`. For fractional rates with long windows (e.g. `rate: 0.1, window: 1h`, which takes 10 hours to refill), the state is preserved for 20 hours (72000s), preventing premature eviction and renewal.
2. **Unified Redis Time Source & Cluster Routing**:
   - Distributed Lua scripts directly query `redis.call('TIME')` on the Redis server, eliminating node-to-node clock skew discrepancies.
   - Fixed window passes full key via `KEYS[1]`, ensuring full compatibility with Redis Cluster slot routing.
3. **Algorithm Switching & Concurrent Reload Safety**: Redis keys use isolated namespaces (`gate:ratelimit:<algo>:<window_ms>ms:<key>`). Key-level singleflight serialization prevents concurrent reloads from spawning duplicate limiter instances.

## Concurrent requests

```yaml
site: api.example.com
/upload:
  proxy: localhost:8080
  rate_limit: {rate: 10, key: ip}
  limit_conn: 20
  limit_conn_key: ip
```

`limit_conn` controls in-flight requests; rejection returns **503** with `Retry-After: 5`. See [circuit breaking](../09-advanced/circuit-breaker.md) for upstream failure protection.


## Traffic protection on registered services

Register this identical resource tag set on every orders instance. Rate limiting admits at most 100 requests per client IP in a one-minute sliding log window. Circuit breaking tracks completed upstream outcomes independently per backend address over 30 seconds, opening at 20 samples and a failure ratio of 0.5. Rate-limit window accepts a duration (1m) or integer milliseconds; breaker window is integer seconds (30). Deregistration removes an instance after the discovery update reaches the gateway; requests during that propagation interval can still fail. Backend failures remain breaker samples. Do not mix named resources with shortcut tags.

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

For MCP generation, read `get_config_guide(topic="traffic")`, then run `preview_service_tags`: errors must be fixed; review warnings before applying. For YAML, run `validate_site_config` before `save_site_config`.


## Large transfers and request body protection

`rate_limit` limits request counts; `bandwidth` limits upload and download bytes per second. Proxy requests and file responses remain streaming.

Global configuration (`config.yaml`):

```yaml
http:
  max_request_body_size: 67108864 # Default 64MiB; 0 means unlimited
  body_buffer_budget: 67108864   # Default 64MiB; 0 selects the default budget
  bandwidth:
    total_upload: 20971520       # All routed traffic in this process: 20MiB/s
    total_download: 52428800     # All routed traffic in this process: 50MiB/s
```

Site configuration:

```yaml
site: files.example.com
max_request_body_size: 1048576
bandwidth:
  total_download: 20971520

/upload:
  max_request_body_size: 4294967296 # 4GiB; explicit 0 means unlimited
  bandwidth:
    key: ip
    upload: 2097152
    download: 4194304
    total_upload: 10485760
  limit_conn: 4
  limit_conn_key: ip
  proxy: http://127.0.0.1:8080

/:
  serve: ./public
```

Rates are integer **bytes/second**; 0 disables that rate. `key` defaults to `ip`, using LiteGate's trusted client IP resolution rather than accepting arbitrary forwarding headers. `global` shares `upload` / `download` across all requests in that scope. Concurrent connections from one IP share their quota, including users behind the same NAT. Upload and download are independent.

Global, site and route quotas apply together. Site quotas span every route in that site; route quotas span every connection to that route. Token buckets allow an initial burst of at most 32KiB, or one second of quota for lower rates. Waiting responds to cancellation and deadlines. Adjust proxy timeouts for the intended file size and rate, and combine bandwidth quotas with `limit_conn` to bound long-lived requests.

Body size uses the explicit route value, then a positive site value, then the global value. Site 0 inherits the global setting; explicit route 0 allows unlimited size. A declared length exceeding the limit returns 413 before reading the body. Chunked and unknown-length bodies are limited while reading. A rejected streaming upload may already have sent a prefix to the backend; the backend must clean up failed uploads and commit files atomically. A limit error after the response has been committed cannot change its earlier status.

Retry buffering only handles known lengths below 1MiB. Larger and unknown-length bodies stream without retries or proxy mirroring. `disable_chunked` still buffers at most 2MiB and is unsuitable for large uploads. The named mirror middleware has a separate 4MiB body limit.

`body_buffer_budget` is a process-wide shared budget for proxy replay, `disable_chunked` and named mirror buffers. Reservations account for three times the read limit to cover buffer growth and remain held until asynchronous readers and mirrors finish. Budget exhaustion skips optional retry buffering or mirroring; mandatory `disable_chunked` buffering returns 503. This is not a process RSS limit: connections, IDS, response caches and plugins have their own overhead.

Bandwidth limits cover regular HTTP uploads, proxy responses, static files and cache hits. Download accounting counts compressed HTTP body bytes, excluding protocol and TLS overhead. WebSocket, CONNECT and other hijacked tunnel traffic are outside this feature. Quotas are local to one instance.

Handler rebuilds reuse limiter state. Idle client keys expire after five minutes. The process retains at most 10,000 client keys and 4,096 scopes; capacity exhaustion returns 503 with `Retry-After: 60`.

The new default 64MiB body limit changes unconfigured upload endpoints. Configure a suitable route override before upgrading those endpoints.
