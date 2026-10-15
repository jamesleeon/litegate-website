<!-- GENERATED FILE — DO NOT EDIT.
     Source: internal/configdocs/docs/en/circuit-breaker.md (package internal/configdocs)
     Regenerate: go generate ./internal/configdocs/...
     Edit the source instead; a drift test fails if this copy is edited directly. -->

# Circuit breaking (V2 configuration)

Circuit breaking is an upstream Service policy. YAML `services` defines local upstream configurations and does not require a service registry: use `servers` for static addresses or `discovery` for registered services. Both support the same breaker policies. Use V2 site and path routes:

## Consecutive failures (compatible default)

```yaml
site: api.example.com
services:
  payment:
    to: ["http://127.0.0.1:8080", "http://127.0.0.1:8081"]
    circuitbreaker:
      enabled: true
      timeout: 60
      maxrequests: 1
      tripthreshold: 3
/api/payment:
  service: payment
  rate_limit: 100
```

Service keys use `circuitbreaker`, `maxrequests` and `tripthreshold`, without underscores. For service discovery, replace `servers` with `discovery: {name: payment}`; do not configure both. See [Services](../03-configuration/services.md).

| Parameter | Default | Meaning |
|---|---|---|
| `enabled` | `false` | Enable the breaker |
| `strategy` | `consecutive` | Consecutive failures, or `failure_rate` for a sliding window |
| `window` | `30` | Window seconds, range 1–3600; failure-rate mode only |
| `minimumrequests` | `20` | Minimum effective window calls; failure-rate mode only |
| `failureratio` | `0.5` | Failure fraction threshold in (0,1]; failure-rate mode only |
| `slowthresholdms` | `0` | Slow-call threshold in milliseconds, range 0–3600000; 0 disables it. Calls strictly above it count as failures in either strategy |
| `tripthreshold` | `3` | Consecutive failures required to open |
| `timeout` | `60` | Seconds before probing recovery; not the request timeout |
| `maxrequests` | `1` | Half-open probe allowance and consecutive successes needed to close |

Omitted or zero numeric parameters use defaults. State is local to each gateway process, not shared through Redis. The cache uses upstream address and breaker settings, with separate ports and custom DNS views isolated. Routes with identical keys share state. At most 2048 entries are cached. Eviction only removes closed entries with no effective failure history or in-flight requests. If all entries are protected, requests for new keys return 503 until a safe slot becomes available; existing circuits retain their state.

## Sliding-window failure rate

Select `failure_rate` explicitly for either static or registered services. Each instance tracks completed effective calls over the recent window. It opens when both the minimum sample size and the failure fraction threshold are reached. Successes remain in the denominator without clearing earlier failures.

### Static upstreams: YAML without a registry

Put this configuration in a site YAML file. `payment` is a locally defined upstream name referenced by the route through `service: payment`.

```yaml
site: api.example.com
services:
  payment:
    to:
      - "http://127.0.0.1:8080"
      - "http://127.0.0.1:8081"
    timeout: 5s
    circuitbreaker:
      enabled: true
      strategy: failure_rate
      window: 30
      minimumrequests: 20
      failureratio: 0.5
      timeout: 30
      maxrequests: 1
/api/payment:
  service: payment
```

The two addresses have separate statistics: opening one circuit does not open the other. For one backend, keep one `servers` entry. For failover between addresses, optionally add `retry: {attempts: 1}`; see the failover section below.

`services.payment.timeout: 5s` bounds the request; `circuitbreaker.window: 30` is the statistical window in seconds; `circuitbreaker.timeout: 30` is the open-state wait before probing. The latter two are integers, not duration strings such as `30s`. Each backend must have at least 20 effective calls in its window and a failure fraction of at least 50% to trip. Low traffic below the sample minimum does not open the circuit.

### Registry upstreams: YAML discovery reference

Replace `servers` in the same configuration with this block, keeping the breaker settings:

```yaml
discovery:
  name: payment
```

`discovery` belongs under `services.payment` and is mutually exclusive with `servers`. `discovery.name` names the registered service and may differ from the local upstream name.

### Registry upstreams: registration tags

The same policy can be declared through registration tags:

```text
litegate.http.services.payment.circuitbreaker.enabled=true
litegate.http.services.payment.circuitbreaker.strategy=failure_rate
litegate.http.services.payment.circuitbreaker.window=30
litegate.http.services.payment.circuitbreaker.minimumrequests=20
litegate.http.services.payment.circuitbreaker.failureratio=0.5
```

This example opens at a failure fraction of at least 50% with at least 20 effective calls. Client cancellation, client-set `grpc-timeout` expiry and breaker rejections are excluded from both numerator and denominator. Gateway-owned timeouts, network errors and configured failure status codes count as failures. Each actual retry counts against its target instance, using completion time. Each gateway process has independent statistics.

The window uses 64 fixed time slices plus one boundary slice, bounding memory independently of QPS. A partially expired slice remains until its newest sample expires, retaining old samples for less than `window / 64` additional seconds (about 0.47 seconds for a 30-second window), without dropping still-recent samples early. The next completion or monitoring snapshot expires idle samples.

Choose either `failure_rate` or `consecutive`. `tripthreshold` is inactive in failure-rate mode. Omitted `strategy` preserves the legacy consecutive-failure policy; window parameters require `strategy: failure_rate`. Half-open recovery still uses limited probes and reopens on any failure. Closing after recovery clears the old window and starts fresh.

