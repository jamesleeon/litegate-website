# IDS Plugin Development: Caveats and Pitfalls

> This page collects the **core design constraints, common bugs, security risks and performance traps** of writing custom IDS (Identity & Decision Service) plugins for LiteGate.
> Related: [IDS overview](ids-overview.md) · [IDS development guide](ids-provider-plugin-guide.md) · [IDS recipes](ids-recipes.md).

---

## 🧭 Mental model and architectural constraints

Keep these three host rules in mind before writing an IDS plugin:

1. **Concurrent singleton**: inside the gateway a Provider instance is a **long-lived singleton shared across requests**. `Evaluate` is called **concurrently** by huge numbers of goroutines.
2. **Decisions drive service discovery**: IDS isn't just an interceptor. Its output (`IDSDecision`) is used directly by the host for **instance filtering (Selector/Meta), dynamic rate limiting and trusted header projection**.
3. **Strict host control and breakers**: the host enforces concurrency control (default limit 100), execution timeouts (default 500 ms) and failure-rate-based circuit breaking on Providers.

---

## ⚠️ Six footguns and how to avoid them

### 🚨 Footgun 1: caching request state on the Provider struct (data race)

* **Symptom**: under concurrency tests or heavy production traffic, tenant A's request occasionally gets tenant B's identity, or data is cross-contaminated, or the process panics.
* **Cause**: the Provider struct is a global singleton. Non-thread-safe fields holding per-request data are overwritten by concurrent requests.

❌ **Wrong**:
```go
type MyIDSProvider struct {
    logger       *zerolog.Logger
    currentAppID string // ❌ serious bug: requests overwrite each other!
    requestToken string // ❌ serious bug: data leaks across requests!
}

func (p *MyIDSProvider) Evaluate(ctx context.Context, input plugin.IDSInput) (*plugin.IDSDecision, error) {
    p.currentAppID = input.Request.Header("X-App-Id")[0]
    p.requestToken = input.Request.Header("Authorization")[0]
    // Under concurrency, currentAppID has already been changed by another goroutine here!
    tenant, _ := p.db.FindTenant(p.currentAppID)
    ...
}
```

✅ **Right**:
The Provider struct holds **only global read-only dependencies or concurrency-safe client pools**. All per-request state must be **local variables** inside `Evaluate`:
```go
type MyIDSProvider struct {
    logger *zerolog.Logger       // global, read-only
    rdb    redis.UniversalClient // concurrency-safe client
}

func (p *MyIDSProvider) Evaluate(ctx context.Context, input plugin.IDSInput) (*plugin.IDSDecision, error) {
    // Local variables with their own lifetime: fully concurrency-safe
    appID := first(input.Request.Header("X-App-Id"))
    token := first(input.Request.Header("Authorization"))
    ...
}
```

---

### 🚨 Footgun 2: external I/O ignoring the context, leaking goroutines and exhausting concurrency slots

* **Symptom**: when the downstream auth system or Redis slows down, the gateway suddenly floods with `IDS provider concurrency limit reached (100)` and every request on the route is rejected.
* **Cause**:
  - The LiteGate host limits a Provider's maximum in-flight calls with an atomic counter in `internal/middleware/ids_guard.go` (`max_concurrency`, default 100).
  - The gateway has cooperative timeouts (default 500 ms), but **the Go runtime cannot kill blocked network I/O**.
  - If the plugin calls external HTTP / Redis / MySQL **without passing `ctx`**, the background goroutine keeps waiting even after the gateway has timed out, the in-flight counter can't decrease, the 100 slots fill quickly, and the whole route is denied.

❌ **Wrong**:
```go
// ❌ Wrong: the default client or context.Background() ignores the incoming ctx
resp, err := http.Get("http://auth-service/verify?token=" + token)
val, err := p.rdb.Get(context.Background(), "session:"+token).Result()
```

✅ **Right**:
All external network and database operations **must inherit the incoming `ctx`**:
```go
// ✅ Right: when the gateway timeout fires, the HTTP request and Redis call stop and release resources
req, _ := http.NewRequestWithContext(ctx, http.MethodGet, "http://auth-service/verify", nil)
resp, err := p.httpClient.Do(req)

val, err := p.rdb.Get(ctx, "session:"+token).Result()
```

---

