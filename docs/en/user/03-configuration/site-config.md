<!-- GENERATED FILE — DO NOT EDIT.
     Source: internal/configdocs/docs/en/site-config.md (package internal/configdocs)
     Regenerate: go generate ./internal/configdocs/...
     Edit the source instead; a drift test fails if this copy is edited directly. -->

# Site configuration reference (`sites/*.yaml`)

Each site is one YAML file, by default under `./sites`. LiteGate scans that directory and hot-reloads on change.

> [!TIP]
> MCP's `get_config_guide` returns this file verbatim. The fields here must stay in step with `internal/loader/types.go`.

---

## 0. Unified site YAML (v2, default for new configurations)

Create new sites as `.yaml` with a top-level `site:`. Users no longer need to choose Lite or standard mode. `version: 2` is optional: `site` identifies v2, `domain` identifies legacy standard YAML, and legacy `.lite.yaml` domain mappings remain supported. All documents in a file must use the same format. Existing files require no migration.

AI tools should generate v2 for new sites and preserve the format when editing existing files. `litegate -t -config config.yaml` checks all three formats through the common Loader. v2 defaults `https` to false; explicit true or false takes precedence. Creation tools preserve their previous HTTPS choices.

```yaml
site: api.example.com
proxy: localhost:8080, 192.168.50.110:8088
```

A frontend with an API proxy uses path-segment prefixes and a site-level fallback:

```yaml
site: app.example.com
response_headers:
  X-Frame-Options: DENY
/api:
  proxy: localhost:8080
  strip_prefix: true
  cache: {ttl: 30s}
spa: ./dist
```

- Use `serve: ./public` for static files and `spa: ./dist` for an SPA. Single-action shorthands include `respond: ok` and `redirect: https://example.com`.
- Proxy scalars/lists always contain addresses; commas separate multiple addresses. Reference a defined local Service using `service: orders` or `proxy: {service: orders}`. Advanced discovery/connection settings can retain internal fields under `action`; a discovery name is not a proxy address.
- Use `routes` with `match` for exact paths and method/header/query/rule combinations. Path-key routes cannot also specify match. Advanced action fields remain available under `action`.
- `use` references defined middleware. Site request_headers apply only to proxies; response_headers apply to every action. Route header values override site values.
- With child routes, put root authentication/rate limiting in an explicit `/` route; use site use for middleware covering all routes. Boolean true and string "true" strip_prefix both require prefix matching.
- MCP enable_jwt/apikey/oidc_for_site tools support single-document v2 and legacy standard sites. v2 edits proxy route AST nodes while retaining comments and shorthand; repeated calls do not duplicate bindings. JWT/API Key update same-name definitions and reject type conflicts; OIDC updates route remote_auth. Static/SPA routes receive no new authentication. Use full YAML editing, validation and saving for legacy Lite or multi-document files.

The following root/match/action tables describe the internal model and legacy standard format. v2 uses `site`, `https`, `transports` and `use` instead of legacy `domain`, `force_https`, `serverstransports` and route `middlewares`. Do not copy a legacy root example unchanged into v2.

### Listener port shorthand

`site: :9090`, `site: "*:9090"`, and `site: 0.0.0.0:9090` are equivalent to `site: "*"` plus `port: 9090`, accepting any HTTP Host on that port. YAML values starting with `*` require quotes. Ports range from 1–65535; do not also set `port` or `entrypoints`. `site: example.com:9090` matches that hostname on the port; use `[::1]:9090` for IPv6 with a port. The host selects requests, not the local network interface to bind. `https` still defaults to false.

```yaml
site: :9090
proxy: 127.0.0.1:8080
```

### Case-insensitive path prefixes

`/goapi:` is case-sensitive; `~/goapi:` is case-insensitive. Both match path segments: the latter matches `/goapi`, `/GoApi`, and `/GOAPI/orders`, but not `/goapix` or `/other/goapi`. This is not regex syntax; use routes/match.rule for regex. `strip_prefix: true` removes the actual matched prefix while preserving the remaining path's case.

`~/` guarantees case-insensitive matching for ASCII paths only. Middleware references are deduplicated across inherited and imported declarations; duplicates within one `use` declaration are errors. The same prefix cannot be declared using both `/path` and `~/path`.

```yaml
site: :9090
~/goapi:
  proxy: 127.0.0.1:8080
  cors:
    allowed_origins: ["*"]
    allowed_methods: [GET, POST, OPTIONS]
    allowed_headers: ["*"]
    max_age: 1728000
```

### file_server alias

Path keys also accept a proxy address directly, equivalent to a `proxy` field under that path:

```yaml
site: :9090
~/goapi: 127.0.0.1:8080
spa: ./www
```

API requests preserve their paths when forwarded; other paths use the SPA. Ordinary `/api` keys also support this shorthand. Use a mapping with `proxy` when adding route options such as `strip_prefix: true`.

`file_server` aliases `serve`, accepting a directory string or an object, including under path keys and routes lists. Specify the directory explicitly. Do not combine file_server, serve, spa, or other terminal actions on the same route. Keep using spa for Vue/React SPA shorthand. Generic `action: {type: file_server, root: ./public}` also compiles to serve.

```yaml
site: example.com
file_server: /www/example.com
```

```yaml
site: localhost
file_server: {root: ./www, index: index.html}
/api:
  proxy: localhost:9001
```

### PHP websites (WordPress / Laravel)

The `php` action combines PHP-FPM, static files, directory indexes and front-controller fallback:

```yaml
site: example.com
https: true
compress: true
php:
  root: /var/www/wordpress
  upstream: unix:///run/php/php8.3-fpm.sock
  deny_scripts: [/wp-content/uploads]
  keep_conn: true
  max_idle_conns: 16
  idle_timeout: 60
```

Use the actual PHP-FPM socket path, `fastcgi://127.0.0.1:9000`, or an address list. PHP-FPM runs separately; both processes must have access to the same website files. Use TCP on Windows.

By default, requests check the requested file, a directory's `index.php`, then its `index.html`, and finally `/index.php`. PHP scripts and PATH_INFO go to PHP-FPM; both PHP and HTML directory indexes receive a trailing-slash redirect preserving the query. Front-controller fallback preserves the original `REQUEST_URI`, query and request body. Explicit requests for nonexistent PHP scripts return 404 and never serve PHP source as static content.

Optional fields: `index` (default `index.php`, must be a PHP file), `try_files` (default `["{path}", "{path}/index.php", "{path}/index.html", "/index.php"]`), `timeout` (seconds), `keep_conn`, `max_idle_conns`, `idle_timeout` (seconds), and `params` (additional CGI variables). `try_files` checks regular files within root in order, executes PHP candidates through PHP-FPM, and returns 404 when none exists. Set `try_files: ["{path}", "{path}/index.php", "{path}/index.html"]` to retain directory indexes while disabling root front-controller fallback.

Keep `deny_scripts` in production WordPress configurations. High-concurrency deployments can enable `keep_conn`, which is off by default. The example retains up to 16 idle connections and reclaims them after 60 seconds; adjust these values for PHP-FPM worker counts and actual load.

Common PHP source backup suffixes return 404, case-insensitively: `.php~`, `.php.bak`, `.php.old`, `.php.orig`, `.php.backup`, `.php.save`, `.php.swp`, `.php.swo`, `.php.tmp`. Hidden files remain blocked by static serving rules. Ordinary static resources containing `.php`, such as `prism.php.min.js` and `syntax.php.css`, remain accessible. These rules do not detect every possible backup name; keep other backups outside the website root.

Use `php` at site level, under a path key, or in `routes`. Each route accepts one terminal action. Set `strip_prefix: true` explicitly to remove a mounting prefix; the application must also support that deployment prefix. With child routes, put root governance such as compression on an explicit `/` route.

**Disable script execution in uploads**: set `deny_scripts: [/wp-content/uploads]` under `php`. No directories are denied by default. Configured directories reject PHP scripts, PATH_INFO and PHP directory indexes with 403 while allowing static resources. Entries start with `/`, are relative to `root`, and match case-insensitively on directory boundaries; `/wp-content/uploads-extra` remains accessible. Checks happen after stripping a mounting prefix and also cover resolved in-root symlink targets and scripts selected by custom `try_files`.