Deregistering an instance is handled by service discovery and is not a breaker failure sample. Breaking isolates instances that remain discoverable but actually fail calls.

Legacy action / middleware fields are `strategy`, `window_seconds`, `minimum_requests` and `failure_ratio`.

## States and outcomes

- **Closed:** forward requests; the selected policy opens on consecutive failures or window failure rate; success resets the streak only for the consecutive policy.
- **Open:** reject this instance without forwarding; after `timeout`, enter Half-Open.
- **Half-Open:** accept limited probes and reject excess requests; any failure opens the breaker again; enough consecutive successes close it.

Network errors and HTTP 5xx responses count as failures by default. A failure response is still forwarded: the response that trips the breaker retains the upstream status, such as 500. Later requests encounter the fast rejection.

Client cancellation and client-set `grpc-timeout` expiry do not count as upstream failures. These are neutral outcomes: neither success nor failure is recorded, failure streaks remain intact, and half-open probe slots are released without advancing recovery. Gateway-owned timeouts still count as failures. WebSocket and other Upgrade requests apply the same breaker to dialing and the HTTP handshake; established tunnel traffic is not counted. This breaker observes HTTP RoundTrip results, not business errors in HTTP 200 bodies, response-body read errors or gRPC trailer status.

## Responses and failover

A final breaker fast rejection returns **503** for ordinary HTTP. Other upstream errors generally return 502; timeouts return 504. Native gRPC and gRPC-Web use protocol error responses (`grpc-status: 14` for breaker rejection).

Retries can try another instance, so one open instance does not necessarily cause a route-wide 503:

```yaml
site: api.example.com
services:
  payment:
    to: ["http://127.0.0.1:8080", "http://127.0.0.1:8081"]
    retry: {attempts: 1}
    circuitbreaker: {enabled: true, timeout: 30, maxrequests: 1, tripthreshold: 3}
/api/payment:
  service: payment
```

Breaker rejections did not send a request upstream and allow failover without backoff. Endpoint selection and request replay rules still apply. Service `healthcheck` complements circuit breaking.

## Custom failure codes: compatibility block

The Service schema exposes the policy parameters above. Custom code lists require an explicit action compatibility block inside a V2 route:

```yaml
site: api.example.com
/api/payment:
  action:
    type: proxy
    upstream: ["127.0.0.1:8080"]
    circuit_breaker:
      enabled: true
      trip_threshold: 3
      timeout: 60
      max_requests: 1
      failure_status_codes: [500, 502, 504]
      ignore_status_codes: [503]
```

Ignored codes take precedence. With a failure list, only listed HTTP codes count; network failures still count. Do not put these legacy names inside Service `circuitbreaker` or combine Service breaking with named breaker middleware on the same route. Prefer Services for new configurations.

Dashboard and Prometheus expose breaker state and trips. Distinguish rate-limit 429, concurrency-limit 503, breaker 503 and upstream 503. See [rate limiting](../05-middleware/rate-limit.md).

Monitoring snapshots also expose `strategy`, `window_seconds`, `minimum_requests`, `failure_ratio`, `window_requests`, `window_failures` and `window_failure_ratio`. Window counters reset on state changes.

## Monitoring and troubleshooting

The dashboard shows upstream breaker state and failure counts. Prometheus exposes `litegate_circuit_breaker_state` (0 closed, 1 half-open, 2 open) and `litegate_circuit_breaker_trips_total`. Distinguish rate-limit 429, concurrency-limit 503, breaker 503 and upstream 503 when investigating.

Snapshots include `strategy`, `window_seconds`, `minimum_requests`, `failure_ratio`, `window_requests`, `window_failures` and `window_failure_ratio`. Window samples reset when the breaker changes state.


## Latency-based circuit breaking

Service `circuitbreaker.slowthresholdms` sets a slow-call threshold in milliseconds (default `0`, disabled; maximum `3600000`). Calls strictly above this threshold count as breaker failures even when HTTP 200 is returned; the original response is preserved. Network errors and configured failure statuses still count, with each call counted only once. With `failure_rate`, the threshold applies to the combined fraction of failed or slow calls:

```yaml
services:
  payment:
    servers: ["http://10.0.0.11:8080", "http://10.0.0.12:8080"]
    retry: {attempts: 1}
    circuitbreaker:
      enabled: true
      strategy: failure_rate
      window: 30
      minimumrequests: 20
      failureratio: 0.5
      slowthresholdms: 500
      timeout: 30
      maxrequests: 1
```

Each instance needs 20 completed effective calls in the window. When at least 50% fail or exceed 500ms, its circuit opens. After 30 seconds a probe is allowed; recovery requires successful probes within the latency threshold. A slow probe reopens the circuit. Client cancellation and client `grpc-timeout` remain neutral.

Latency covers HTTP RoundTrip through response headers, including connection establishment and waiting for headers, excluding body reads and established stream lifetimes. This policy does not interrupt a slow request; configure Service `timeout` to limit individual request duration. With `consecutive`, slow calls count toward the consecutive failure threshold.

Registry tags use `circuitbreaker.slowthresholdms`; legacy Action / middleware uses `slow_threshold_ms`. Snapshots expose `slow_threshold_ms`; existing failure counters include slow calls. An open circuit rejects before contacting the upstream. Load balancing may still select that instance; retries can try another instance, and final breaker rejection returns 503.
