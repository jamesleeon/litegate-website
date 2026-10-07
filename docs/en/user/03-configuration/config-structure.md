# Configuration Structure and Best Practices

This page explains LiteGate configuration as a whole: which files exist, how each file is structured, what each level is responsible for, and how to organize configuration sensibly.

For field-by-field details see the references: [Global Configuration](global-config.md), [Site Configuration](site-config.md), [Named Services](services.md) and [Service Tags](tag-reference.md).

---

## 1. Where Configuration Comes From

LiteGate reads configuration from three kinds of sources, each with one job:

| Source | Location | Responsible for | Written by |
|---|---|---|---|
| **Global configuration** | `config.yaml` | The gateway process itself: ports, certificates, where services are discovered, logging and monitoring, trust boundaries | Gateway operators |
| **Site configuration** | `sites/*.yaml` | Routes of each domain: where a request goes, what processing it passes through, who responds | Gateway operators / application teams |
| **Service tags** | On services registered in Consul / LiteMesh / Docker / K8s | A service declares which domain and path it is exposed on | The services themselves |

`streams/*.yaml` configures layer-4 TCP/UDP forwarding; see [Stream Configuration](stream-config.md).

Typical layout:

```text
litegate/
├── config.yaml              # global configuration (one)
├── sites/                   # site configuration (one file per site)
│   ├── www.example.com.yaml
│   ├── api.example.com.yaml
│   └── blog.example.com.yaml
├── streams/                 # layer-4 forwarding (optional)
└── certs/                   # certificates (automatic or custom)
```

**Choosing a source:**

*   Stable listeners, certificates and security settings → `config.yaml`.
*   Domains and routes managed centrally by the gateway → `sites/*.yaml`.
*   Many services that come and go, and should declare their own routes → service tags.
*   Site files and service tags can target the same domain: for example, a site file serves the frontend with `serve` while backend services declare `/api` through tags. Both are merged into one site.

---

## 2. Global Configuration `config.yaml`

### 2.1 Structure

```text
config.yaml
├── mode                  runtime mode: observability (default) / performance
├── entrypoints           listeners: name → address, TLS or not
├── http                  legacy port and timeout settings (entrypoints take precedence)
├── tls / auto_cert       static certificates / automatic certificates
├── sites_dir             site configuration directory
├── streams_dir           layer-4 configuration directory
├── consul / litemesh     configuration or registry connections (optional)
├── service_discovery     discovery catalogs, ports that service tags may open
├── real_ip               trusted proxies: where the real client IP comes from
├── ip_restriction        global IP allow / deny lists
├── scan_protection       scan protection
├── auth_providers        OIDC / OAuth2 identity providers (referenced by routes)
├── dashboard / metrics / pprof / mcp    management and monitoring ports
├── log / tracing         logs, access logs, tracing
└── passive_health / cache / redis / ... other runtime parameters
```

The fields fall into five groups:

| Group | Fields | Purpose |
|---|---|---|
| Listeners | `entrypoints`, `http` | Which ports the gateway listens on. Sites and routes reference them by name |
| Certificates | `tls`, `auto_cert` | Where HTTPS certificates come from |
| Configuration sources | `sites_dir`, `streams_dir`, `consul`, `litemesh`, `service_discovery` | Where sites and services are read from |
| Security boundaries | `real_ip`, `ip_restriction`, `scan_protection`, `auth_providers` | Whom to trust, whom to reject |
| Operations | `dashboard`, `metrics`, `mcp`, `log`, `tracing` | Management and observability |

### 2.2 Recommended production configuration

```yaml
mode: observability

# Listeners: names are referenced by sites and tags; web / websecure are the defaults
entrypoints:
  web:
    address: ":80"
  websecure:
    address: ":443"
    tls: true

sites_dir: "./sites"
streams_dir: "./streams"

# Automatic certificates: enable once DNS points here and port 80 is reachable
auto_cert:
  enabled: true
  email: "ops@example.com"
  certs_dir: "./certs"
  default_challenge: "http"

# Required when a load balancer sits in front of the gateway; otherwise the
# client IP is the load balancer's address
real_ip:
  trusted_proxies:
    - "10.0.0.0/8"

# Service discovery: enable only the sources you use
service_discovery:
  catalogs:
    - enabled: true
      provider: "consul"
      url: "127.0.0.1:8500"
  tag_entrypoints:
    allowed_ports: []        # service tags may not open new ports by default

dashboard:
  enabled: true
  port: 9999
  username: "admin"
  password: "$2a$10$..."     # generate with `litegate -hash <password>`; never plain text

log:
  level: "info"
  format: "json"             # easier for log pipelines in production
  access_log:
    enabled: true
    stdout: true
```