**TLS termination at a load balancer**: configure the actual proxy IPs or CIDRs in global `config.yaml`, for example `real_ip: {trusted_proxies: ["192.0.2.10/32"]}`. This is global configuration, not site YAML.

A direct trusted peer supplying a single `X-Forwarded-Proto: https` value causes PHP to receive `HTTPS=on` and, without an explicit Host port, `SERVER_PORT=443`. `https: true` also avoids redirecting this request again. Untrusted sources, repeated values and comma-separated protocol chains are not accepted. The proxy should overwrite this header with the actual client protocol. This applies to lower-level FastCGI proxy actions too.

**Subpath mapping**: `php` preserves the URL path by default, while `file_server` automatically strips the matched route prefix. For route `/blog`, root `/var/www` and request `/blog/x`:

| Configuration | Physical path |
|---|---|
| `php: {root: /var/www, upstream: ...}` | `/var/www/blog/x` (like Nginx root) |
| `strip_prefix: true` + `php: {root: /var/www, upstream: ...}` | `/var/www/x` |
| `file_server: /var/www` | `/var/www/x` (like Nginx alias) |

PHP's static files and scripts use the same mapping. The default `/index.php` fallback is always relative to `root`; explicitly configure `try_files` to use `/blog/index.php` as a mounted application's front controller.

### Configuration fragments: snippets / import

Define document-local route governance under top-level `snippets`, and expand it with `import` at a site or route. `import` accepts a name or list of names. Fragments have no parameters or file/KV imports; `sites/_shared.yaml` shares snippets across sites. It reuses configuration, without changing runtime middleware, rate-limit, or load-balancing state scopes.

Fragments accept governance fields such as cors, auth, compress, strip_prefix, use, request_headers, and response_headers. They cannot define site, port, match, routes, terminal actions, or services/transports/middlewares resources. Declare proxy/service and actions at the use site. Nested imports are supported; cycles, missing references, duplicate references, and expansion limits are errors.

Merge rules:

- Repeated ordinary governance fields are errors even when equal. No deep merging of auth/cors objects or silent local overrides.
- request_headers / response_headers merge by case-insensitive header name. Local values win; conflicting headers from sibling imported fragments are errors.
- use references at one import location merge in declaration order and deduplicate. Existing site/route inheritance and duplicate-binding validation still apply.
- With child routes, imported root governance such as cors/auth belongs in an explicit `/` route. Site-level use and response headers retain inheritance.

Source files retain snippets/import and comments; runtime compilation uses independent expanded nodes. Errors preserve definition locations; compile diagnostics also identify the snippet and import location. Unused definitions are checked for fields, types, references, and cycles; business semantics are validated on effective routes. Loader exposes `ExpandSiteV2Document` for effective AST inspection.

```yaml
site: localhost
snippets:
  public-api:
    cors:
      allowed_origins: ["*"]
      allowed_methods: [GET, POST, OPTIONS]
      allowed_headers: ["*"]
    response_headers:
      X-Frame-Options: DENY
    compress: true
/goapi:
  import: public-api
  proxy: localhost:9001
/userapi:
  import: public-api
  response_headers:
    X-Service: users
  proxy: localhost:9002
```

### v2 backends and transports

`proxy` objects and named `services` accept `to`, `servers`, `discovery`, `resolver`, `timeout`, `retry`, `lb` / `loadbalancer`, `health` / `healthcheck`, and `circuitbreaker`. `servers` aliases `to`; using both is an error. Static addresses and discovery are mutually exclusive. Use `service` for a named reference.

`retry: 2` means `retry: {attempts: 2}`; `health: /health` means `healthcheck: {path: /health}`; `lb: least_conn` means `loadbalancer: {strategy: least_conn}`; `discovery: orders` means `discovery: {name: orders}`. Do not combine health/healthcheck or lb/loadbalancer. Apart from these aliases, object fields retain the service-label hierarchy.

Define top-level `transports` and reference them through backend `loadbalancer.serverstransport`. Backend `transport` is unsupported.

```yaml
site: shop.example.com
transports:
  mesh:
    tls: {enabled: true, insecureskipverify: false}
services:
  orders:
    to: [https://127.0.0.1:8080]
    timeout: 500ms
    retry: 2
    health: /health
    loadbalancer: {strategy: least_conn, serverstransport: mesh}
/orders:
  service: orders
/api:
  proxy: {to: localhost:8080, timeout: 2s, retry: 2, lb: least_conn, health: /health}
```

### Legacy fields versus v2

| Legacy field | v2 syntax |
|---|---|
| domain / force_https | site / https |
| serverstransports / route middlewares | transports / use (string or list) |
| headers / res_headers | request_headers / response_headers |
| enable_tracing | tracing |
| proxy_cache / proxy_cache_ttl / proxy_cache_key | cache: {enabled, ttl, key} |
| Route upstream / timeout | proxy: {to, timeout} |
| fastcgi_*, insecure_skip_verify, host, sticky_* and advanced fields | action: {type: proxy, ...} |
| action: {service: x} | service: x or proxy: {service: x}; generic action requires type |

Sections 1–9 describe legacy standard YAML and the internal model. Do not copy their route fields directly into v2.

## 0.1 Legacy Lite mode (still supported)

When manually rewriting Lite as v2, explicitly set `https: true` to retain HTTP→HTTPS redirects: Lite defaults to true, while v2 defaults to false. Existing Lite files need no migration.

The following legacy Lite examples are retained for existing files. Use unified v2 for new configurations.
Name the file `.lite.yaml` (for example `example.com.lite.yaml`) and the structure collapses dramatically, with no deep nesting. New configurations no longer default to this format.

The idea: **the top-level key is the domain; the keys under it are paths (starting with `/`) or site-wide properties.**

### Lite reverse proxy
```yaml
api.example.com:
  /v1:
    proxy: 127.0.0.1:8080
  /v2:
    proxy: 127.0.0.1:8081
```

### Lite SPA and static assets
```yaml
docs.example.com:
  /:
    root: /var/www/html
    spa: true
  /images:
    root: /var/www/images
```

### Directives lite mode supports
Under a route path (below `/xxx:`), lite mode supports these shortcuts:
- `proxy`: upstream address to reverse-proxy to (e.g. `127.0.0.1:8080`)
- `root`: directory to serve static files from
- `spa`: boolean; with `root` present, enables single-page-app fallback routing
- `redirect`: redirect target URL
- `respond`: return this static text directly
- `headers`: inject request headers (map)
- `res_headers`: override response headers (map)

The following may **only appear at site level** (directly under the domain). Written into a route they are rejected outright, because `LiteRoute` is decoded strictly with KnownFields:
- `webdav`: directory to serve WebDAV from
- `https`: boolean; disables the forced HTTPS redirect (default true)
- `entrypoints`: the listeners this site binds to

Within one route the actions are mutually exclusive — only one takes effect, in the order `proxy` > `root` > `respond` > `redirect`.

### Site-level actions
Lite mode lets you omit the `/` and hang a directive directly on the domain.
```yaml
simple.example.com:
  https: false               # disable the forced HTTPS redirect (default true)
  proxy: 127.0.0.1:3000      # same as configuring proxy under /
  headers:
    X-Forwarded-App: legacy  # sent upstream by proxy only; not a security response header
```

Legacy Lite site headers are inherited by every route beneath. For new sites, unified v2 provides route governance and the action escape hatch for advanced features.

---

## 1. Root fields (standard mode)

