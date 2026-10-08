# Template Action (Server-Side Templates)


The `template` action renders dynamic HTML on the server using Go's `html/template`. Output is HTML-escaped by default (XSS-safe), the request context (headers / query / cookies / client IP …) is injected, and multi-file **partial reuse** (header / footer / nav) is supported.

> Use cases: error/status pages, lightweight pages with a bit of dynamic data, or multi-page sites that share one layout. Equivalent to Caddy's `templates`.

---

## 1. Minimal Configuration (Inline Template)

```yaml
domain: status.example.com
routes:
  - name: hello
    match:
      path_prefix: /
    action:
      type: template
      body: "<h1>Hello {{ .Host }}</h1><p>Your IP: {{ .ClientIP }}</p>"
```

`body` is best for short inline templates.

---

## 2. File Template

```yaml
action:
  type: template
  template: "./templates/index.html"   # Path to the main template file
```

```html
<!-- ./templates/index.html -->
<!DOCTYPE html>
<html>
  <body>
    <h1>{{ .Host }}{{ .Path }}</h1>
    <p>Method: {{ .Method }} Time: {{ .Time }}</p>
    <p>UA: {{ header "User-Agent" }}</p>
  </body>
</html>
```

---

## 3. Multi-File Composition (Partial Reuse)

When `template_root` is set, LiteGate scans the directory for every `.html` / `.tmpl` file and **compiles them together**, so the main template can reference others via `{{ template "relative/path" . }}` and reuse shared layout such as header / footer.

```yaml
action:
  type: template
  template: "./site/pages/index.html"   # Main template
  template_root: "./site"               # Root scanned for partials
```

```html
<!-- ./site/pages/index.html (main) -->
{{ template "partials/header.html" . }}
<main>Welcome to {{ .Host }}</main>
{{ template "partials/footer.html" . }}
```

```html
<!-- ./site/partials/header.html -->
<header><nav>Site Nav</nav></header>
```

> A partial's template name is its path relative to `template_root` (slash-separated), e.g. `partials/header.html`.

### 📦 Distributed Loading from litemesh / Consul KV (`template_kv_mode`)

Instead of reading from local disk, templates can be **stored directly in litemesh / Consul KV** and compiled in memory by the gateway. A clustered deployment then needs no per-node file distribution — update the KV once and it takes effect fleet-wide. This mirrors the existing [Serve KV mode](../../serve_kv_mode.md).

```yaml
action:
  type: template
  template_kv_mode: true
  template_kv_provider: "litemesh"            # litemesh or consul
  template_kv_prefix: "litegate/tmpl/site-a/" # KV prefix the partials live under
  template_kv_namespace: "tenant-a"           # optional, multi-tenant isolation; empty = client default namespace
  template: "pages/index.html"                # main template: key suffix relative to the prefix
```

How it works:

- The gateway calls `ListKV(prefix)` to fetch every partial under the prefix (each KV key, with the prefix stripped, becomes the template name usable via `{{ template "..." }}`); the main template is named by the `template` field.
- **Pure in-memory compilation, zero local files** — no filesystem, hence no symlink / path-traversal surface.
- **Hot reload**: the gateway watches the prefix for changes (litemesh SSE / KV `ModifyIndex`), recompiles in the background on any change, and atomically swaps — in-flight requests are unaffected.
- **Fail-safe**: if a KV fetch fails, the gateway falls back to the last successfully compiled template instead of breaking the page.

#### ⚖️ Resource & Security Boundaries

| Boundary | Limit | Notes |
| :--- | :--- | :--- |
| Number of partials | ≤ 100 | Exceeding returns an error (memory-abuse guard) |
| Single partial size | ≤ 1 MB | Exceeding returns an error |
| Total size of all partials | ≤ 10 MB | Exceeding returns an error |

> ⚠️ **Security note**: write access to this KV prefix equals the ability to inject arbitrary template code into the gateway (templates can call `safeHTML` etc. to bypass escaping). Treat KV template write access as a **code-deploy privilege** and lock down the corresponding namespace and access token.

> ℹ️ **Limitation**: in KV mode there is no local root directory, so the **file-loading form of `{{ markdown "x.md" }}` is unavailable** (only inline strings such as `{{ markdown "# Title" }}` work). All other context variables and built-in functions (see the next section) work normally.

---

## 4. Variables and Methods Available in Templates

The render context (`.`) exposes:

| Field / Function | Description |
| :--- | :--- |
| `{{ .Host }}` | Request Host |
| `{{ .Path }}` | Request path |
| `{{ .Method }}` | HTTP method |
| `{{ .ClientIP }}` | Real client IP |
| `{{ .Time }}` | Current time (RFC3339) |
| `{{ header "Key" }}` | A specific request header |
| `{{ query "key" }}` | A specific query parameter |
| `{{ cookie "name" }}` | A specific cookie value |
| `{{ .Req }}` | Raw `*http.Request` (advanced; fields only) |
| `{{ .Data.<key> }}` | Parsed JSON for a `fetch_json` entry (see §10) |
| `{{ .Errors.<key> }}` | Error message for a failed `fetch_json` entry (`ignore` policy) |
| `{{ .Nonce }}` | Per-request cryptographically secure nonce for CSP |

> Templates call registered functions only, never methods on the data (such as `{{ .Req.FormValue "x" }}`): calling methods by name through reflection makes the linker keep every method of every dependency (about 4MB). `header` / `query` / `cookie` are functions too; the old `{{ .Header "X" }}` form fails when the template loads, and the error shows the replacement.

### 🛠️ Built-in Template Helper Functions

In addition to Go's standard built-ins, LiteGate registers the following helpers in the render context:

| Function | Description | Example |
| :--- | :--- | :--- |
| `formatTime` / `formatDateTime` | Format a `time.Time` or a common time string (RFC3339, `2006-01-02 15:04:05`) | `{{ formatTime .Time "2006-01-02" }}` |
| `markdown` | Render a Markdown string into safe HTML (no double-escaping) | `{{ markdown "# Title" }}` |
| `htmx` | Inject the built-in HTMX 4.0.0 `<script>` tag (no CDN needed) | `{{ htmx }}` |
| `safeHTML` | Mark a trusted HTML fragment to bypass auto-escaping | `{{ safeHTML "<div>" }}` |
| `lower` / `upper` | Lowercase / uppercase a string | `{{ upper "xyz" }}` |
| `contains` / `replace` / `substr` | Substring match, replace-all, rune-safe slicing | `{{ substr "abcdef" 1 4 }}` → `bcd` |
| `env` | Read an allow-listed environment variable | `{{ env "APP_ENV" }}` |

---

## 5. Field Reference

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `template` | string | — | Main template file path (mutually exclusive with `body`; `template` takes priority) |
| `template_root` | string | dir of main template | Root directory scanned for partials (multi-file composition) |
| `markdown_template` | string | — | Path to the layout template used when rendering Markdown files in `serve` mode |
| `body` | string | — | Inline template string |
| `status` | int | `200` | Response status code |
| `content_type` | string | `text/html; charset=utf-8` | Response `Content-Type` |
| `headers` | map | — | Extra response headers |
| `template_production` | bool | `false` | Enable production cache. Templates (including layouts) are precompiled at startup with zero disk I/O on hot paths. |
| `template_debug` | bool | `false` | Enable visual dark-mode error screen (Vite/Gin style) with line numbers and 11 lines of code context. Forces hot-reload. |
| `on_error` | object | — | Degradation rules when template execution or compilation fails (contains `status`, `content_type`, `body`, and `template`). |
| `fetch_json` | list | — | Server-side JSON data sources fetched before render and exposed as `.Data.<key>` (see §10). |

---

## 6. Performance & Caching

- **Development Mode**: By default, compiled templates are cached and only recompiled when a template file changes (detected by modification time `os.Stat` calls) — avoiding full per-request disk reads.
- **Production Mode (`template_production: true`)**: All templates and layouts are precompiled at gateway startup and stored in memory. Request processing serves directly from memory cache, **completely eliminating disk I/O** (zero `os.Stat` / `os.ReadFile` syscalls).
- **Buffer Safety**: Rendering goes to an in-memory buffer first, so a render failure never emits a half-written 200 response to the client.

---

## 7. Security Notes