Notes:

*   **Entrypoint names are the contract between sites and the global configuration.** Site `entrypoints` and tag `entrypoints` reference these names. For an internal management port, add a new entrypoint (e.g. `internal: { address: ":8080" }`) instead of changing `web` / `websecure`.
*   **`real_ip.trusted_proxies` lists only the proxies in front of the gateway.** A range that is too wide lets anyone forge `X-Forwarded-For` and bypass IP restrictions and rate limits.
*   **Enable only the discovery sources you need.** Every enabled source is scanned periodically.
*   **Leave `tag_entrypoints.allowed_ports` empty by default.** Service tags can then only attach to existing entrypoints, not open new ports.

---

## 3. Site Configuration `sites/*.yaml`

### 3.1 Syntax

New sites use the v2 syntax with a top-level `site:`. A simple site takes a few lines, and you add fields to the same file as you need more, without switching formats (full description in [Site Configuration](site-config.md), section 0):

```yaml
site: blog.example.com
/api: 127.0.0.1:8080
spa: /var/www/blog
```

The legacy `domain:` format and `.lite.yaml` files still load without migration. v2 compiles to the same internal model as the legacy standard format; the rest of this page explains each layer of that model. For the corresponding v2 field names (such as `site`, `https`, `transports`, and `use`), see [Site Configuration](site-config.md), section 0.

### 3.2 Structure

A site file has two parts: **definitions at the top, usage at the bottom.** The definitions give reusable things a name; the routes below reference them by name.

```text
site.yaml
│
├── domain                 site domain (required)
├── entrypoints            entrypoints the site is attached to (all by default)
├── force_https            redirect HTTP to HTTPS
├── tls                    custom certificate for this site (optional)
├── ip_restriction         site-wide IP rules (apply to every route)
├── max_request_body_size / error_pages / defaults   site-wide defaults
│
│ ── definitions: named, referenced by routes ──
├── serverstransports      upstream transport (TLS / mTLS)
├── services               backends: how to reach them (discovery, load balancing, timeouts, retries, circuit breaking)
├── middlewares            middleware: what happens on the way in and out (CORS, auth, rate limits ...)
│
│ ── usage ──
└── routes[]               route list
    ├── name               route name (shown in logs, the Dashboard and the pipeline)
    ├── priority           explicit priority (rarely needed)
    ├── match              where it goes: path / path_prefix / rule / method / header / query
    ├── ip_restriction     IP rules for this route
    ├── middlewares        names of middleware from the definitions, run by phase
    └── action             who responds
        ├── type           proxy / serve / template / respond / redirect / webdav / list / markdown / status
        ├── service        (proxy) a Service from the definitions
        ├── type fields    e.g. root / spa for serve, status / body for respond
        └── common fields  strip_prefix, headers, res_headers, log_level, on_error
```

**References:**

```text
routes[].middlewares    ──by name──▶  middlewares
routes[].action.service ──by name──▶  services ──references──▶ serverstransports
entrypoints             ──by name──▶  entrypoints in config.yaml
```

Every reference is checked at load time. A name that does not exist fails loading instead of going live broken.

### 3.3 A complete site

A common shape: a static frontend, several API backends and a redirect for old URLs.

