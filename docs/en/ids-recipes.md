# IDS Recipes

> Copyable end-to-end scenarios. For the contract see [IDS Provider development and rollout](ids-provider-plugin-guide.md); for choosing a layer see [Choosing Go vs WASM](ids-go-vs-wasm.md).
> All Provider logic below lives in `Evaluate`; for registration and project structure see the [Go guide](ids-provider-plugin-guide.md) / [WASM guide](ids-wasm-plugin-guide.md).

Each recipe gives: **goal → route configuration → key Provider decisions**.

---

## Recipe 1 · Look up a session and inject database context (Go)

**Goal**: read the JWT/token → look up the Redis session → pass and inject tenant and database context downstream.

```yaml
site: api.example.com
services:
  shared-saas-service:
    discovery: {name: shared-saas-service}
routes:
  - name: protected-api
    match: { path_prefix: /api }
    service: shared-saas-service
    ids:
      provider: saas-session
      fail_policy: deny
      options:
        token_header: Authorization
        session_ref: tenant-session-prod
      header_projection:
        allowed_headers: [X-Tenant-Ref, X-Database-Ref]
```

**Key decisions**:

```go
values := in.Request.Header(in.Options.Get("token_header"))
if len(values) != 1 || values[0] == "" {
    return &plugin.IDSDecision{Action: plugin.ActionRespond,
        Response: &plugin.DirectResponse{Status: http.StatusUnauthorized}}, nil
}
session, err := p.lookup(ctx, in.Options.Get("session_ref"), values[0]) // in-process cache → Redis → backfill
if err != nil { return nil, err }                                        // infrastructure failure → error
if session == nil {
    return &plugin.IDSDecision{Action: plugin.ActionRespond,
        Response: &plugin.DirectResponse{Status: http.StatusUnauthorized}}, nil
}
return &plugin.IDSDecision{
    Action:  plugin.ActionForward,
    Headers: http.Header{"X-Tenant-Ref": {session.TenantRef}, "X-Database-Ref": {session.DatabaseRef}},
}, nil
```