```yaml
domain: "example.com"          # Required. The site's domain
entrypoints: ["web", "websecure"] # Optional. Listeners to bind to (empty binds to all of them)
port: 0                        # Optional. A dedicated port for this site; 0 uses the global listeners
force_https: true              # Optional. Redirect HTTP to HTTPS automatically
connect_override: home         # Optional. Allow this Connect peer to take over the same exact hostname
description: "User Center"        # Optional. Site description
disable_trace_id: false        # Optional. Suppress X-Trace-Id injection

# Optional. Custom certificate and key paths; once set this certificate is used instead of global auto-issuance
tls:
  enabled: true
  cert_file: "./certs/example.com.crt"
  key_file: "./certs/example.com.key"

defaults:
  timeout: 30                  # Optional. Default timeout, in seconds

ip_restriction:
  allow_ips: ["192.168.0.0/16"]
  deny_ips: []

# Middleware definitions (optional)
middlewares:
  limit-10:
    type: "ratelimit"
    config:
      qps: "10"
  strip-api:
    type: "strip_prefix"
    config:
      prefixes: "/api"

routes:
  - name: "default"
    match:
      path_prefix: "/"
    action:
      type: "proxy"
      upstream: ["127.0.0.1:8080"]
```

`connect_override` supports zero-downtime migration of an existing Cloud Site to LiteGate Connect. It must name a configured `connect.server.peers` entry and is valid only for an exact DNS hostname. The local route remains active until that peer registers the same hostname; after takeover, an offline peer remains fail-closed and does not fall back to the local upstream.

Field reference:

| Field | Type | Description |
| :--- | :--- | :--- |
| `domain` | string | Required. The site's domain |
| `entrypoints` | string[] | Optional. Names of the global listeners to bind to (e.g. `["web", "websecure"]`); empty binds to all of them |
| `port` | int | Optional. A dedicated listening port for this site |
| `force_https` | bool | Optional. Redirect HTTP to HTTPS automatically |
| `description` | string | Optional. Site description |
| `disable_trace_id` | bool | Optional. Suppress the `X-Trace-Id` response header |
| `tls` | object | Optional. Custom (purchased) TLS certificate configuration |
| `tls.enabled` | bool | Required when using a custom certificate. Enables this site's own TLS certificate |
| `tls.cert_file` | string | Required when using a custom certificate. Path to the certificate file (e.g. `./certs/example.crt`) |
| `tls.key_file` | string | Required when using a custom certificate. Path to the private key (e.g. `./certs/example.key`) |