```yaml
domain: shop.example.com
force_https: true

# ── definitions ─────────────────────────────────────────

serverstransports:
  mesh:
    tls:
      enabled: true
      clientcertificate: litemesh     # mutual TLS with the backends

services:
  orders:                             # instances found through service discovery
    discovery:
      name: orders
    timeout: 10s
    loadbalancer:
      strategy: least_conn
      serverstransport: mesh
    healthcheck: { path: /health, interval: 10s }
    retry: { attempts: 2 }
    circuitbreaker: { enabled: true, tripthreshold: 5 }

  payments:
    discovery:
      name: payments
      selector:
        match: { env: prod }          # production instances only
    timeout: 30s                      # payment callbacks are slow
    loadbalancer: { strategy: round_robin }

  legacy-cms:                         # an old system outside service discovery
    servers: ["http://10.0.3.21:8080", "http://10.0.3.22:8080"]
    timeout: 5s

middlewares:
  api-limit:
    type: ratelimit
    config:
      qps: "200"
  api-auth:
    type: jwt_auth
    config:
      jwks_url: "https://auth.example.com/.well-known/jwks.json"
  api-common:                         # a common bundle; routes reference one name
    type: chain
    config:
      middlewares: "api-limit,api-auth"

# ── usage ───────────────────────────────────────────────

routes:
  - name: orders-api
    match: { path_prefix: /api/orders }
    middlewares: [api-common]
    action:
      service: orders
      strip_prefix: /api

  - name: payments-callback           # third-party callback: no JWT, rate limited only
    match: { path: /api/payments/callback, method: [POST] }
    middlewares: [api-limit]
    action:
      service: payments
      strip_prefix: /api

  - name: payments-api
    match: { path_prefix: /api/payments }
    middlewares: [api-common]
    action:
      service: payments
      strip_prefix: /api

  - name: cms
    match: { path_prefix: /cms }
    action:
      service: legacy-cms

  - name: old-help                    # permanent redirect for old URLs
    match: { path_prefix: /help }
    action:
      type: redirect
      location: "https://help.example.com/"
      status: 301

  - name: frontend                    # catch-all: single-page app
    match: { path_prefix: / }
    action:
      type: serve
      root: /var/www/shop
      spa: true
      compress: true
```

Why it is organized this way:

*   **Each backend is defined once.** `payments` serves two routes; its timeout and load balancing live in the Service, and both routes share its health and circuit-breaker state.
*   **Middleware is named by purpose, and the common set is bundled with `chain`.** A new API route only needs `middlewares: [api-common]`.
*   **Frontend and API share one domain.** The browser sees a single origin, so calls to `/api/...` need no CORS.
*   **Special routes are more specific.** The payment callback uses an exact `path`, which naturally wins over the `/api/payments` prefix.
*   **The catch-all route is `/`.** Longest-prefix matching makes sure it only receives requests no other route matches.

---

## 4. Route Matching

### 4.1 `match` fields

| Field | Meaning | Example |
|---|---|---|
| `path` | Exact path | `path: /login` |
| `path_prefix` | Path prefix | `path_prefix: /api` |
| `method` | Method list | `method: [GET, POST]` |
| `header` | Request header equality | `header: { X-Tenant: acme }` |
| `query` | Query parameter equality | `query: { version: "2" }` |
| `rule` | Rule expression, exclusive with the fields above | `rule: 'PathPrefix("/api") && Method("GET")'` |

Note: YAML uses the singular **`method` / `header` / `query`**. The Dashboard and the JSON API show the plural forms; do not copy those into YAML.

### 4.2 Priority

When several routes match, the winner is decided in this order:

1.  Higher `priority` wins.
2.  An exact `path` wins over a prefix.
3.  A longer prefix wins (longest-prefix match).
4.  Routes from site files win over routes from service tags (only when the first three are equal).
5.  Otherwise, the order in the file.

`priority` is rarely needed; the specificity of the path gives the right result. Use it only when paths are identical, routes differ by `method` / `header`, and you want an explicit order.

**Note:** a route produced by service tags with a higher `priority` or a more specific path can override a site-file route on the same domain (for example by declaring `/login`). Only trusted services should be allowed to register in service discovery.

---

## 5. Where a Capability Belongs

The same need can often be written several ways. Recommended placement:

| Need | Recommended place | Not recommended |
|---|---|---|
| Backend addresses, load balancing, timeouts | `services` | Repeating `service_name` / `timeout` on several routes |
| Retries, circuit breaking, health checks | `services` | `retry` / `circuit_breaker` middleware (deprecated) |
| Upstream TLS / mTLS | `serverstransports` | `mtls` / `insecure_skip_verify` on every route |
| CORS, auth, rate limits, IP restriction | `middlewares`, referenced by routes | A separate inline copy on every route |
| A simple setting used by one route only | Inline action field (e.g. `compress: true`) | Defining a middleware just for it |
| Path rewriting | `strip_prefix` (drop a prefix) or `rewrite` (regex) | Adding path compatibility in the backend |
| Site-wide IP rules | Site `ip_restriction` | Repeating them on every route |
| Global IP deny list | `ip_restriction` in `config.yaml` | Repeating it in every site |

