# Proxy response cache

Supports `local` and `redis`; local is the default. Multiple nodes must explicitly select Redis and share the same deployment, namespace, and route configuration. Enabling `cache.redis` alone does not switch the proxy cache backend.

## Route configuration

```yaml
site: example.com
/api/list:
  name: cached-list
  proxy: 127.0.0.1:8080
  cache:
    ttl: 30s
```

`cache: true` uses a 10-second TTL. The mapping accepts enabled, ttl, and key. TTL accepts positive integer seconds or whole-second durations. Underlying action fields are proxy_cache, proxy_cache_ttl, and proxy_cache_key.

X-LiteGate-Cache reports MISS, HIT, or STALE; bypassed responses may omit it. Hits update Age. Default keys include Host, route, and complete URI including query parameters. GET and HEAD share a key. Storage additionally isolates namespace, Host, route, and route configuration version, even with custom keys.

## Gateway configuration

Place these settings in gateway config.yaml, rather than site YAML:

```yaml
cache:
  redis:
    enabled: true
    address: 127.0.0.1:6379
  proxy_cache:
    backend: redis                  # local | redis; default local
    namespace: production          # default default; separate environments
    max_object_bytes: 262144        # default 256KB
    redis_timeout: 200ms            # timeout per Redis operation
    stale_while_revalidate: 0s      # Redis defaults to no stale responses
  proxy_cache_max_entries: 10000    # local LRU entry limit
```

Connections reuse enabled cache.redis, falling back to global redis. Selecting Redis without an enabled connection is invalid. Existing Redis Cluster configuration is supported; scripts operate on a single key. Redis mode reads shared storage directly without an L1 copy.

Local bodies up to 64KB use memory; larger bodies use an exclusively owned process directory. Default budgets are 128MB memory and 10GB disk. Eviction and maintenance every 30 seconds reclaim expired entries and indexes; normal shutdown reclaims cached bodies. Local cache does not survive restart. Abnormally terminated processes can leave directories requiring operating-system temporary-directory maintenance or operator cleanup; other processes do not remove them at startup.

Redis atomically stores bodies, metadata, and variants in response buckets. Each base key permits at most 100 variants; writes reclaim expired variants. proxy_cache_max_entries does not cap Redis storage: configure Redis capacity and eviction separately. Idle scope-generation metadata expires after one day; unique replacement tokens prevent old buckets becoming visible again.

## Identity and HTTP behavior

Custom keys accept `{host}`, `{uri}`, `{path}`, `{method}`, and `{header.X}`. Unknown, empty, whitespace-containing, or malformed placeholders fail validation. URI includes query parameters; path does not.

Credential-bearing or authenticated requests require a nonempty identity dimension, for example `key: "{host}:{uri}:{header.Authorization}"`. Authentication-injected headers such as X-Auth-Subject are supported, but authentication must overwrite client-supplied identity headers. Disable caching for personalized endpoints unless identity isolation is explicit.

Only GET fills the cache. HEAD can consume an existing GET entry; misses pass through. Cacheable statuses are 200, 203, 300, and 301. Hits support conditional and range requests; upstream 206 is not cached.

Set-Cookie, private, no-store, no-cache, and unsupported Vary responses are not cached. Supported Vary dimensions are Origin and Accept-Encoding. WebSocket, gRPC, SSE, streaming flushes, incomplete responses, and oversized bodies bypass caching. Compressed upstream bodies can be cached as separate variants; bodies are not necessarily uncompressed.

TTL uses the shorter route/upstream freshness, accounting for Age. Request no-cache/max-age=0 forces refresh; no-store bypasses. Upstream stale-while-revalidate permits stale responses with background refresh. The gateway setting caps that window without creating one absent from upstream policy. Redis defaults to a zero cap; unspecified local caps preserve upstream behavior.

## Invalidation API

`POST /api/proxy-cache/purge` uses dashboard API-token/session authentication. Session writes require existing Origin/Referer CSRF checks. Include any configured dashboard path prefix.

```json
{"scope":"route","site":"example.com","route":"cached-list"}
```

| Scope | Required fields | Target |
| --- | --- | --- |
| all | none | Current namespace |
| site | site | Request Host domain, ignoring port and case |
| route | site, route | A named route at that domain |
| key | base_key | An opaque internal base key and its variants |

Redis scope invalidation rotates generations; old bodies expire without database-wide scans. Older fills cannot make invalidated responses visible again. Exact-key invalidation also prevents old fills committing. **Local site/route invalidation conservatively clears the entire cache in that process**, reclaiming resources immediately; other processes are unaffected.

## Invalidate after a write

```yaml
site: example.com
routes:
  - name: cached-list
    match: {path: /api/items, method: [GET]}
    proxy: 127.0.0.1:8080
    cache: {ttl: 30s}
  - name: update-item
    match: {path: /api/items, method: [POST]}
    proxy: 127.0.0.1:8080
    on_success:
      invalidate_proxy_cache: [cached-list]
```

invalidate_proxy_cache accepts route names in the current request's site; `["*"]` invalidates that site. Only upstream 2xx responses trigger it. Existing invalidate_cache still targets template fetch_json.cache_tags; both can be configured together.

If Redis invalidation fails, the upstream write is preserved, the response carries X-LiteGate-Cache-Invalidation: failed, and the gateway logs the failure and attempts up to three bounded retries. Retries are not durable and stop with process exit. Callers requiring read-after-write consistency must handle the marker. Disable caching for strictly real-time endpoints; asynchronous Redis failover does not provide strong consistency.

## Failures and observability

Redis failures bypass caching and return to the origin without independent local fallback. Use rate limits to protect the origin. Distributed fill locks use a 30-second lease, renewal every 10 seconds, and unique ownership tokens. Waiting for shared fills lasts approximately 200ms before requests can return to the origin; failures do not always guarantee a single origin request.

Metrics: litegate_proxy_cache_requests_total, litegate_proxy_cache_operations_total, and litegate_proxy_cache_redis_duration_seconds. Administrative invalidation returns 503 on Redis failure; a successful upstream write is not presented as an upstream failure merely because cache invalidation failed.
