# Two-Layer Routing: Choose the Upstream, Then Rewrite the Path (Troubleshooting Recipes)

If you've only used `path:` for forwarding, you've used about half of LiteGate's routing. Combining **`rule:` matching** with **`rewrite`** solves most "tricky gateway problems" with one way of thinking. This page explains the mental model first, then gives a set of copyable recipes.

---

## 1. Mental model: two orthogonal questions

Handling a request comes down to two questions:

```
                A request arrives
                     │
        ┌────────────┴────────────┐
        │ Layer 1: pick upstream   │   ← decided by match / rule
        │ "Which backend gets it?" │      any boolean combination of host/path/
        └────────────┬────────────┘         query/header/IP/method selects a route
                     │
        ┌────────────┴────────────┐
        │ Layer 2: adapt the path  │   ← decided by rewrite
        │ "Does the backend know   │      after matching, change path/query to
        │  this URL?"              │      what the backend expects
        └────────────┬────────────┘
                     │
               Forward upstream
```

| Layer | Configuration | Job | Decides |
| --- | --- | --- | --- |
| Layer 1 | `match` (`path` or `rule`) | **Dispatch** | Which route → which upstream |
| Layer 2 | `rewrite` / `strip_prefix` | **Adapt** | Change path/query into the form the backend expects after matching |

**Two rules**:

1. **Choosing the upstream is always layer 1 (match)**, never rewrite.
2. **`rewrite` only changes the path within the matched route and never returns to the routing table** (unlike Nginx `rewrite ... last`).

Thinking in these two layers, many cases that used to need Nginx `if` + `rewrite ... last` become "one conditional route + an optional rewrite".

---

## 2. Why `path:` isn't enough, and what `rule:` unlocks

`path:` / `path_prefix:` can only dispatch by URL path. `rule:` is a boolean expression DSL that combines **any dimensions**:

- **Host**: `Host`, `HostRegexp`
- **Path**: `Path`, `PathPrefix`, `PathSuffix`, `PathRegex`
- **Query**: `Query`, `QueryPrefix` / `QueryIPrefix`, `QuerySuffix` / `QueryISuffix`, `QueryRegex`
- **Header**: `Header`, `HeaderRegexp`, `HeaderPrefix` / `HeaderIPrefix`, `HeaderSuffix` / `HeaderISuffix`
- **Cookie**: `Cookie`, `CookieRegex`, `CookiePrefix` / `CookieIPrefix`, `CookieSuffix` / `CookieISuffix`
- **Source / method**: `ClientIP` (CIDR supported), `Method`

> `Header`, `Query` and `Cookie` accept a single argument as an **existence check** (for example `Cookie("session")` matches when the cookie is present). Query/cookie values used for **value** matching must be single-valued; repeated names (several occurrences) don't match, so the gateway and the backend can't read different values.
- **Logic**: `&&`, `||`, `!`, parentheses