- Business rejections use `Respond`; infrastructure failures use `error` (`fail_policy` decides between passing and 503).
- Injected headers must be **regenerated** by the plugin; client-forged headers with the same names have already been stripped by the core.
- Redis/DB clients are concurrency-safe, reused connections inside the Provider singleton; passwords come from [shared plugin configuration](ids-provider-plugin-guide.md#dynamic-configuration-secrets-and-caching), not `options`.

---

## Recipe 2 · Open-platform signature verification (Go or WASM)

**Goal**: read the App ID → fetch the secret → verify the request signature → inject a common identity header.

Pure signature checking is **self-contained computation** and can use WASM (secret injected via `config_get`, verification computed in the sandbox); if the secret must be fetched live from a tenant system, use Go.

```yaml
site: open.example.com
/api:
  proxy: 127.0.0.1:8080
  ids:
    provider: openapi-sign     # WASM or Go, same contract by name
    fail_policy: deny
    options: { app_header: X-App-Id, sign_header: X-Sign }
```

**Key decisions**: read `app_id` → fetch the secret from shared plugin configuration with `in.Config.Scope("providers.openapi-sign").Lookup(app_id)` → recompute the signature and compare with `X-Sign` → on success `Forward` with `X-App-Verified`, otherwise `Respond 401`.

> The built-in [openapi-md5](openapi-md5-ids-plugin.md) is a ready reference.

---

## Recipe 3 · Route each tenant to its own database / cluster (Selector hard boundary)

**Goal**: tenant A's traffic may **only** enter cluster A, never degrading to another cluster.

`Selector` is a hard isolation boundary. After returning `{cluster: a}`, service discovery chooses only among instances with that label; if none is found the request fails and **does not** fall to another cluster.

```go
return &plugin.IDSDecision{
    Action: plugin.ActionForward,
    Discovery: &plugin.DiscoveryDecision{
        Selector: &plugin.DiscoverySelector{Match: map[string]string{"cluster": session.Cluster}},
    },
}, nil
```

Downstream instances need the matching discovery label (such as `cluster=a`). Use this for tenants with physically isolated clusters or databases.

---

## Recipe 4 · Canary versions (Meta soft preference)

**Goal**: prefer v2 within the same cluster, falling back safely to the cluster's default instances when v2 isn't deployed.

`Meta` is a soft preference inside the Selector boundary: `{version: v2}` uses v2 when present, otherwise falls back to **the default pool in the same Selector that declares no route meta**, never to other versions or other Selectors.

```go
return &plugin.IDSDecision{
    Action: plugin.ActionForward,
    Discovery: &plugin.DiscoveryDecision{
        Selector: &plugin.DiscoverySelector{
            Match: map[string]string{"cluster": session.Cluster}, // hard boundary
            Meta:  map[string]string{"version": "v2"},            // soft preference
        },
    },
}, nil
```

So a cluster can hold three default instances plus one canary instance; forgetting to deploy the canary still falls back safely to the cluster's defaults. Canary ratios and A/B rules are up to the Provider (for example by tenant ID suffix).

---

## Recipe 5 · Dynamic rate limits per business subject (RateLimit)

**Goal**: quotas per business subject such as tenant/app/device, not per route. The core doesn't know what the subject is.

```go
return &plugin.IDSDecision{
    Action:    plugin.ActionForward,
    RateLimit: &plugin.RateLimitDecision{Key: session.SubjectRef, RequestsPerSecond: session.QPS},
}, nil
```

- Order: **IDS → dynamic rate limit → Selector/Meta service discovery → proxy**. Over the limit returns 429 directly, without looking up instances or contacting downstream.
- `Key` is an opaque business subject and `QPS > 0`; it is hashed before entering local caches, Redis or logs. The same Provider + route + key share one token bucket.
- Coexists with the route's static `rate_limit`: the static limit protects the whole route and runs **before** IDS; the IDS dynamic limit handles per-subject quotas.

---

## Recipe 6 · Pure-compute WASM Provider (Rust)

**Goal**: write a self-contained verification Provider in Rust, hot-loaded by dropping in the artifact, without rebuilding the gateway.

Manifest (in the IDS WASM directory):

```yaml
name: rust-ids
kind: ids
abi: litegate.ids/v1
module: rust-ids.wasm
request:
  headers: [Authorization]     # expose only the request fields needed, minimizing input
  query: false
  body: false
config_prefixes: [shared.identity, providers.rust-ids]  # config_get allow list
limits: { timeout_ms: 100, memory_pages: 512, max_input_bytes: 1048576, max_output_bytes: 262144 }
```

The Provider exports `alloc` + `evaluate`; input and output are JSON (`IDSDecision`) in linear memory. For a complete skeleton see `examples/wasm-ids-rust/` and the [WASM guide](ids-wasm-plugin-guide.md).

**Constraint reminder**: inside WASM you **cannot** query Redis/DB/HTTP — only compute on values injected via `config_get`. For external lookups use Go (see [choosing a layer](ids-go-vs-wasm.md)).

---

## Header projection rules (all recipes)

The core projects headers injected by Forward safely:

- **Reserved headers are dropped**: `Authorization`, `Cookie`, `X-Forwarded-*`, `X-Real-IP`, `X-Lito-Verified`, `X-Request-Source`.
- **Sensitive names need the allow list**: header names containing `tenant-id`, `tenant-code`, `db-name`, `database-name`, `db-cluster`, `shard-id`, `cluster-id`, or a standalone `sid` segment, **must** be listed in `allowed_headers`, otherwise 403 is returned.
- Non-sensitive, non-reserved headers are projected normally.
- After passing, the core adds `X-Lito-Verified: true` and `X-Request-Source: trusted-router`, so downstream can tell the request went through the gateway's verdict.

> Naming tip: "reference" names such as `X-Tenant-Ref` / `X-Database-Ref` avoid sensitive fragments; when you must inject a sensitive name, list it in `allowed_headers` explicitly.

---

## Three ways to write the configuration

The same IDS configuration can be expressed as route YAML, service tags or [shared plugin configuration](ids-provider-plugin-guide.md#dynamic-configuration-secrets-and-caching). Service tags go on a named Router:

```text
litegate.http.routers.orders.match.hosts=api.example.com
litegate.http.routers.orders.ids.provider=saas-session
litegate.http.routers.orders.ids.failpolicy=deny
litegate.http.routers.orders.ids.options.token_header=Authorization
litegate.http.routers.orders.ids.allowedheaders=X-Tenant-Ref,X-Database-Ref
```

For all key names see the [service tag reference](user/03-configuration/tag-reference.md).

- `options` are hot-reloadable route parameters; changes need no restart. Put **policy/references** in them, not plaintext secrets.
- Keys and connection targets shared across Providers go in the shared plugin configuration file (`${ENV}` injects secrets; atomic snapshots; only scalars and maps are accepted).