### 🚨 Footgun 3: confusing business rejection with system errors (Respond vs. error)

* **Symptom**: with `fail_policy: allow` (meant to degrade gracefully when the auth service is down), forged wrong passwords, expired tokens and invalid signatures **are all let through**.
* **Cause**:
  - `ActionRespond` means **the business decision is "not allowed"** (wrong password, expired token, invalid signature). The plugin should build a 401/403 response to block the request.
  - `error` means **an infrastructure failure of the gateway or plugin** (Redis down, DB timeout, network broken).
  - `fail_policy: allow` exists to **pass only on infrastructure `error` when failover is acceptable — never to change an explicit `ActionRespond` rejection.** If the plugin returns a business authentication failure as an `error`, under `allow` the gateway treats it as a system fault and lets it through.

❌ **Wrong**:
```go
if !isValidSignature(appID, sign) {
    // ❌ Wrong: business rejection returned as an error! With fail_policy: allow this passes — a serious hole!
    return nil, fmt.Errorf("invalid signature")
}
```

✅ **Right**:
```go
if !isValidSignature(appID, sign) {
    // ✅ Right: business rejections must return ActionRespond
    return &plugin.IDSDecision{
        Action: plugin.ActionRespond,
        Response: &plugin.DirectResponse{
            Status: http.StatusUnauthorized,
            Headers: http.Header{"Content-Type": []string{"application/json"}},
            Body:   []byte(`{"code":"invalid_signature","message":"Signature verification failed"}`),
        },
    }, nil
}

// Return error only for infrastructure failures (e.g. Redis down)
tenantInfo, err := p.lookupTenantFromRedis(ctx, appID)
if err != nil {
    return nil, fmt.Errorf("redis lookup failed: %w", err)
}
```

---

### 🚨 Footgun 4: multi-tenant secret lookup "silently degrading" and letting signatures through

* **Symptom**: on a multi-tenant open platform, an unauthorized or disabled `app_id` passes gateway verification just by signing with the global default test key.
* **Cause**:
  When the plugin's dynamic per-tenant key lookup misses for an `app_id`, the code doesn't reject; it "helpfully" falls back to a default environment variable secret (such as `LITEGATE_OPENAPI_MD5_SECRET`). Once a global default exists in production, every illegal `app_id` can authenticate with it.

✅ **Rules**:
- When a route declares per-tenant key lookup (for example a key-prefix option defined by the plugin), a missing tenant **must fail immediately**; never fall back across layers to a global default key.
- Key lookup errors must say which tenant/App ID is missing, rather than suggesting a missing environment variable.

---

### 🚨 Footgun 5: sensitive headers injected without being listed in `allowed_headers` (blocked with 403)

* **Symptom**: the plugin sets `Headers.Set("X-Tenant-Id", "1001")` and returns `ActionForward`, but the client receives `403 Forbidden: IDS sensitive header is not allowlisted: X-Tenant-Id`.
* **Cause**:
  The LiteGate core enforces strict zero-trust protection at the edge. Before IDS runs, client-forged internal headers are stripped; after IDS, **headers injected downstream with sensitive keywords (`tenant-id`, `tenant-code`, `db-name`, `shard-id`, `cluster-id`, `sid`, ...) must pass an allow list**. Sensitive headers not declared in YAML are blocked by the gateway.

✅ **Correct configuration**:
In the site YAML route, allow the sensitive headers the plugin injects with `header_projection.allowed_headers`:
```yaml
site: api.example.com
services:
  core-service:
    discovery: {name: core-service}
routes:
  - name: saas-api
    match:
      path_prefix: /api
    service: core-service
    ids:
      provider: my-saas-auth
      header_projection:
        allowed_headers:
          - X-Tenant-Id
          - X-Database-Ref
          - X-Shard-Id
```

---

### 🚨 Footgun 6: no negative cache, leading to cache penetration and avalanches

* **Symptom**: an attacker scans the gateway with huge numbers of random fake tokens / App IDs, and the backend auth service or core DB CPU spikes instantly.
* **Cause**:
  The plugin caches in Redis or memory, but only **users that exist**. For "no such user / invalid token" every request goes through the cache to the backend DB.