- **XSS-safe by default**: built on `html/template`, variables are context-escaped automatically.
- **Traversal protection**: the main template and every partial are symlink-resolved (`EvalSymlinks`) and checked for escaping `template_root`; anything outside is rejected.
- **TOCTOU protection**: the file handle is opened before stat/read. Ensure the `template_root` tree is **writable only by trusted users** (see [SECURITY.md](https://github.com/jamesleeon/LiteGate/blob/master/SECURITY.md)).
- **fetch_json SSRF protection**: target hosts are resolved and checked **at dial time**; private / loopback / link-local / multicast / CGNAT (`100.64.0.0/10`) / reserved ranges are blocked unless `allow_private: true`. Redirects are re-validated through the same secure transport, only `http`/`https` schemes are allowed, and response size / timeout are enforced. See §10.
- **forward_headers credential leak** ⚠️: `forward_headers` forwards the named request headers (e.g. `Authorization`, `Cookie`) to the fetch target. The target URL is **not allow-list restricted**, so only forward credential headers to URLs you fully control — a misconfigured or injected URL template could exfiltrate credentials to an external host. Hardcode the host portion of `url`; never build it from user input.
- **HTMX script & CSP**: `{{ htmx }}` emits the bundled script **with the per-request nonce baked in** — e.g. `<script src="/_litegate/assets/htmx-4.0.0.min.js" nonce="…"></script>` — and always points at the current embedded version, so an htmx upgrade never leaves a hardcoded versioned URL 404ing. Prefer `{{ htmx }}` over hand-writing the tag. For the nonce to actually enforce anything you must also emit a matching CSP header: set **`template_csp`** on the action (see below). Hardcode the versioned URL only if you cannot use the helper, and remember to update it on every htmx bump.
- **Content-Security-Policy (`template_csp`)**: the `{{ .Nonce }}` / `{{ htmx }}` nonce is body-only until a `Content-Security-Policy` response header carries the *same* value. `template_csp` closes that loop:
  - `template_csp: "auto"` emits a strict baseline: `default-src 'self'; script-src 'self' 'nonce-<request-nonce>'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'`. Only `{{ htmx }}` and `{{ .Nonce }}`-tagged inline scripts run; all other scripts are blocked. (Inline `<style>` is still allowed via `'unsafe-inline'`; tighten it yourself if needed.)
  - Any other value is treated as a literal policy where the token `{nonce}` is replaced by the request nonce, e.g. `template_csp: "default-src 'self'; script-src 'nonce-{nonce}'"`.
  - If `action.headers` already sets `Content-Security-Policy`, that explicit value wins and `template_csp` is skipped.
- **HTMX 4 migration**: LiteGate embeds 4.0.0. Parent-level htmx attributes are no longer inherited implicitly; add the `:inherited` suffix where descendants rely on them. Event names use the new phase form (for example, `htmx:after:request` instead of `htmx:afterRequest`), and request/response event data now lives under `event.detail.ctx`. HTTP 4xx/5xx bodies are swapped by default in v4. The legacy unversioned asset URL `/_litegate/assets/htmx.min.js` returns 410 Gone and logs migration guidance; templates should use `{{ htmx }}` or the versioned URL.

---

## 8. Markdown Template Layout (Serve Mode integration)

In `serve` mode, if `render_markdown` is enabled, you can specify `markdown_template` to wrap the rendered markdown document in a custom HTML layout.

```yaml
action:
  type: serve
  root: "./docs"
  render_markdown: true
  markdown_template: "./templates/layouts/doc.html"
```

In the layout template `doc.html`, the following Go template variables are exposed:
- `{{ .Title }}`: The resolved title from the filename or the first H1 header in the document.
- `{{ .Content }}`: The rendered HTML content of the Markdown document (of type `template.HTML` to prevent escaping).
- `{{ .Sidebar }}`: The tree navigation structure of sibling files. Render with `{{ range .Sidebar }}`.
- `{{ .Host }}`, `{{ .Path }}`: Standard request context values.
- `{{ .Nonce }}`: Random cryptographically secure nonce generated per request for Content Security Policy.

### 📝 Example Layout Template
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{{ .Title }} - Docs</title>
</head>
<body>
    <aside class="sidebar">
        <h3>Menu</h3>
        {{ range .Sidebar }}
            <div><a href="{{ .Href }}">{{ if .IsDir }}Folder{{ else }}File{{ end }} {{ .Name }}</a></div>
        {{ end }}
    </aside>
    <main>{{ .Content }}</main>
</body>
</html>
```

---

## 9. Advanced Settings: Production, Debug & OnError

LiteGate provides robust settings for performance pre-compilation, visual diagnostics, and fallback degradation.

### ⚙️ YAML Configuration Example
```yaml
action:
  type: template
  template: "./site/pages/index.html"
  template_root: "./site"
  
  # 1. Production Mode
  # Precompiles all templates (including markdown layout templates) at gateway startup.
  # Keeps them in memory to eliminate cold starts and bypasses disk syscalls (zero os.Stat / os.ReadFile) during request handling.
  template_production: true

  # 2. Debug Mode
  # If compile or execution fails, renders a detailed Glassmorphism-style diagnostics screen in the browser
  # highlighting the exact error location and showing 11 lines of surrounding code.
  # Automatically invalidates and hot-reloads templates on Mtime changes of files inside template_root.
  template_debug: true

  # 3. On-Error Fallback Configuration
  # Safe degradation configuration when templates fail to build or run.
  on_error:
    status: 502
    content_type: "text/html; charset=utf-8"
    body: "<h1>Site Maintenance</h1>"    # Inline HTML string
    # template: "./site/fallback.html"   # Or local HTML file fallback
```

### 🧠 Environment Mode Guide

| Environment | Recommendations | Core Benefits |
| :--- | :--- | :--- |
| **Development** | `template_debug: true`<br>`template_production: false` | 1. **Hot reload**: Auto-detects modifications on main file or nested partials inside `template_root`. <br>2. **Visual diagnostics**: Beautiful Vite-like screens highlighting error line numbers and context. |
| **Production** | `template_debug: false`<br>`template_production: true` | 1. **Zero I/O overhead**: Eliminates stat and file syscalls, boosting concurrency QPS.<br>2. **Precompilation**: Warm up the caches at startup.<br>3. **Degradation**: Gracefully handles errors using `on_error` settings to hide backend paths and debug info. |

---

## 10. Partial Dynamic Refresh with HTMX + fetch_json 🌟

By combining `fetch_json` (server-side data fetching) with the built-in `{{ htmx }}` helper, you can build modern, no-reload partial-update pages entirely at the gateway layer — no Vue/SPA backend required.

The example below: a `respond` action plays the role of a monitoring JSON API, `/stats-partial` returns an HTML fragment, and the home page uses the embedded HTMX to swap that fragment in-place on button click.

### ⚙️ YAML Example (`sites/demo.yaml`)
```yaml
domain: "cool-dashboard.local"
force_https: false

routes:
  # 1. Mock backend JSON API
  - name: mock-json-api
    match:
      path: "/api/stats"
    action:
      type: "respond"
      status: 200
      content_type: "application/json; charset=utf-8"
      body: '{"status":"healthy","qps":342,"cpu":14.8,"time":"{{.Time}}"}'

  # 2. Called by HTMX: fetch the API and return an HTML fragment to swap in
  - name: stats-fragment
    match:
      path: "/stats-partial"
    action:
      type: "template"
      body: '<div id="stats-data"><p>Status: <strong style="color:#22c55e;">{{.Data.monitor.status}}</strong></p><p>QPS: <strong>{{.Data.monitor.qps}}</strong></p><p>CPU: <strong>{{.Data.monitor.cpu}}%</strong></p><p style="color:#94a3b8;">Updated: {{formatTime .Data.monitor.time "15:04:05"}}</p></div>'
      fetch_json:
        - key: "monitor"
          url: "http://127.0.0.1:8080/api/stats"
          allow_private: true

  # 3. The dashboard home page
  - name: main-dashboard
    match:
      path: "/"
    action:
      type: "template"
      template: "./templates/dashboard.html"
      fetch_json:
        - key: "monitor"
          url: "http://127.0.0.1:8080/api/stats"
          allow_private: true
```

### 📝 ./templates/dashboard.html
```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>System Health Dashboard</title>
    <!-- Auto-load the embedded HTMX script -->
    {{ htmx }}
</head>
<body>
    <h1>Dashboard - {{ .Host }}</h1>
    <div class="card">
        <h3>Live Metrics</h3>
        <!-- First paint: rendered server-side via fetch_json for instant load -->
        <div id="stats-data">
            <p>Status: <strong style="color:#22c55e;">{{.Data.monitor.status}}</strong></p>
            <p>QPS: <strong>{{.Data.monitor.qps}}</strong></p>
            <p>CPU: <strong>{{.Data.monitor.cpu}}%</strong></p>
            <p style="color:#94a3b8;">Updated: {{formatTime .Data.monitor.time "15:04:05"}}</p>
        </div>
        <!-- On click, HTMX fetches /stats-partial and swaps #stats-data with no reload -->
        <button hx-get="/stats-partial" hx-target="#stats-data" hx-swap="outerHTML">
            Refresh
        </button>
    </div>
</body>
</html>
```

### 📋 `fetch_json` Field Reference

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `key` | string | — | Template variable name; parsed JSON is exposed as `{{ .Data.<key> }}` |
| `url` | string | — | Fetch URL; supports `{{ }}` templating against the request context (`.Query`/`.Header`) |
| `ttl` | int (sec) | `0` | Result cache duration; `0` disables caching. Non-2xx and network errors get a short negative cache to prevent stampedes |
| `timeout` | int (sec) | `5` | Per-request timeout |
| `allow_private` | bool | `false` | Allow the target to resolve to private/loopback IPs (needed for internal services) |
| `max_body_size` | int (bytes) | `2MB` | Response body cap; exceeding it aborts the fetch |
| `fail_policy` | string | `ignore` | `ignore`: record into `{{ .Errors.<key> }}` and keep rendering; `error`: abort render and trigger `on_error` |
| `forward_headers` | []string | — | Request headers forwarded to the target; also isolate the cache key so different identities don't share a cached result |
| `cache_tags` | []string | — | Tags attached to the cached result; a proxied response can invalidate them with `LiteGate-Invalidate: tag-a,tag-b` |
| `lb_policy` | string | `round_robin` | Load-balancing policy used by a `service://` data source |

In addition to `http://` and `https://`, `url` accepts a gateway-native service address:

```yaml
template_fragment: "stats-cards" # render this named template for HX-Request:true
fetch_json:
  - key: stats
    url: "service://orders/api/stats"
    ttl: 10
    cache_tags: ["orders:{{ header \"X-Tenant-Id\" }}"]
    forward_headers: ["X-Tenant-Id"]
```

`service://` reuses LiteGate service discovery, IDS selector/meta, healthy-instance filtering, load balancing, and the mTLS-aware proxy transport. Its cache key includes the discovery query dimensions. Identity-dependent headers must still be listed in `forward_headers` so they are both forwarded and included in cache isolation.

With `template_fragment`, a normal request executes the full main template while `HX-Request: true` executes the named `{{ define "..." }}` template and returns `Vary: HX-Request`. One URL can therefore serve both the full page and HTMX refreshes.

Prefer keeping a JSON API unaware of gateway protocols by declaring the behavior on its write proxy route:

```yaml
action:
  type: proxy
  upstream: ["127.0.0.1:9000"]
  on_success:
    invalidate_cache: ["orders:tenant-a"]
    htmx_trigger: ["orders-changed"]
    discard_body: true
```

After an upstream `2xx`, LiteGate invalidates the cache, emits `HX-Trigger`, and optionally withholds the JSON response body. This works identically whether templates are loaded from `template_root` files or KV through `template_kv_mode`.

For compatibility, an existing mutating backend may instead return:

```http
LiteGate-Invalidate: orders:tenant-a
HX-Trigger: orders-changed
```

LiteGate consumes the first header internally to invalidate matching `fetch_json` entries and passes the second through to HTMX. New systems should prefer `on_success` so the API is not coupled to either header.

> **Security**: see §7 — `fetch_json` blocks SSRF by default, `forward_headers` can leak credentials to non-allow-listed hosts, and `{{ htmx }}` needs a nonce under a strict CSP.

### 🔌 Gateway HTMX-awareness (proxy-backend setups)

When you run the **HTMX + backend (`type: proxy`)** architecture (gateway at the edge, backend rendering fragments with `html/template`), LiteGate detects the `HX-Request: true` header and adjusts two behaviors so it never breaks HTMX's in-place swapping:

- **Error pages skip HTMX requests**: on normal full-page requests `error_pages` replaces 404/5xx with a full error page, but for HTMX requests (including `hx-boost` requests that send `Accept: text/html`) interception is **bypassed**, letting the backend's HTML fragment and status code pass through — otherwise a full error page would be swapped into a `<div>`.
- **SSO uses `HX-Redirect` when unauthenticated**: on routes protected by `auth.type: sso`, an unauthenticated normal request gets a `302` to the login page, while an HTMX request gets `401 + HX-Redirect: /_auth/login?next=...` so htmx performs a real full-page navigation instead of swapping the login page into a fragment target.

> All `HX-*` request/response headers (`HX-Trigger`, `HX-Redirect`, `HX-Push-Url`, `HX-Retarget`, `HX-Reswap`, …) are passed through unchanged by the reverse proxy (only RFC 7230 hop-by-hop headers are stripped), and HTMX's SSE / WebSocket extensions are supported. The OIDC middleware's auth redirect is not yet HTMX-aware.

---

## Further Reading
- [Markdown Rendering Service](./markdown.md)
- [Serving Static Assets](./serve.md)
- [Respond Action](./respond.md)
