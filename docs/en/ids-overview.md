# What IDS Is and Why You Need It

> This is the entry and positioning page for IDS. For contract details see [IDS Provider development and rollout](ids-provider-plugin-guide.md); for Go vs WASM see [Choosing Go vs WASM](ids-go-vs-wasm.md); for copyable scenarios see [IDS recipes](ids-recipes.md).

## In one sentence

**IDS is a business-identity and routing decision seam that LiteGate opens between "route matched" and "action not yet executed".** The core has no built-in `tenant_id`, `app_id`, JWT or login semantics; who the caller is, whether they may enter, and how the request continues are all decided by a plugin from the raw HTTP request and your business systems.

```text
Client → route match → IDS Provider.Evaluate ──┬─ Forward: inject trusted headers / rate limit, then run the Action (proxy can also pick instances)
                                               ├─ Respond: answer the client directly (401/403/...)
                                               └─ error: handled by fail_policy
        → dynamic rate limit → Action (proxy: service discovery with Selector/Meta filtering → downstream)
```

## Mental model

The core offers one typed contract and **enforces the semantics** of every part of the decision:

| Decision field | Meaning | How the core treats it |
|---|---|---|
| `Action: Forward/Respond` | Pass or respond directly | Respond short-circuits; downstream is not contacted |
| `Headers` | Trusted identity headers injected downstream | Projected through the `allowed_headers` allow list; sensitive headers are blocked as a backstop |
| `Discovery.Selector.Match` | Hard isolation boundary, e.g. `{cluster: a}` | Only cluster A may be used, **never degrading to B** |
| `Discovery.Selector.Meta` | Soft preference inside the boundary, e.g. `{version: v2}` | Uses v2 when present, otherwise falls back to the default pool in the same boundary |
| `RateLimit{Key, RequestsPerSecond}` | Dynamic quota per business subject | Applied after Forward and before the Action; over the limit returns 429 |

Providers are **lazily created concurrent singletons by name**; each call receives a copy of the route's current `options`, so site configuration or service tag hot reloads **need no restart**.

## How IDS differs from middleware

The most common question. The standard answer:

> **Middleware is a processing pipeline** — a chain of generic, ordered, composable request transformers (auth, cors, ratelimit, headers, strip_prefix) answering "how should this request be processed".
> **IDS is a decision point** — a single business-identity verdict after route matching and before the Action, answering "who are you, may you enter, and how should this request continue"; a proxy Action can also choose backend instances from it.

Structural differences:

| Aspect | Middleware | IDS |
|---|---|---|
| Shape | Chained, many, ordered | Single point, exactly one per route |
| Position | In the generic request pipeline | At the boundary after matching and before the Action |
| Output | Opaque request/response rewrites | A typed decision the core understands and enforces |
| **Can it choose backends** | **No** | **Yes** (Selector hard boundary + Meta soft preference) |
| Trust model | Looser | Strips client-forged internal headers; only projects regenerated, allow-listed values |
| Typical job | Cross-cutting processing | Identity verdict + multi-tenant routing + per-subject rate limiting |

**The decisive difference in one line: IDS output feeds service discovery; middleware cannot choose backends.** Authentication, multi-tenant routing and per-subject quotas happen once, in one business-neutral contract — that is why IDS exists and why an ordinary middleware cannot replace it.

## Why not make it a middleware

1. **Fixed placement**: it must run "after matching, before discovery" and produce a structured decision, not a generic `ServeHTTP` wrapper.
2. **The core can reason about the decision**: Forward/Respond + Selector/Meta/RateLimit/Headers are typed, so the core can project allow-listed headers, treat Selector as a hard isolation boundary and backstop sensitive headers. Middleware just rewrites requests opaquely; the core cannot tell what it did.
3. **Trust boundary**: IDS first strips internal identity headers sent by clients (`X-Lito-Verified`, `X-Request-Source`, ...) and only lets through headers the plugin regenerated and allow-listed.
4. **Single verdict**: exactly one IDS per route, whereas middleware is a chain.

## Compared with other gateways

| Approach | Shape | Can it choose backends | Notes |
|---|---|---|---|
| **LiteGate IDS** | In-process (Go) or in-process sandbox (WASM) | ✅ | Authorization + routing + per-subject rate limiting in one, business-neutral |
| Envoy `ext_authz` | Out-of-process RPC | ❌ | An extra hop of latency and operations; allow/deny only, cannot pick a backend cluster |
| Nginx `auth_request` | Subrequest | ❌ | Allow/deny only, no typed decision or routing |
| Kong plugins | Middleware-style | ❌ | Essentially a processing chain, not a dedicated routing verdict |

**Headline**: other gateways' authorization hooks stop at allow/deny; an IDS decision **drives service discovery directly**.

## When to use IDS

Good fit:
- Multi-tenant SaaS: read identity → query tenant system/Redis → inject database context → route per tenant to a database or cluster.
- Open platforms: read App ID → fetch secret → verify signature → inject common headers.
- Canary / multi-version: pick v2 within a cluster by business rules, falling back safely when absent.
- Dynamic rate limits per tenant/app/device rather than static limits per route.

Not a fit (ordinary middleware will do):
- Generic processing unrelated to business identity: CORS, compression, static rate limits, header rewriting.
- Standard JWT/API-key authentication without routing — use the built-in authentication middleware.

## Two implementation layers

IDS Providers can be written two ways, covering different scenarios; see [Choosing Go vs WASM](ids-go-vs-wasm.md):

- **Go Provider**: trusted, can reach Redis/DB/HTTP, highest performance. All main paths that need external lookups.
- **WASM Provider**: sandboxed, multi-language (Rust, ...), hot-deployable without rebuilding the gateway. **Self-contained computation only** (signature checks, JWT verification, static policy, header/rate-limit key transforms); the host provides no I/O.

## Next steps

- Understand the contract and security boundaries → [IDS Provider development and rollout](ids-provider-plugin-guide.md)
- Decide between Go and WASM → [Choosing Go vs WASM](ids-go-vs-wasm.md)
- Copy an end-to-end scenario → [IDS recipes](ids-recipes.md)
- Write a Go Provider → [IDS Provider plugin development and configuration](ids-provider-plugin-guide.md)
- Write a WASM Provider → [IDS WASM plugin development guide](ids-wasm-plugin-guide.md)