✅ **Recommended defense (prefer the official `idskit.IdentityLoader`)**:
Use the official runtime package `pkg/plugin/idskit`. Its generic `IdentityLoader` includes 128-bit HMAC-SHA-256 fingerprints keyed with a per-process random secret, SingleFlight request coalescing, `WithoutCancel` timeout isolation, automatic negative caching on `ErrNotFound`, and invalidation that can't be resurrected thanks to an atomic in-flight state lock:

```go
loader := idskit.NewIdentityLoader(func(ctx context.Context, rawToken string) (*TenantInfo, error) {
    tenant, err := p.queryBackend(ctx, rawToken) // receives the raw credential, can query directly
    if err != nil { return nil, err } // infrastructure errors are not negatively cached
    if tenant == nil { return nil, idskit.ErrNotFound } // written to a 2s negative cache automatically
    return tenant, nil
}, idskit.LoaderOptions{
    KeyFunc:     idskit.TokenFingerprint, // cache/coalescing key is a fingerprint; long tokens never sit in memory in plaintext
    TTL:         30 * time.Second,
    NegativeTTL: 2 * time.Second,
})
// Call with the raw credential: loader.Get(ctx, rawToken)
// Invalidate with the raw credential too (must match Get so KeyFunc yields the same key): loader.Invalidate(rawToken)
```

If you write your own cache, write a negative marker with a short TTL (1–3 s) for invalid/nonexistent identities, cache only business `NotFound`, and never cache network failures or DB errors.

---

## ⚡ Performance and availability practices

### 1. Use `input.Request.Body()` with care
* `input.Request.Body()` materializes the request body in memory (host hard limit 8 MiB; over the limit returns `IDSBodyTooLargeError`).
* The host restores the body stream after reading, but materializing bodies frequently under high concurrency or large uploads creates heavy GC pressure.
* **Rules**:
  - For file uploads, audio/video streaming and other heavy routes, **don't use IDS plugins that read the body**; authenticate from headers / query / TLS client certificates only.
  - For JSON API routes, constrain `max_body_size` in the plugin configuration (for example `64KiB`).

### 2. Designing keys for dynamic rate limits (`RateLimitDecision`)
* When an `IDSDecision` returns `RateLimit`, `Key` must be a **business subject** (such as `tenant:1001` or `app:order-sync`).
* **Rules**:
  - Don't use high-cardinality, unbounded, changing strings (URLs with random numbers, full raw tokens) as keys, or the gateway's local token bucket cache will blow up.
  - `RequestsPerSecond` must be strictly greater than 0 (not negative, NaN or Inf).

### 3. Using `Selector` (hard boundary) and `Meta` (soft preference) correctly
* **`Discovery.Selector.Match` (hard boundary)**: for multi-tenant database sharding and physical data-center isolation (such as `{"cluster": "tenant-a-dedicated"}`). **If the target cluster has no available instance, the gateway returns 503 and never degrades to another cluster.**
* **`Discovery.Selector.Meta` (soft preference)**: for canary releases (such as `{"version": "v2"}`). **If all `v2` instances are down or undeployed, the gateway falls back to the default pool under the same Selector**, keeping the business available.

---

## 📋 Production IDS Provider checklist

Before deploying a custom IDS plugin to production, check each item:

- [ ] **Prefer `idskit`**: use `pkg/plugin/idskit` to avoid SingleFlight, context isolation and negative caching pitfalls automatically.
- [ ] **Concurrency safety**: no per-request fields on the struct, no unprotected map access; local caches have an LRU capacity limit (no OOM).
- [ ] **Context propagation and isolation**: every HTTP / Redis / gRPC / SQL call honors `ctx`; coalesced backend lookups use `context.WithoutCancel` so one caller's cancellation doesn't affect others.
- [ ] **Semantics**: business rejections use `idskit.RespondUnauthorized` / `ActionRespond`; only infrastructure failures return `error`.
- [ ] **Configuration and secrets**: no plaintext passwords hard-coded in `options`; multi-tenant lookups have clear isolation boundaries and no arbitrary fallback.
- [ ] **Header allow list**: every sensitive header injected downstream is declared in the route's `allowed_headers`.
- [ ] **Penetration protection**: a short local TTL negative cache for frequent invalid requests.
- [ ] **Heavy traffic**: don't read the body unless necessary; when you must, configure a sensible `max_body_size`.
- [ ] **Graceful shutdown**: plugins holding background goroutines or database pools implement `plugin.IDSCloser`.