> Note: with `tls` enabled, the domain matches by exact SNI and uses **only** this certificate — it no longer falls back to global automatic issuance, and a missing or unloadable certificate fails the handshake outright. The certificate is read when the site configuration reloads, so after a renewal you must save the configuration again. A global HTTPS listener still has to be enabled for any of this to apply.
| `defaults.timeout` | int | Optional. Default timeout in seconds |
| `ip_restriction` | object | Optional. Site-level IP allow/deny list |
| `middlewares` | map | Optional. Middleware definitions (like Traefik's middlewares) |
| `services` | map | Optional. Named Service definitions, referenced by routes with `action.service` (see section 4) |
| `serverstransports` | map | Optional. Upstream transport settings (TLS / mTLS) referenced by services |
| `routes` | array | Required. The route list |

---

### Forward-only sites

A Forward site does not need `routes`. Its hostname binds one server-selected internal
target that clients cannot override. Tokens must be at least 32 bytes; `token_file` is
recommended in production. A target may be a dedicated L4/SOCKS5 Stream, a local L7
Site, or a remote service registered through Connect.

```yaml
domain: forward.example.com
forward:
  target:
    type: stream # stream, site, or connect
    name: rds-mysql
  token_file: /etc/litegate/secrets/forward.token
```

The legacy `stream: rds-mysql` spelling remains supported and is equivalent to
`target.type: stream`. For local Sites and Connect-published L7 Sites, every tunneled
request is authority-bound to `target.name`, so one Forward token cannot reach another Site.

`entrypoints` may be omitted. When the global configuration has no explicit entrypoints, LiteGate still synthesizes `websecure` from `http.https_port`. Forward itself requires WSS/TLS. Set `entrypoints: [websecure]` only when multiple entrypoints exist and the site must be restricted to that one.

Public connections use WSS at `/_litegate/forward/v1`. The hostname must be covered
by an existing HTTPS certificate; for example, `*.example.com` covers
`forward.example.com`.

## 2. Routes

`routes` match in order, but when several overlap — with a complex `rule` DSL, say — `priority` controls the matching order precisely.

```yaml
routes:
  - name: "api-v1"
    priority: 100                 # Optional. Match priority; higher matches first
    match:
      path_prefix: "/api/v1"
      method: ["GET", "POST"]
      header:
        X-Env: "staging"
    middlewares: ["limit-10"]      # reference a middleware
    ip_restriction:
      deny_ips: ["1.2.3.4"]
    action:
      type: "proxy"
      upstream: ["127.0.0.1:8080"]
```

### Route fields

| Field | Type | Description |
| :--- | :--- | :--- |
| `name` | string | Required. Unique route identifier |
| `priority` | int | Optional. Match priority (default `0`; with mixed matching or the Rule DSL, higher wins) |
| `match` | object | Required. Path and condition matching block |
| `middlewares` | string[] | Optional. Middleware names to attach |
| `ip_restriction` | object | Optional. Route-specific IP allow/deny list, overriding the site-level one |
| `action` | object | Required. What to do when the route matches |

### The `match` block

| Field | Type | Description |
| :--- | :--- | :--- |
| `path_prefix` | string | Prefix path match, e.g. `/api` |
| `path` | string | Exact path match, e.g. `/health` |
| `rule` | string | Expression rule (Caddy/Traefik-style DSL), e.g. `Host("a.com") && PathPrefix("/api")` |
| `method` | string[] | Restrict to these HTTP methods, e.g. `["GET", "POST"]` |
| `header` | map | Header key/value conditions the request must satisfy |

### Route-level `ip_restriction`

| Field | Type | Description |
| :--- | :--- | :--- |
| `allow_ips` | string[] | IPs or CIDRs allowed through this route |
| `deny_ips` | string[] | IPs or CIDRs blocked from this route |

---

## 3. Common action fields

Every `action` type supports the following:

| Field | Type | Description |
| :--- | :--- | :--- |
| `type` | string | Required. Built in: `proxy`, `serve`, `respond`, `redirect`, `block`, `list`, `webdav`, `markdown`, `template`, `status` |
| `headers` | map[string]string | Request header injection (when proxying) or response headers (in some cases) |
| `res_headers` | map[string]string | Override upstream response headers |
| `rate_limit` | float64 | QPS rate limit |
| `rate_limit_policy` | string | `static` or `adaptive` |
| `auth` | object | Basic / JWT authentication |
| `cors` | object | CORS configuration |
| `waf` | object | WAF configuration |
| `circuit_breaker` | object | Circuit breaker configuration |
| `ids` | object | Unified control engine / OIDC / remote authorization |
| `remote_auth` | object | Remote authorization / OIDC (backwards compatible) |
| `route_selector` | map[string]string | Multi-tenant or multi-dimensional route selection |
| `route_tags_header` | string | Explicitly enable a client route-tag request header; unset, the default header is only honoured for trusted selector clients |

> [!NOTE]
> Validator requirements:
> - `proxy` must set either `upstream` or `service_name`
> - `serve` / `webdav` / `markdown` must set `root`

---

## 4. Proxy

```yaml
action:
  type: proxy
  namespace: "default"
  upstream_type: static            # Optional. Common values: static / consul / litemesh / external
  upstream: ["127.0.0.1:8080"]
  service_name: "order-api"
  service_tag: "v2"
  host: "backend.internal"
  proto: "http"                    # http / https / ws / wss / fastcgi / grpc
  insecure_skip_verify: false
  strip_prefix: "/api"
  prepend_prefix: "/gateway"
  timeout: 30
  retry: 0
  disable_chunked: false
  lb_policy: round_robin
  prefer_h2: false
  mtls: false
  flush_interval: 0
  
  # Governance and observability parameters (optional)
  gray_weight: 10                  # canary weight (10 sends 10% of traffic to this route)
  log_level: "info"                # per-route log level override
  enable_tracing: true             # enable distributed tracing for this proxy path

  health_check:
    enabled: true
    path: "/health"
    interval: 10s
    timeout: 3s
  route_selector:
    sid: "{head.X-Tenant-ID}"
  route_tags_header: "X-LiteGate-Tags"
```

### Fast HTTP/1.1 upstream client (`upstream_client`)

On by default and normally needs no configuration: when the backend is plain HTTP/1.1 (no TLS, gRPC or HTTP/2), the proxy uses a synchronous connection pool that lowers the CPU cost of each request; other backends automatically use the standard client. Set the field only to turn it off or to enforce it. A site value applies to every proxy route of the site, a route value overrides it, and changes take effect on site hot reload:

```yaml
site: api.example.com
/api:
  proxy: 10.0.0.11:8080, 10.0.0.12:8080
/legacy:
  proxy: 10.0.0.13:8080
  upstream_client: standard     # off: this route always uses Go's net/http Transport
/orders:
  proxy: 10.0.0.14:8080
  upstream_client: fast         # enforced: this route must be able to use the fast client, or the site fails to load
```

- The default and a site-level `fast` mean "use it where possible": `https://`, `grpc`, `prefer_h2` and mTLS/TLS routes quietly keep the standard client. A route-level `fast` is strict and those configurations fail to load; discovered endpoints are only known at runtime and fall back with one warning logged per endpoint.
- To turn it off globally: `http.upstream_client: standard` in `config.yaml`.
- WebSocket and other protocol upgrades keep using the tunnel path.
- A few requests still go to the standard client so behaviour stays identical: `Expect: 100-continue`, request trailers, and request bodies of unknown length or over 64KB.
- To confirm what is used: the metric `litegate_upstream_client_requests_total{route, client, fallback}` counts `client=fast/standard` and the fallback reason per route; a trusted request with `X-LiteGate-Debug: true` gets the response header `X-LiteGate-Upstream-Client` set to `fast` or `standard; fallback=<reason>`.

### FastCGI proxying

For PHP-FPM and other FastCGI backends:

```yaml
action:
  type: proxy
  upstream_type: static
  proto: "fastcgi"                 # must be fastcgi
  fastcgi_root: "/var/www/html"    # Required when proto is fastcgi. The backend's document root
  fastcgi_split_path: ".php"       # Optional. Suffix splitting script from PATH_INFO, default ".php"
  fastcgi_extensions: [".php"]     # Optional. Allow-list of executable extensions, default [".php"]. "*" allows all, with the obvious risk
  fastcgi_params:                   # Optional. Extra CGI environment variables passed to PHP-FPM
    APP_ENV: production
    REDIRECT_STATUS: "200"
  fastcgi_keep_conn: true          # Optional. Reuse pooled connections, default false
  fastcgi_max_idle_conns: 10       # Optional. Maximum idle connections kept in the pool, default 2
  fastcgi_idle_timeout: 60         # Optional. Idle connection reclaim timeout in seconds; 0 means never
  upstream:
    - "fastcgi://127.0.0.1:9000"   # a backend addressed over TCP
    # or a Unix socket:
    # - "unix:///var/run/php-fpm.sock"
```

Field reference:

| Field | Type | Description |
| :--- | :--- | :--- |
| `namespace` | string | Optional. Upstream namespace |
| `upstream_type` | string | How the upstream is resolved |
| `upstream` | string[] | Static upstream list |
| `service_name` | string | Service discovery name |
| `service_tag` | string | Service tag |
| `host` | string | Override the request Host |
| `proto` | string | Upstream protocol |
| `fastcgi_root` | string | FastCGI only. The backend's document root. Required when `proto` is `fastcgi`. |
| `fastcgi_split_path` | string | FastCGI only. Suffix splitting the script path from PATH_INFO (e.g. `.php`). Defaults to `.php`. |
| `fastcgi_extensions` | string[] | FastCGI only. Allow-list of script extensions executable over FastCGI (e.g. `[".php"]`). Defaults to `[".php"]`. `["*"]` permits any extension, which risks arbitrary file execution if PHP-FPM is misconfigured. |
| `fastcgi_params` | map[string]string | FastCGI only. Extra CGI environment variables such as `APP_ENV` and `REDIRECT_STATUS`; cannot override path, request or built-in `HTTP_*` variables. |
| `fastcgi_keep_conn` | bool | FastCGI only. Reuse pooled connections to the backend. Defaults to `false`. |
| `fastcgi_max_idle_conns` | int | FastCGI only. Maximum idle connections in the pool (default `2`, cannot be negative). |
| `fastcgi_idle_timeout` | int | FastCGI only. Idle connection reclaim timeout in seconds (default `0`, meaning never; cannot be negative). |
| `insecure_skip_verify` | bool | Skip TLS verification. Note: under `mtls: true` the certificate chain and SPIFFE identity are still verified strictly even with this set — it only emits a warning and cannot be bypassed, which keeps the zero-trust guarantee intact. |
| `strip_prefix` | string | Remove this path prefix before forwarding |
| `prepend_prefix` | string | Prepend this path prefix before forwarding |
| `timeout` | int | Timeout in seconds |
| `retry` | int | Retry count, cannot be negative; non-idempotent requests are retried only when the request is known not to have been sent |
| `retry_on_status` | int[] | Optional. Upstream status codes that trigger failover and retry (e.g. `[502, 503, 504]`) |
| `retry_methods` | string[] | Optional. HTTP methods allowed to retry (e.g. `["GET", "HEAD"]`; idempotent methods only by default) |
| `passive_failure_status` | int[] | Optional. Status codes counted against passive health and outlier ejection (e.g. `[500, 502, 503, 504]`) |
| `xff_mode` | string | Optional. X-Forwarded-For handling: `transparent` (pass through untouched) or `boundary` (sanitize at the boundary) |
| `disable_chunked` | bool | Disable chunked transfer; buffers the body to compute its length and returns 413 above 2 MiB |
| `lb_policy` | string | Load-balancing policy: `round_robin`, `ip_hash`, `weighted_round_robin`, `p2c` (power-of-two-choices over in-flight requests and latency), `least_conn`, `cookie` (session affinity) |
| `prefer_h2` | bool | Prefer HTTP/2 |
| `upstream_client` | string | Follows the global `http.upstream_client` (default `fast`: synchronous pool for plaintext HTTP/1.1 upstreams, standard client for the rest); `standard` turns it off; a route-level `fast` is strict. See below |
| `mtls` | bool | Enable mTLS |
| `flush_interval` | int | Flush interval; `-1` flushes immediately |
| `gray_weight` | int | Optional. Share of traffic for this canary route (0 - 100) |
| `log_level` | string | Optional. Per-route access-log level override (`none` / `error` / `warn` / `info` / `debug`); applies to every action type |
| `enable_tracing` | bool | Optional. Always sample and export this route's edge span (ignores `sample_ratio`); requires global `tracing.enabled` |
| `health_check` | object | Health check configuration |

### Caching, rewriting, session affinity, concurrency limits and gRPC

All of these go on a proxy route's `action`:

```yaml
action:
  type: proxy
  upstream: ["127.0.0.1:8080"]

  # Reverse-proxy content cache
  proxy_cache: true
  proxy_cache_ttl: 30              # cache seconds, default 10; also honours upstream Cache-Control, taking the shorter
  proxy_cache_key: "{host}:{uri}:{header.Accept-Language}"  # optional; {uri} includes the query string, {path} does not

  # URL regexp rewrite (runs before auth / WAF / rate limiting)
  rewrite:
    pattern: "^/old/(.*)$"
    target: "/new/$1"

  # Cookie session affinity
  lb_policy: cookie                # others: round_robin / ip_hash / weighted_round_robin / p2c / least_conn
  sticky_cookie_name: "LG_STICKY_BACKEND"   # optional, this is the default
  sticky_cookie_ttl: 1800                    # optional, seconds, default 1800

  # Concurrency limit
  limit_conn: 100
  limit_conn_key: "ip"            # "ip" limits per client IP; empty limits the route as a whole

  # First-class gRPC: proto: grpc (cleartext h2c; with mtls:true it upgrades to grpcs / TLS)
  proto: grpc
```

| Field | Type | Description |
| :--- | :--- | :--- |
| `proxy_cache` | bool | Enable content caching. Automatically bypassed for requests carrying `Authorization`/`Cookie`, responses with `Set-Cookie`/`private`, unknown `Vary` dimensions, non-GET/HEAD methods, and WS/gRPC/SSE |
| `proxy_cache_ttl` | int | Cache lifetime in seconds, default 10 |
| `proxy_cache_key` | string | Custom cache-key template supporting `{host}`/`{uri}` (with query string)/`{path}`/`{method}`/`{header.X}` |
| `rewrite.pattern` / `rewrite.target` | string | Go regexp rewrite of `URL.Path`, `$1` referencing a capture group; does not re-run route matching |
| `lb_policy: cookie` | string | Cookie session affinity. The cookie is AES-GCM encrypted, HttpOnly, and Secure over HTTPS |
| `sticky_cookie_name` | string | Affinity cookie name, default `LG_STICKY_BACKEND` |
| `sticky_cookie_ttl` | int | Affinity cookie lifetime in seconds, default 1800 |
| `limit_conn` | int | Maximum concurrent in-flight requests; over the limit returns 503 with Retry-After |
| `limit_conn_key` | string | `ip` limits per client IP; empty limits the route as a whole |
| `proto: grpc` | string | First-class gRPC proxying with automatic HTTP/2 and trailer pass-through; upgrades to grpcs when `mtls:true` |

> Related global settings (config.yaml): multi-node cookie affinity needs `sticky_key` (a shared 32-byte hex key); `cache.proxy_cache_max_entries` caps the number of cached entries.

---

### Running old and new services side by side (MCP/AI must follow this)

`rewrite` is not Nginx's `rewrite ... last`: it only changes the path sent upstream on the route that already matched. It does not re-match other routes and cannot switch the upstream.

When the user asks to "keep the old service running and move some traffic to a new one by query or header", the AI must generate two proxy routes: a high-priority conditional route pointing at the new service, and a low-priority catch-all keeping the old one. Do not claim that a rewrite will jump to another route.

```yaml
routes:
  - name: oauth-new
    priority: 100
    match:
      path: "/oauthcallback"
      rule: 'Query("state", "optional_state_id")'
    action:
      type: proxy
      upstream: ["new-oauth-service:8080"]
      rewrite:
        pattern: "^/oauthcallback$"
        target: "/new_oauthcallback"

  - name: oauth-old
    priority: 10
    match:
      path: "/oauthcallback"
    action:
      type: proxy
      upstream: ["old-oauth-service:8080"]
```

MCP call order: read and preserve the existing configuration with `get_site_config`, validate the complete YAML with `validate_site_config`, and only then call `save_site_config`. Do not use `create_proxy_site` to modify such a site — it can only produce a single route. After saving, call `lookup_route` at least twice, to verify the conditional match and the catch-all separately.

### Post-success actions for pure API backends (`on_success`)

When the page is rendered by LiteGate's `template` action and the backend only exposes a JSON API, cache invalidation and the HTMX protocol can stay in gateway configuration:

```yaml
- name: create-todo
  match:
    path: "/api/todos"
    method: ["POST"]
  action:
    type: proxy
    upstream_type: static
    upstream: ["127.0.0.1:9000"]
    on_success:
      invalidate_cache: ["todos"]
      htmx_trigger: ["todos-changed"]
      discard_body: true
```

Success means strictly `200` through `299`. On `3xx`, `4xx` and `5xx` none of these actions run and the error body still reaches the client. `htmx_trigger` overrides an upstream response header of the same name; `invalidate_cache` corresponds to `fetch_json.cache_tags`. The YAML route match field is `method`; in the JSON representation it is `methods`.

Templates may come from files under `template_root`, or from litemesh/Consul KV with `template_kv_mode` enabled; `on_success` is independent of how templates are stored.

### Referencing a named Service (legacy standard: `services` / `serverstransports`)

Define "how to reach the backend" once as a site-level named Service and reference it from routes with `action.service`.
The keys are the same as the service discovery tags `litegate.http.services.<name>.*` and `litegate.http.serverstransports.<name>.*`, and so are the validation rules.

```yaml
serverstransports:
  mesh:
    tls:
      enabled: true
      clientcertificate: litemesh    # mutual TLS with the Litemesh identity
      insecureskipverify: false

services:
  orders:
    discovery:
      name: orders                   # service name in discovery; mutually exclusive with servers
      selector:
        match: { version: v2 }       # hard boundary: only instances whose metadata matches
        meta: { zone: a }            # soft preference: preferred, falls back when none match
    timeout: 5s                      # end-to-end timeout of one request; 500ms etc. allowed
    loadbalancer:
      strategy: least_conn
      server: { port: 8080, scheme: https }
      serverstransport: mesh
    healthcheck: { path: /health, interval: 10s }
    retry: { attempts: 2 }
    circuitbreaker: { enabled: true, timeout: 60, maxrequests: 1, tripthreshold: 3 }

  legacy:
    servers: ["http://10.0.0.1:8080", "http://10.0.0.2:8080"]   # static backends

routes:
  - match: { path_prefix: /orders }
    action: { type: proxy, service: orders }
  - match: { path_prefix: /v2/orders }
    action: { service: orders }        # type defaults to proxy
```

Rules:

*   A route that references a `service` cannot also set upstream fields inline (`service_name`, `upstream`, `lb_policy`, `timeout`, `retry`, `circuit_breaker`, `health_check`, `route_selector`, `route_meta`, `service_port`, `proto`, `insecure_skip_verify`, `mtls`); loading fails otherwise. A route's backend has exactly one source of configuration.
*   Exactly one of `discovery.name` and `servers` must be set; `selector` only works with `discovery`.
*   Routes referencing the same Service share health and circuit-breaker state; a discovery-based Service also shares one load balancer, while static `servers` keep a round-robin position per route.
*   The inline form (writing `service_name`, `timeout`, ... directly in `action`) keeps working and behaves the same as referencing a Service.
*   The `retry` and `circuit_breaker` middleware types are deprecated; use the Service's `retry` / `circuitbreaker` instead.

## 5. Static file and directory actions

### `serve`

```yaml
action:
  type: serve
  root: "/var/www/html"
  index: "index.html"
  file: ""
  not_found_file: "404.html"
  spa: true
  compress: true
  cache_control: "public, max-age=3600"
  try_files: ["{path}", "/index.php"]   # Optional. Fall back through candidate files; a last entry starting with / is an internal redirect fallback (max 5, to prevent loops). Suits a PHP front controller
  
  # --- Serve KV auto-deployment mode (optional) ---
  kv_mode: true                    # enable hot deployment of a static ZIP
  kv_provider: "litemesh"          # driver: litemesh, consul, http
  kv_key: "litegate/config/main"   # key to watch; for http, the full endpoint URL
  keep_versions: 3                 # how many historical version bundles to keep locally (default 3)
```

### `webdav`

```yaml
action:
  type: webdav
  root: "/data/shared"
  web_ui: true
  read_only: false
  direct_download: true            # Optional. Allow direct file download, skipping the web player or serving as an attachment
  allow_browse: true               # Optional. Let anonymous visitors browse directories in the web UI (pairs with auth)
```

### `markdown`

```yaml
action:
  type: markdown
  root: "./docs"
  index: "README.md"
  render_markdown: true
  title: "Project Docs"
  show_hidden: false
```

Field reference:

| Field | Type | Description |
| :--- | :--- | :--- |
| `root` | string | Required. Root directory |
| `index` | string | Default index page |
| `file` | string | Serve one fixed file |
| `not_found_file` | string | Custom 404 file |
| `spa` | bool | SPA fallback to `index.html` |
| `compress` | bool | Enable compression |
| `cache_control` | string | Cache-Control header |
| `try_files` | string[] | serve only. Fall back through candidate files; a last entry starting with `/` acts as an internal redirect fallback (capped at 5 to prevent loops) |
| `kv_mode` | bool | Enable KV/HTTP auto-deployment of a front-end static ZIP |
| `kv_provider` | string | Version driver: `litemesh`, `consul`, `http` |
| `kv_key` | string | KV key to watch, or the full API URL |
| `keep_versions` | int | How many historical version directories each node keeps locally (default 3) |
| `web_ui` | bool | WebDAV file management UI |
| `read_only` | bool | WebDAV read-only |
| `direct_download` | bool | WebDAV only. Allow direct file download, skipping the previewer and supporting unauthenticated direct links |
| `allow_browse` | bool | WebDAV only. Allow anonymous users to browse directories in the web UI |
| `title` | string | Title for the listing / markdown page |
| `show_hidden` | bool | Show hidden files |
| `render_markdown` | bool | Enable markdown rendering |

### `template`

Server-side template rendering. The main template and its partials use `html/template`, which applies context-sensitive escaping against XSS automatically.

```yaml
action:
  type: template
  template: "./site/pages/index.html"   # Main template file (under KV mode, the main template's key in KV storage); or inline it with body
  template_root: "./site"               # Optional. Root scanned for partials, reusable as {{ template "partials/header.html" . }} (only when template_kv_mode is false)
  body: ""                              # Inline template string (alternative to template)
  status: 200
  content_type: "text/html; charset=utf-8"
  headers: {}

  # --- Template KV auto-deployment mode (optional) ---
  template_kv_mode: true                # load template files from KV storage
  template_kv_provider: "litemesh"      # KV driver: litemesh or consul
  template_kv_prefix: "litegate/templates/" # KV key prefix watched for template files
  template_kv_namespace: "default"      # Optional. Litemesh-only namespace

  # Fetch backend JSON APIs concurrently at render time (merged into .Data)
  fetch_json:
    - key: "weather"                      # merged key name, reachable as {{ .Data.weather }}
      url: "http://api.weather.local/v1"  # JSON endpoint fetched at render time (supports request context such as {{.Path}})
      ttl: 60                             # cache lifetime, in seconds
      timeout: 5                          # request timeout, in seconds
      allow_private: false                # allow requests to private IPs (SSRF protection)
      max_body_size: 2097152              # maximum response body, default 2MB
      fail_policy: "ignore"               # failure policy: "ignore" (swallow and return empty) or "error" (respond 500)
      forward_headers: ["Authorization"]  # client headers forwarded to the backend endpoint
```

| Field | Type | Description |
| :--- | :--- | :--- |
| `template` | string | Path to the main template (mutually exclusive with `body`, which `template` wins; under KV mode this is the main template's key in KV storage) |
| `template_root` | string | Optional. Root directory scanned for partials, for composing multiple files |
| `body` | string | Inline template string |
| `status` | int | Response status, default 200 |
| `content_type` | string | Defaults to `text/html; charset=utf-8` |
| `headers` | map | Extra response headers |
| `template_kv_mode` | bool | Load templates from KV with hot updates |
| `template_kv_provider` | string | Version driver: `litemesh`, `consul` |
| `template_kv_prefix` | string | KV key prefix watched for template files |
| `template_kv_namespace` | string | Optional. Namespace (litemesh only) |
| `fetch_json` | array | Backend JSON endpoints fetched concurrently at render time |
| `fetch_json[].key` | string | Key the data is merged under in `.Data`, e.g. `weather` |
| `fetch_json[].url` | string | URL template for the target JSON API (`{{ ... }}` parameters are rendered with `text/template` to avoid escaping) |
| `fetch_json[].ttl` | int | How long a success or failure is cached at the gateway, in seconds |
| `fetch_json[].timeout` | int | Backend request timeout in seconds (default 5s) |
| `fetch_json[].allow_private` | bool | Allow requests to private IPs. Defaults to `false`, which blocks SSRF and DNS rebinding |
| `fetch_json[].max_body_size` | int64 | Maximum backend response size in bytes (default 2MB) |
| `fetch_json[].fail_policy` | string | `ignore` (swallow the error, readable in the template as `.Errors.key`) or `error` (respond 500 immediately) |
| `fetch_json[].forward_headers` | string[] | Client headers to forward. Their values take part in the cache key, normalized case-insensitively |

> Variables and methods available in templates: `{{ .Host }}`, `{{ .Path }}`, `{{ .Method }}`, `{{ .ClientIP }}`, `{{ .Time }}`, `{{ .Header "K" }}`, `{{ .Query "k" }}`, `{{ .Cookie "n" }}`, `{{ .Nonce }}`.
> Built-in template functions:
> - `{{ htmx }}`: emits the embedded HTMX script tag `<script src="/_litegate/assets/htmx-4.0.0.min.js"></script>`, with nothing to download by hand.
> - `{{ markdown "## Content" }}`: converts Markdown text to safe HTML at render time.
> - `{{ safeHTML "<div>" }}`: marks an HTML fragment as trusted.
> - `{{ lower "ABC" }}` / `{{ upper "abc" }}` / `{{ contains "a" "b" }}` / `{{ replace "a" "b" "c" }}` / `{{ substr "abc" 0 2 }}`: common string operations.
> - `{{ env "APP_ENV" }}`: reads a value from the environment-variable allow-list.
> - `{{ formatTime .Time "2006-01-02" }}` / `{{ formatDateTime .Time "2006-01-02" }}`: RFC3339 and common time formatting.

> [!WARNING]
> **Security and functional limits of distributed templates (KV mode)**
> 1. **Markdown file loading stops working**: with `template_kv_mode` enabled there is no real local template directory (`realTemplateRoot` is empty), so `{{markdown "x.md"}}` referencing an external file no longer works. Only inline Markdown text renders (e.g. `{{markdown "## 文本"}}`).
> 2. **The generic `namespace` field is rejected**: validation forbids a root `namespace` field on `template` and `status` actions. For tenant or KV namespace isolation, declare `template_kv_namespace` explicitly.
> 2. **Security — equivalent to deploy permission**: write access to the target KV prefix (`template_kv_prefix`) is equivalent to being able to inject and execute arbitrary HTML/template code in the gateway through mechanisms like `safeHTML`. Lock down the namespace and the read/write token for that KV path accordingly.

### Combining HTMX with a backend API (fetch_json)

```yaml
domain: "dashboard.example.com"
routes:
  - name: "realtime-dashboard"
    match:
      path_prefix: "/"
    action:
      type: "template"
      template: "./pages/dashboard.html"
      fetch_json:
        - key: "metrics"
          url: "http://metrics-service.internal:8000/api/v1/stats?domain={{.Host}}"
          allow_private: true  # allow reaching the internal metrics service
          ttl: 5               # short cache for fast refresh
          fail_policy: "ignore"
```

And in the main template `./pages/dashboard.html`:
```html
<!DOCTYPE html>
<html>
<head>
    <title>Dashboard</title>
    <!-- pulls in the built-in HTMX script -->
    {{ htmx }}
</head>
<body>
    <h1>System Status for {{ .Host }}</h1>
    
    <!-- render the concurrently fetched JSON data -->
    <div id="stats">
        <p>Active Users: {{ .Data.metrics.active_users }}</p>
        <p>Total Requests: {{ .Data.metrics.total_reqs }}</p>
    </div>

    <!-- partial refresh via HTMX -->
    <button hx-get="/stats-partial" hx-target="#stats">Refresh Stats</button>
</body>
</html>
```

### `status`

Renders a system status dashboard, collecting live traffic, QPS and latency metrics plus historical health for every site and proxy route in the gateway.

```yaml
action:
  type: status
  title: "Service Status"                  # Optional. Status page heading, default "LiteGate System Status"
  host: "self"                          # Optional. "self" shows only the domain being visited; empty (default) shows every site
  template: "./site/pages/status.html"   # Optional. Custom status page template path (same usage as the template action)
  template_root: "./site"               # Optional. Root scanned for partials
  template_debug: false                 # Optional. Debug mode (templates not cached)
  template_production: true             # Optional. Production mode (templates cached)
  show_instances: false                 # Optional. Show the backend instances beneath each proxy route (default false)

  # --- Template KV auto-deployment mode (optional) ---
  template_kv_mode: true                # load the status page template from KV storage
  template_kv_provider: "litemesh"      # KV driver: litemesh or consul
  template_kv_prefix: "litegate/templates/" # KV key prefix watched for the status page template
  template_kv_namespace: "default"      # Optional. Litemesh-only namespace
```

| Field | Type | Description |
| :--- | :--- | :--- |
| `title` | string | Optional. Heading shown at the top of the status page |
| `host` | string | Optional. Which site to show. `self` shows only the domain being visited, which isolates tenants; a specific domain also works; empty (the default) shows every site in the gateway |
| `template` | string | Optional. Path to a custom status page template. Empty renders the gateway's built-in dashboard |
| `template_root` | string | Optional. Root directory scanned for partials |
| `template_debug` | bool | Optional. Debug mode, which disables template caching |
| `template_production` | bool | Optional. Production mode, which caches templates |
| `show_instances` | bool | Optional. Show the underlying backend instances beneath each proxy route (default false) |
| `template_kv_mode` | bool | Optional. Load the status page template from KV with hot updates |
| `template_kv_provider` | string | Optional. Version driver: `litemesh`, `consul` |
| `template_kv_prefix` | string | Optional. KV key prefix watched for the status page template |
| `template_kv_namespace` | string | Optional. Namespace (litemesh only) |

> The status page is not only an HTML dashboard: a request carrying `?format=json` or `Accept: application/json` returns the whole metric set as structured JSON, so other systems can scrape it.

---

## 6. `respond` and `redirect`

### `respond`

```yaml
action:
  type: respond
  status: 200
  body: "Hello, LiteGate!"
  content_type: "text/plain; charset=utf-8"
```

### `redirect`

```yaml
action:
  type: redirect
  location: "https://new-site.com{path}"
  status: 301
```

---

## 7. Middleware configuration

### `cors`

```yaml
cors:
  allowed_origins: ["https://app.example.com"]
  allowed_methods: ["GET", "POST", "PUT", "DELETE"]
  allowed_headers: ["Authorization", "Content-Type"]
  exposed_headers: ["X-Request-ID"]
  allow_credentials: true
  max_age: 3600
```

`allow_credentials: true` requires an explicit `allowed_origins` list; combining it with `*` (or `enabled: true` without origins) fails at load time.

### `auth`

```yaml
auth:
  type: basic
  realm: "LiteGate"
  users:
    admin: "<sha256>"
  permissions:
    admin: "rw"
  secret: ""
  sso_enabled: false
  allow_anonymous: false
  jwks_url: ""
  issuer: ""
  audience: []
```

### `waf`

```yaml
waf:
  enabled: true
  block_mode: true
  sensitivity: "medium"
```

### `circuit_breaker`

```yaml
circuit_breaker:
  enabled: true
  timeout: 60
  max_requests: 1
  trip_threshold: 3
```

---

## 8. IDS Providers (`ids`) and OIDC (`remote_auth`)

`ids` invokes a registered request-decision plugin. `remote_auth` configures OIDC / OAuth2 login; it is not an alias for IDS. The old “unified control engine” description no longer represents the current configuration. The core does not implement MD5, Redis sessions, login_steering or token_steering business rules.

V2 route example (`company-ids` must be implemented and registered):

```yaml
site: api.example.com
/api:
  proxy: localhost:8080
  ids:
    provider: company-ids
    fail_policy: deny
    selector_merge_policy: intersect
    options:
      policy_ref: order-read
    header_projection:
      allowed_headers: [X-Tenant-Ref]
```

| IDS field | Purpose |
|---|---|
| `provider` | Required registered IDS Provider name, independent of auth_providers |
| `fail_policy` | Defaults to deny; allow never overrides explicit rejection, host timeout or panic |
| `selector_merge_policy` | Defaults to intersect; merges static and plugin discovery filters |
| `runtime` | Host timeout, slow_threshold, max_concurrency and circuit_breaker |
| `options` | Plugin-defined string parameters, not built-in business rules |
| `header_projection` | allowed_headers controls trusted headers forwarded downstream |

IDS runs before the action, including proxy, respond and serve. Only proxy consumes discovery filters; the plugin cannot replace the selected Service. openapi-md5 is registered by the default entry point; upgrade to a binary containing it before use. See the [IDS Provider guide](../../ids_development_guide.md).

remote_auth supports enabled, provider, callback_path, enforce, inject_claims, default_redirect_back and fail_policy, using a global OIDC / OAuth2 auth_providers entry. Its retained sign_method field does not provide an MD5 IDS plugin.

Old ids.enabled, url, sign_method, static_secret, lookup and session parameters are not part of the current IDSConfig. Implement the relevant business logic in a Provider and define its options.

---

## 9. Rule expression DSL reference

`match.rule` supports boolean logic and a set of predicate functions:

- `Host("domain")`: match the domain, ignoring the port.
- `Path("/path")`: exact path match.
- `PathPrefix("/prefix")`: prefix match.
- `PathRegex("^/api/.*$")`: regular expression path match.
- `Method("GET")`: HTTP method match.
- `Header("Key")` or `Header("Key", "Value")`: header presence or value match.
- `HeaderRegexp("Key", "Pattern")`: header regular expression match.
- `Query("Key")` or `Query("Key", "Value")`: query parameter presence or value match.
- `QueryRegex("Key", "Pattern")`: query parameter regular expression match.
- `Cookie("Name")` or `Cookie("Name", "Value")`: cookie presence or value match.
- `CookieRegex("Name", "Pattern")`: cookie regular expression match.
- `CookiePrefix("Name", "Prefix")` / `CookieSuffix("Name", "Suffix")`: cookie prefix/suffix match (`CookieIPrefix`/`CookieISuffix` match case-insensitively).
- `ClientIP("10.0.0.0/8")`: match the real client IP or a CIDR range.

Logical operators: `&&` (and), `||` (or), `!` (not), `()` (grouping).

Example:
```yaml
match:
  rule: 'Host("api.example.com") && (Cookie("env", "canary") || Header("X-Beta"))'
```

---

## Response header removal, client IP limits and site TLS policies

```yaml
site: api.example.com
response_headers:
  "-Server": ""
  "-X-Powered-By": ""
  X-Gateway: LiteGate
tls:
  min_version: "1.2"
  max_version: "1.3"
  client_auth: require
  client_ca_file: ./certs/client-ca.pem
/api:
  rate_limit: {rate: 10, key: ip}
  proxy: localhost:8080
```

A leading `-` removes a response header at commit time; its value must be empty. An ordinary name with an empty value still sets an empty header. Route declarations override inherited site declarations. Setting and removing the same header in one declaration is rejected. Legacy `res_headers` supports removal too.

The numeric `rate_limit: 10` shares a bucket within a site and route. The mapping `{rate: 10, key: ip}` gives each client IP its own bucket; `key: route` shares it. Legacy actions use `rate_limit: 10` plus `rate_limit_key: ip`; named `ratelimit` middleware accepts `config: {qps: "10", key: ip}`. Rates are requests per second with the existing token-bucket burst behavior. Forwarded client addresses honor global `trusted_proxies`. Redis-backed limits remain distributed when keyed by IP.

TLS policies work with automatic certificates independently of the manual-certificate `enabled` flag. Versions accept only `1.2` and `1.3`; the minimum defaults to 1.2 and an omitted maximum is unrestricted. HTTP/3 requires TLS 1.3, so a site capped at TLS 1.2 cannot use HTTP/3.

`client_auth` accepts `none` (default), `optional` (verify any supplied certificate), and `require` (require a trusted certificate). The latter two require a local PEM `client_ca_file` and reject plain HTTP requests. Policies apply during the SNI handshake and are checked against the request's target site on every request, including reused connections. Reload the site after changing the CA file.

Optional `cipher_suites` lists safe Go TLS 1.2 suite names, for example `[TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256, TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256]`. TLS 1.3 suites cannot be customized.



### Client certificate revocation lists and connection caches

```yaml
tls:
  client_auth: require
  client_ca_file: ./certs/client-ca.pem
  client_crl_file: ./certs/client.crl.pem
```

`client_crl_file` accepts a local PEM CRL bundle (`X509 CRL`) or one DER CRL and requires `client_auth: optional` or `require`. When enabled, each leaf and intermediate certificate in an accepted chain requires a full CRL from its issuer. Missing, expired, future-dated, incorrectly signed lists and revoked certificates reject access. Signatures are checked against the actual issuer. Multiple full lists for one issuer use the highest CRL number. Delta, indirect and distribution-point-scoped CRLs are unsupported. If the CA file explicitly trusts an intermediate, include its issuer chain through a self-signed root in that file so intermediate revocation can also be checked.

CRLs are checked during TLS handshakes, including session resumption. HTTP/1, HTTP/2 and HTTP/3 requests reuse a connection-local verification result. Chains already verified by the handshake are reused only if trusted by the target site's current CA set. Each connection caches at most one successful result for the current policy, bounded by the earliest certificate or CRL expiration. Changing the target site, CA or CRL policy triggers verification again, including on existing keep-alive connections.

Reload the site after updating CA or CRL files; lists are not downloaded automatically. A failed reload preserves the previous configuration. Once its CRL expires, access remains denied rather than accepting stale revocation data.

## 10. Minimal examples (v2)

```yaml
site: api.example.com
proxy: 127.0.0.1:8080
```

```yaml
site: docs.example.com
spa: ./public
```

### Named request matchers

Site-level `matchers` define reusable conditions. Use `match: "@name"` to reference one in the same site. This is a reference, not an expression; YAML requires quotes around `@name`. Names start with a letter or underscore and contain letters, digits, underscores or hyphens. Undefined references, duplicate names, empty conditions and unknown fields are rejected, including in unused definitions. A matcher definition may be a list that composes other matchers (see composition below); cycles are rejected.

```yaml
site: example.com
matchers:
  blocked: { path: [/xmlrpc.php, "*.sql"] }
  post: { method: POST }
routes:
  - match: "@blocked"
    respond: { status: 403 }
  - match: "@post"
    proxy: localhost:6001
proxy: localhost:8080
```

Inline and named conditions have identical semantics. Different criteria are ANDed; path alternatives are ORed. A plain single `path` is exact. Path lists accept exact paths and `*` wildcards, matching the whole case-sensitive request path without its query. `*` matches zero or more characters, including `/`; `?` and brackets are literal. Quote YAML strings starting with `*`. `method` accepts a string or list. Use `rule` for expressions, ANDed with other criteria.

References do not change routing order: routing uses the precedence described below, and the root `proxy` is the fallback. The blocked example is a rejecting route, not a policy executed before every business route. Continue using snippets for shared governance settings.

Matcher routing order: explicit `priority` first (higher wins); at equal priority, exact paths precede pathless conditional routes (rule/method/header/query), which precede prefix routes. Prefixes retain length sorting, root `/` remains the fallback, and ties retain existing source precedence and declaration order. A singleton exact-path list has the same specificity as a scalar path. Thus `@blocked` with `*.sql` and method-only `@post` run before `/api`; use higher priority to override an exact path.

Paths are case-sensitive: `/xmlrpc.php` does not match `/XMLRPC.PHP`. For case-insensitive security matching use `PathRegexp` with `(?i)` in `rule`. `match` may be a list whose items must all hold: each item is `"@name"`, an inline condition or a `/prefix` shorthand, for example `match: ["@api", {method: POST}]`. When merging, `rule` expressions are joined with AND and `header`/`query` maps are merged without repeating a key (headers case-insensitively); other fields such as `prefix`, `path` and `method` may come from one item only (an identical repeat is allowed, a different value is an error). Lists do not nest.

Duplicate normalized route conditions are rejected; to reuse one matcher on several routes, add a different condition per route with a list. The routing-order change also affects legacy standard YAML, Lite, catalog-only and merged sites; set explicit priority to preserve the intended behavior of overlapping legacy routes.

### Multiple addresses, wildcard sites and redirect placeholders

```yaml
site: a.example.com, b.example.com
proxy: localhost:8080
```

Comma-separated v2 site addresses expand into independent sites sharing the configuration. Each address can include its own port. Empty or duplicate addresses are rejected; hostnames are lowercased and trailing dots removed. Single-site MCP authentication shortcuts do not support these multi-site configurations; use full YAML editing and validation.

```yaml
site: "*.example.com"
respond: hello
```

A wildcard matches one DNS label: foo.example.com, but neither example.com nor a.foo.example.com. Exact sites precede wildcards, which precede SaaS mappings and global fallbacks. Port-specific wildcards match that port only. HTTP matching does not configure TLS certificates; HTTPS still requires a valid certificate. Loading an HTTPS wildcard site without a matching enabled DNS-01 configuration or site-specific certificate logs a configuration warning; an existing usable wildcard certificate can still be served. A wildcard site does not authorize individual certificates for arbitrary subdomains. Use an existing DNS-01 wildcard certificate; without one, issuance is denied when on-demand is disabled, and otherwise still requires on-demand authorization and rate limits.

Exact sites allow `redirect: https://www.{host}{uri}`. Expanded multi-address sites are also exact sites. `{labels.N}` indexes hostname labels from the right, starting at zero, without the port: for www.example.com, labels.0=com, labels.1=example and labels.2=www. Out-of-range indexes and IP addresses yield an empty string. For example, `site: www.a.com, www.b.com` with `redirect: https://{labels.1}.{labels.0}{uri}` removes www. Wildcard and catch-all sites retain restrictions on variable-derived cross-origin redirects; query/header inputs cannot change the target origin.

### SPA index caching defaults

`spa: ./dist` defaults fallback, root and directly requested index files to `Cache-Control: no-cache`, permitting storage but requiring revalidation before reuse. Ordinary JS/CSS assets retain their existing behavior; missing resources with extensions still return 404. Explicit `cache_control` or an existing Cache-Control response header takes precedence. Explicit cache_control continues to apply to all files.

### Shared matchers and configuration fragments (_shared.yaml)

Put `sites/_shared.yaml` in the sites directory (in KV mode, the `_shared.yaml` key under the sites prefix). It accepts only top-level `matchers` and `snippets`. It is never compiled as a site; it is distributed together with the sites as shared definitions. Sites reference them with `match: "@name"` and `import: "@name"`; the existing `import: name` form remains supported. `config.yaml` no longer holds these keys; using them there is an error that names the new location.

Local definitions take precedence for direct site references. Imports inside shared snippets always resolve against the shared definitions, so site definitions cannot change their behavior. Only referenced shared definitions enter a site, and middleware names in `use` are checked against each site that actually imports the snippet. `_shared.yaml` itself is checked for syntax, references and cycles when loaded; `_shared.yaml` and `_shared.yml` cannot both exist.

Changing `_shared.yaml` revalidates every site. Any failure rejects the whole change and keeps the previous definitions and sites. In KV mode, unchanged shared content does not rebuild sites, and KV sites rejected because they arrived before the shared entry are retried once it applies. Removing shared definitions that are still referenced is rejected. Errors name `_shared.yaml` or the site file with source lines.

```yaml
# sites/_shared.yaml
matchers:
  api:
    prefix: /api
snippets:
  common:
    compress: true
```

```yaml
# sites/app.yaml
site: https://a.b.com
routes:
  - match: "@api"
    import: "@common"
    proxy: localhost:8080
```

`site: https://a.b.com` is equivalent to `site: a.b.com` with `https: true`, using the existing TLS and HTTP-to-HTTPS redirect behavior. A trailing `/` is allowed; URL paths, queries and user information are rejected. Combining it with `https: false` is an error. Explicit ports retain the existing `site: host:port` listener behavior and default HTTPS redirect target port rules.

Set site-level ech: ech.example.com alongside site: to select a configured ech.groups public name and DNS provider. Names are derived automatically. Multiple groups require explicit selection; one group also accepts true, and false disables ECH. Requires global ech.enabled, HTTPS port 443 and TLS 1.3; unknown groups and wildcard/IP/passthrough sites are rejected. Selection reloads live; transfers withdraw old records before the new group publishes. Legacy global domains remain enabled even with a false flag.