> For full semantics see the [rule expression DSL reference](../03-configuration/site-config.md#9-rule-expression-dsl-reference).

**Performance tip**: when there's one route and paths don't overlap, keep using `path:` (O(1) exact matching). You need `rule:` only when **several routes share a path and are distinguished by extra conditions**, and then give the more specific route a higher `priority` (see [section 4](#4-boundaries-and-pitfalls)).

---

## 3. Troubleshooting recipes

Every recipe follows the same pattern: **layer 1 picks the backend with match; layer 2 rewrites the path if needed**.

### 3.1 One OAuth callback URL, several backends

The platform allows only one callback URL, but callbacks must go to main/sub accounts by `state` prefix. → See [Single callback URL routing](./oauth-single-callback.md).

### 3.2 Canary releases (choose the upstream by header)

Traffic with a particular header goes to the new version; the rest to stable:

```yaml
- name: api-canary
  priority: 200
  match:
    rule: 'PathPrefix("/api/") && Header("X-Release", "canary")'
  proxy: ["10.0.0.9:8080"]   # new version
- name: api-stable
  priority: 100
  match:
    rule: 'PathPrefix("/api/")'
  proxy: ["10.0.0.1:8080"]   # stable
```

For percentage canaries, let an upstream color requests with the header, or start with internal clients via `ClientIP`.

### 3.3 Multiple API versions + legacy compatibility

New and old versions are deployed separately, while old clients' `/api/v1/*` maps smoothly to the v2 backend's new paths:

```yaml
# v2 / v3 each go to their own backend
- name: api-v3
  match: { path_prefix: "/api/v3/" }
  proxy: ["10.0.0.3:8080"]
- name: api-v2
  match: { path_prefix: "/api/v2/" }
  proxy: ["10.0.0.2:8080"]

# Old v1 clients → v2 backend, path rewritten into the v2 form (layer 2 adaptation)
- name: api-v1-compat
  match: { path_prefix: "/api/v1/" }
  proxy: ["10.0.0.2:8080"]
  rewrite:
    path:
      pattern: "^/api/v1/(.*)$"
      target: "/api/v2/$1"
```

Versions can also go in a header: `rule: 'PathPrefix("/api/") && Header("X-Api-Version", "v3")'`, keeping URLs clean.

### 3.4 A/B tests (split by cookie)

The native `Cookie` matcher splits by cookie value directly:

```yaml
- name: bucket-b
  priority: 200
  match:
    rule: 'PathPrefix("/") && Cookie("ab", "B")'
  proxy: ["10.0.0.12:8080"]   # variant B
- name: bucket-a
  priority: 100
  match: { path_prefix: "/" }
  proxy: ["10.0.0.11:8080"]   # variant A (default)
```

For values with prefix/regex patterns use `CookiePrefix("ab", "B")` or `CookieRegex("ab", "^B[0-9]+$")`.

### 3.5 Multi-tenant: one domain, each tenant to its own backend by header

```yaml
- name: tenant-blue
  priority: 200
  match: { rule: 'Header("X-Tenant", "blue")' }
  proxy: ["10.1.0.1:8080"]
- name: tenant-green
  priority: 200
  match: { rule: 'Header("X-Tenant", "green")' }
  proxy: ["10.2.0.1:8080"]
```

If tenants are distinguished by subdomain, separate sites with different `site:` values are simpler; use rules only when tenants appear in headers or paths of one domain.

### 3.6 Moving old URLs to a new backend's new paths

The old system's `/old/report/2024` must reach the new service's `/v2/analytics/report/2024`:

```yaml
- name: legacy-report
  match: { path_prefix: "/old/report/" }
  proxy: ["10.0.5.1:8080"]      # layer 1: switch to the new backend
  rewrite:
    path:
      pattern: "^/old/report/(.*)$"
      target: "/v2/analytics/report/$1"   # layer 2: new path
```

To simply strip one prefix, the lighter [`strip_prefix`](../04-actions/proxy.md#3-advanced-steering--proxy-settings) is enough; no rewrite needed.

### 3.7 Split by client type (different backends for web and mobile)

```yaml
- name: mobile-api
  priority: 200
  match:
    rule: 'PathPrefix("/api/") && HeaderRegexp("User-Agent", "(?i)(iphone|android)")'
  proxy: ["10.0.7.1:8080"]
- name: web-api
  priority: 100
  match: { path_prefix: "/api/" }
  proxy: ["10.0.7.2:8080"]
```

### 3.8 Features open only to internal IPs

```yaml
- name: admin-internal
  priority: 200
  match:
    rule: 'PathPrefix("/admin/") && ClientIP("10.0.0.0/8")'
  proxy: ["10.0.9.1:8080"]
- name: admin-blocked
  priority: 100
  match: { path_prefix: "/admin/" }
  respond:
    status: 403
    body: "forbidden"
```

(`ClientIP` uses the directly connected IP; if another proxy sits in front of LiteGate, configure `trusted_proxies` so it parses `X-Forwarded-For`.)

### 3.9 Selecting instance subsets by request attributes (service discovery subset routing)

The recipes above are all "one condition → one route → one upstream". When the backend is a set of instances **registered dynamically with service discovery** and the instances carry endpoint metadata (such as `sid`, `version`), you can also **select a subset of instances** through the Service's `discovery.selector.*` or a selector returned by IDS, without writing a route per tenant or version.

The values of `route_selector` and `route_meta` support `{cookie.x}` / `{header.x}` / `{query.x}` template variables (the same vocabulary as `rewrite` and `service_tag`). For example, sending traffic only to instances whose metadata matches the tenant cookie:

```yaml
- name: api-by-tenant
  match: { path_prefix: "/api/" }
  action:
    type: proxy
    service_name: api                 # dynamic instance pool from service discovery
    route_meta:
      tenant: "{cookie.tenant}"       # soft preference for the subset matching the cookie
      version: "{header.X-Api-Version}"
```

- **Choose the pool**: `service_name: api` is resolved into a set of instances by service discovery;
- **Filter the subset**: `route_meta` / `route_selector` use **the same request attributes** to select instances with matching metadata within the pool.

So in service discovery scenarios there is a third layer besides "match → rewrite": **dynamic filtering by instance metadata within the pool**. One route covers any number of tenants or versions, and instance changes follow service discovery automatically.

The difference between the two fields matters:

| Field | Semantics | Suits |
| --- | --- | --- |
| `route_meta` | **Soft preference**: matching instances first; falls back to other instances in the pool when none match | Canaries, version preference, locality |
| `route_selector` | **Hard isolation**: only matching instances; no match means no backend | Strong isolation boundaries |

> **Missing template values skip the key**: when `{cookie.tenant}` is absent it expands to an empty string and the key is **skipped** (it doesn't filter for an "empty tenant"). Requests without the cookie fall back to the default behavior of not filtering by tenant.
>
> **Security line (must read)**: cookies/headers/query are **forgeable by clients**. Template keys are fixed by you (the operator) in configuration; clients only control **values** — so whether this can be abused depends on which key you hand to which request attribute:
> - ✅ OK: **non-privileged dimensions** such as `tenant` / `version` / `region` / `ab`, especially with `route_meta` (soft preference).
> - ❌ Don't: template **physical isolation / permission boundary** keys (such as `sid`) into `route_selector` from a bare `{cookie.x}` — that lets clients choose their own isolation pool. Authoritative routing like this belongs to [IDS / identity services](../05-middleware/ids-governance.md) injecting it after authentication, or a trusted internal header `X-Selector-Sid` (requires a trusted client IP).
> - ⚠️ Use **low-cardinality** attributes for template values (tenant/version/region), not per-user IDs, or you'll thrash the service discovery cache.

---

## 4. Boundaries and pitfalls

### `rewrite` can't switch upstreams and doesn't re-match

It changes path/query **only within the matched route** and forwards straight to that route's upstream, without returning to the routing table. Any "choose the backend by X" must be written as "a route with condition X pointing at the target upstream"; don't expect rewrite to do it. For "fall back to a front controller for clean URLs" (WordPress/Laravel/SPA) use [`try_files`](../04-actions/serve.md).

### When several routes share a path, make the order explicit with `priority`

Routes are tried in a fixed order: higher explicit `priority` first; at equal priority, exact paths (`path:`) come before rule routes with extra conditions. So with one route using `path:` and another using `rule:`, and neither setting `priority`, the `path:` route matches first and the conditional rule never gets a chance. Fix: **give the more specific route an explicitly higher `priority`**. For the full order see [Named matchers and priority](../cookbook/06-matchers.md#3-which-route-matches-first-priority-rules).

### Query / header values used for matching must be single and trustworthy

- Query parameters used for value matching must have **exactly one value**; multiple values (such as `?v=a&v=b`) don't match, so the gateway and backend can't read different values.
- Be careful using `header` / `cookie` for **security** decisions: clients can forge them. Fine for canaries and A/B, but for permissions (such as the internal gate in 3.8) rely on `ClientIP` or backend authentication, with headers only as an aid.

### Templated `route_selector` / `route_meta` only for non-privileged dimensions

When filtering instances with `{cookie.x}` / `{header.x}` / `{query.x}` templates (see [3.9](#39-selecting-instance-subsets-by-request-attributes-service-discovery-subset-routing)), clients control the values. Use **non-privileged dimensions** (tenant/version/A-B/region) freely, preferably in `route_meta` (soft preference); **never** template **permission / physical isolation boundaries** (such as `sid`) from bare request attributes into `route_selector` — leave that to IDS injection after authentication or a trusted internal header. Also keep template values low-cardinality so the service discovery cache isn't thrashed.

### Rewriting the query can break signature checks

`rewrite.query` re-encodes and reorders the query string; if a third party verifies a signature over the original query bytes, verification fails. In that case change only the path, or have the backend read `{original_uri}` / `{original_path}`. See [Proxy `rewrite`](../04-actions/proxy.md#8-url-rewrite-rewrite).

---

## 5. In one sentence

> **match decides "to whom", rewrite decides "in what shape".** Split any tricky problem into these two questions: choose the right backend with `rule`'s boolean combinations, then adapt the URL with `rewrite`. Gateway-level routing, canaries, multi-version APIs, migrations and multi-tenancy are mostly within reach of this combination.

---

## Related docs

- [Single callback URL routing (one OAuth callback, several backends)](./oauth-single-callback.md)
- [Proxy and `rewrite` parameters](../04-actions/proxy.md#8-url-rewrite-rewrite)
- [Rule expression DSL reference](../03-configuration/site-config.md#9-rule-expression-dsl-reference)
- [Routing priority](../02-concepts/routing-priority.md)
