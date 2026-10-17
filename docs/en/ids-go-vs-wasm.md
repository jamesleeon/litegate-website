# Choosing an IDS Provider: Go vs WASM

> WASM support is experimental and not compiled by default. The host is tested with synthetic WASM modules, but the Rust example artifacts have not yet entered end-to-end release verification; prefer Go Providers for stable delivery.

> For positioning see the [IDS overview](ids-overview.md); for the contract see [IDS Provider development and rollout](ids-provider-plugin-guide.md).

IDS Providers have two implementation layers. They are not "stronger" and "weaker"; they **cover different scenarios**. Picking the wrong one means either giving up sandbox isolation or running into I/O the sandbox cannot do.

> **Build prerequisite**: Go Providers are compiled into the gateway by default. WASM support (wazero runtime, about +4 MB) is **not** compiled in by default; build with `-tags wasmids` (`go build -tags wasmids ./cmd/litegate`, or `make all-wasm`). Without the tag, `ids_wasm.enabled: true` is ignored with a warning. See the [WASM development guide](ids-wasm-plugin-guide.md).

## One table to decide

| Capability / need | Go Provider | WASM Provider |
|---|---|---|
| Look up sessions in Redis / DB / tenant system | ✅ | ❌ **the host provides no I/O** |
| Call external HTTP services | ✅ | ❌ |
| Self-contained computation: signature checks, JWT verification, static policy | ✅ | ✅ |
| Header transforms, rate-limit key derivation, routing decisions | ✅ | ✅ |
| Read shared plugin configuration (`config_get`) | ✅ | ✅ |
| Multiple languages (Rust, TinyGo, ...) | ❌ Go only | ✅ |
| Hot deploy without rebuilding / redeploying the gateway | ❌ compiled in, needs restart | ✅ drop in the artifact to hot-load |
| Sandbox isolation (memory / timeout / no escape) | ❌ fully trusted | ✅ |
| Distribution from untrusted third-party authors | ⚠️ high risk | ✅ |
| Per-request overhead | Lowest | Serialization + instantiation + call cost |

## The key boundary: WASM does no I/O

The WASM host exposes only three host functions to modules (see `internal/wasmids/host.go`):

- `config_version` — read the shared configuration version
- `config_get` — read shared configuration values allowed by the `config_prefixes` allow list
- `log` — structured logging

**No HTTP, no Redis, no database, no network or storage access of any kind.**

So the **main use cases** — "read JWT → look up Redis session → inject database context", "read App ID → fetch secret from the tenant system → verify signature" — **cannot be done inside WASM**, because they all need external lookups. Don't expect a WASM Provider to reach a session store.

WASM is for **compute-heavy, self-contained** decisions:
- **Signature or JWT verification** with keys from shared configuration (keys injected via `config_get`, verification computed in the sandbox).
- **Static policy** decisions based on request content.
- **Header transforms**, **rate-limit key derivation**, rule-based **Selector/Meta routing**.

## Decision guide

**Use Go if** the decision needs a session lookup, a tenant system query, or any external storage or service — that is, most stateful SaaS paths.

**Use WASM if** at least one applies:
- You need **multiple languages** (the team writes Rust).
- You need **hot deployment without rebuilding the gateway** (operations tweak policy often and don't want to recompile and restart each time).
- You must distribute plugins from **untrusted / third-party authors** safely (sandbox limits, no escape).
- The decision is **pure computation + configuration** and touches no I/O.

**The two can coexist**: each route picks its own Provider. A common combination is Go for the stateful main path and WASM for pure-compute slices such as signature checks or policy, handed to business teams for hot iteration.

## If you really need "WASM + I/O"

That is an explicit roadmap trade-off, not an existing capability. Letting WASM query sessions would require new host functions such as `kv_get`/`http_fetch`, which reintroduce:

- a sandbox escape surface (modules can make external calls);
- timeout and concurrency governance (cancellation, limits and connection reuse for external calls);
- a credential boundary (who holds the Redis password).

Until those costs are understood, **keep "WASM computes, Go does I/O"** — the more honest and lower-maintenance boundary.

## Both layers share one contract

Go or WASM, the result is the same `IDSDecision` (Forward/Respond + Headers/Discovery/RateLimit/Response). The core applies allow-list projection, Selector hard boundaries, dynamic rate limits and `fail_policy` the same way. Switching implementation layers **does not change what the route configuration means**.

## Next steps

- Go implementation → [IDS Provider plugin development and configuration](ids-provider-plugin-guide.md)
- WASM implementation → [IDS WASM plugin development guide](ids-wasm-plugin-guide.md)
- End-to-end scenarios → [IDS recipes](ids-recipes.md)
