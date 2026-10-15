# Litemesh Service Discovery

Configure a catalog in global config.yaml, then reference the registered service by discovery.name in a site YAML file. Registration does not by itself require automatic tag routing; use the following explicit YAML route or the resource tag model below.

```yaml
service_discovery:
  catalogs:
    - enabled: true
      provider: litemesh
      url: "http://127.0.0.1:8787"
```

Site YAML:

```yaml
site: api.example.com
services:
  orders:
    discovery:
      name: orders
    timeout: 5s
    circuitbreaker:
      enabled: true
      strategy: failure_rate
      window: 30
      minimumrequests: 20
      failureratio: 0.5
/orders:
  service: orders
  rate_limit:
    rate: 100
    key: ip
    algorithm: sliding_window_log
    window: 1m
```

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

The registered service name must match discovery.name. Do not configure the same route in both YAML and automatic tags. Discovery update latency depends on the provider and connection; this guide promises no fixed propagation time or automatic transport encryption. Configure authentication and transport security separately.

[Discovery overview](./overview.md) · [Rate limiting](../05-middleware/rate-limit.md) · [Circuit breaker](../09-advanced/circuit-breaker.md)

## Troubleshooting KV site hot reload

For direct site additions, enable `litemesh.roles.config_watch` and match the namespace and `keys.config_prefix` to the write location. Site keys must be direct children of the prefix ending in `.yaml` or `.yml`; nested directories are not supported.

The watcher receives changes over SSE. Legacy notifications trigger a KV lookup after approximately 300ms; inline values go directly to the loader. Route reload triggers are batched within 500ms of the first trigger. These are batching delays, not end-to-end latency guarantees. Failed event lookups or snapshot reads are retried; networking, parsing, and route construction still affect activation time. Certificate and DNS checks run asynchronously after route publication; certificate issuance for new HTTPS domains may take additional time.

Check logs for `Litemesh KV Config Change Detected`, `Failed to load config from Litemesh KV`, `Litemesh KV event fetch failed, will retry`, `Failed to read published KV snapshot; will retry event`, and `Hot reload failed`. Invalid YAML requires a content correction.

If `_release.json` exists under the site prefix, the published snapshot owns configuration and individual YAML keys no longer participate in runtime loading. Update the snapshot through the Dashboard / release workflow; do not delete it to bypass publication rules. See [configuration release control](../../release_control_guide.md).

### Distinguish KV, route, and DNS delays

- `Litemesh KV Config Change Detected`: the gateway received the site change.
- `Hot reload completed; routes published`: listeners and routes have been updated; `duration` measures this reload.
- `Auto DNS Sync: published record`: the public DNS provider acknowledged the record write.
- `Public DNS sweep completed`: the public DNS sweep ended. Inspect error logs or DDNS status as well; this does not mean all writes succeeded.

Config watchers reconcile approximately every 30 seconds even while SSE remains connected, recovering missed additions, updates, and deletions. Network and loading time are additional. Failed public DDNS syncs can retry on later reloads or the periodic 5-minute check. Internal DNS heartbeats default to 30 seconds, with a default record TTL of 30 seconds. Public provider TTLs vary; Aliyun and Tencent A/AAAA writes use 600 seconds.

Bypass resolution using the gateway's actual IP and check for the expected site response:

```bash
curl --noproxy "*" --resolve app.example.com:80:192.0.2.10 http://app.example.com/
curl --noproxy "*" --resolve app.example.com:443:192.0.2.10 https://app.example.com/
```

Replace the domain and IP. HTTPS retains certificate validation and may fail while issuance is pending. A generic redirect or default page alone does not prove the intended route works. If the pinned-IP request returns the expected content but ordinary domain access fails, inspect resolution, provider records, and proxies/CDNs. Earlier NXDOMAIN responses for a new name may also be cached; see [RFC 2308](https://www.rfc-editor.org/rfc/rfc2308). Restarting the gateway does not clear external resolver caches.