The rule of thumb is in [Named Services and Configuration Layers](services.md), section 1: **settings that need to know the backend belong to the Service; settings that do not are middleware.**

Whatever order they are listed in, middleware runs in fixed phases: preflight (CORS) → request rewriting → security (IP, WAF) → traffic control (rate limits) → authentication → post-auth (mirroring) → response (compression, caching). So there is no need to worry about "rate limit before or after auth". Within a phase, middleware is ordered by its type's built-in order first, then by the order written.

---

## 6. Recommended Practices

**File organization**

*   **One site per file, named after the domain.** The file name leads straight to the configuration when troubleshooting. A file may hold several sites separated by `---`, but that is harder to maintain.
*   **Definitions at the top, routes at the bottom.** Readers first see which backends and middleware exist, then how routes combine them.
*   **Give every route a `name`.** Route names appear in access logs, the Dashboard and the pipeline; unnamed routes are hard to troubleshoot.

**Backends**

*   **Always use a Service when several routes share a backend.** Otherwise a timeout change must be made in several places, and missing one makes the same backend behave differently.
*   **Set timeouts per backend, not per route.** Define a separate Service for slow endpoints (like `payments` above).
*   **Retry only idempotent requests.** Only idempotent methods are retried by default; do not add POST to `retry_methods` unless the backend guarantees idempotency.

**Middleware**

*   **Name by purpose**, e.g. `api-limit`, `web-cors`, `admin-auth`, not `mw1`.
*   **Bundle common sets with `chain`.** Changing the security policy of a group of routes then takes one edit.
*   **Prefer a single domain.** With the frontend and the API on the same domain, no CORS is needed. When cross-origin access is required, list explicit origins in `allowed_origins`; `*` combined with credentials fails to load.

**Security**

*   **Configure `real_ip.trusted_proxies` whenever the gateway sits behind a load balancer.**
*   **Use a hash generated by `litegate -hash` for the Dashboard password**, and do not expose the Dashboard port to the internet.
*   **Add `ip_restriction` to management routes** so that only the internal network can reach them.
*   **Open `tag_entrypoints.allowed_ports` one port at a time**; do not open a whole range for convenience.

**Verification before going live**

*   The startup log shows no errors and no deprecation warnings.
*   Check the pipeline of each key route in the Dashboard: `GET /api/routing/pipeline?site=<domain>&route=<route name>`, and confirm the middleware order and sources are as expected.

---

## 7. Common Mistakes

| Mistake | Problem | Instead |
|---|---|---|
| `methods: [GET]` | The YAML key is singular `method`; the key is rejected | `method: [GET]` |
| `timeout: 5s` on an action | The inline action `timeout` is an integer number of seconds | Inline `timeout: 5`; in a Service `timeout: 5s` |
| `max_requests` in a Service | Service keys follow the tag spelling | `maxrequests`, `tripthreshold` |
| Referencing a Service and also setting `timeout` / `retry` | A route's backend has one source of configuration; loading fails | Configure it on the Service |
| `allowed_origins: "*"` with `allow_credentials: true` | Any website could read the API as the user; loading fails | List trusted origins |
| Frontend and API on different domains, then CORS everywhere | Complex and error-prone | Serve both from one domain, separated by path |
| CORS configured in both the backend and the gateway | Two policies may disagree, and it is unclear which applies | Once the gateway configures CORS it owns those headers; pick one |
| `priority` on the catch-all `/` route | It overrides more specific routes | No `priority` on the catch-all route |
| `retry` middleware | Deprecated | `services.<name>.retry.attempts` |

---

## Further Reading

- [Global Configuration Reference](global-config.md)
- [Site Configuration Reference](site-config.md)
- [Named Services and Configuration Layers](services.md)
- [Service Tags Guide](tag-dsl.md)
- [Routing Priority](../02-concepts/routing-priority.md)
