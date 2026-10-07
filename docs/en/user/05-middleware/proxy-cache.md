# Proxy Cache (Reverse-Proxy Content Cache)

`proxy_cache` stores upstream responses locally at the gateway and serves hits directly without contacting the backend. It is ideal for absorbing traffic spikes, micro-caching high-QPS APIs, and reducing backend load. Equivalent to Nginx's `proxy_cache`.

> Configured per route on the `action`; only meaningful for `proxy` routes.

---

## 1. Minimal Configuration

```yaml
routes:
  - name: cached-api
    match:
      path_prefix: /api/list
    action:
      type: proxy
      upstream:
        - "127.0.0.1:8080"
      proxy_cache: true
      proxy_cache_ttl: 30      # Cache for 30 seconds
```

Each response carries `X-LiteGate-Cache: HIT` / `MISS` for easy debugging.

---

## 2. Field Reference

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `proxy_cache` | bool | `false` | Enable content caching for this route |
| `proxy_cache_ttl` | int | `10` | Cache lifetime (seconds). Upstream `Cache-Control` is also honored; the **shorter** value wins |
| `proxy_cache_key` | string | `method:host:route:uri` | Custom cache key template (see below) |

Global cap (`config.yaml`):

```yaml
cache:
  proxy_cache_max_entries: 10000   # Max cache entries; LRU-evicted beyond this to prevent OOM
```

---

## 3. Custom Cache Key

The default key already includes method, Host, route name and the full URI (with query string). For finer control use `proxy_cache_key` with placeholders:

- `{host}`, `{uri}`, `{path}`, `{method}` (`{uri}` includes the query string; `{path}` does not)
- `{header.X}`: value of request header `X`

```yaml
action:
  type: proxy
  upstream: ["127.0.0.1:8080"]
  proxy_cache: true
  proxy_cache_ttl: 60
  proxy_cache_key: "{host}:{uri}:{header.Accept-Language}"   # Cache per language
```

---

## 4. Automatic Cache Bypass (Leak / Error Safety)

To avoid caching private or non-cacheable content, the cache is **bypassed automatically** when any of the following holds:

- Request has an `Authorization` or `Cookie` header;
- Response has `Set-Cookie`;
- Response `Cache-Control` contains `private` / `no-store` / `no-cache`, or `max-age=0`;
- Response has a `Vary` header other than `Accept-Encoding` or `Origin`;
- Non-`GET` / `HEAD` requests;
- WebSocket upgrades, gRPC, SSE (`text/event-stream`);
- `Range` or conditional requests (`If-None-Match` / `If-Modified-Since` / `If-Range`);
- The route has auth/identity injection but the cache key lacks an identity dimension (prevents cross-user leakage).

Only `200` / `203` / `300` / `301` responses are cached.

---

## 5. Interaction with Compression

`proxy_cache` stores the **uncompressed** response body; compression happens in an outer layer per the client's `Accept-Encoding`. A single cached entry therefore serves both compression-capable and non-capable clients without sending the wrong encoding.

---

## 6. Memory & Safety Protections

- **1MB per-object cap**: once a response body streams past 1MB it is no longer cached (still passed through to the client), so memory is not consumed.
- **Global entry cap**: beyond `proxy_cache_max_entries`, entries are LRU-evicted to prevent cache-flooding OOM.
- **Request collapsing**: concurrent MISSes for the same key collapse into a single upstream fetch (singleflight), avoiding cache stampede.

---

## Best Practices

1. **Micro-caching**: for read-heavy endpoints that tolerate slight staleness, set `proxy_cache_ttl: 1–5` to flatten spikes dramatically.
2. **Don't globally cache personalized endpoints**: either leave caching off for authenticated endpoints, or fold the identity dimension into `proxy_cache_key`.
3. Combine with [rate limiting](./rate-limit.md) and [concurrency limiting](./rate-limit.md#5-concurrent-connection-limit-limit_conn) to protect the backend.
