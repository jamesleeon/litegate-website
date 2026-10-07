# CORS Middleware (Cross-Origin Resource Sharing)

The LiteGate CORS middleware configures cross-origin request policies, so a frontend served from one origin can call APIs on another.

---

## 0. Do You Need CORS at All?

Browsers only apply cross-origin checks when the **scheme, host, or port** differs. If the frontend and the API are served from the same domain, no CORS is needed:

```yaml
# app.example.com: the frontend is served by the built-in serve action
domain: app.example.com
routes:
  - match: { path_prefix: / }
    action:
      type: serve
      root: /var/www/app
```

When backend services registered in service discovery (LiteMesh / Consul) declare an `/api` route on the same domain through tags, the gateway merges them into the same site. The frontend calls `/api/...` with relative URLs, and those requests are same-origin.

You still need CORS when:

*   The API lives on a different subdomain (e.g. `api.example.com`), port, or scheme.
*   A local dev server such as `http://localhost:5173` calls the gateway directly.
*   Frontends on other domains (mobile H5, admin consoles, third-party pages) call the same API.
*   Fonts or other assets are served from a different (CDN) domain.

---

## 1. Quick Start

The simplest form only turns the switch on:

```yaml
routes:
  - match: { path_prefix: / }
    action:
      type: proxy
      service_name: my-backend
      cors:
        enabled: true
```

With `enabled: true` and nothing else, the defaults are:

| Field | Default |
|---|---|
| `allowed_origins` | `*` (any origin) |
| `allowed_methods` | `GET, POST, PUT, DELETE, PATCH, OPTIONS` |
| `allowed_headers` | `*` (echoed from the preflight request, including `Authorization`) |
| `allow_credentials` | `false` |
| `max_age` | `3600` |

This is **anonymous CORS**: the response carries `Access-Control-Allow-Origin: *` and browsers do not send cookies. It suits public APIs; endpoints that rely on a login session need the credentialed mode below.

---

## 2. Advanced Configuration

### Method A: Route-Inline Configuration (Recommended)

```yaml
domain: api.example.com
routes:
  - match: { path_prefix: /api }
    action:
      type: proxy
      service_name: backend-svc
      cors:
        enabled: true
        # Credentials require the origins to be listed explicitly
        allowed_origins: ["https://web.example.com", "https://admin.example.com"]
        allowed_methods: ["GET", "POST", "PUT", "DELETE"]
        allowed_headers: ["Authorization", "Content-Type"]
        # Response headers readable by frontend scripts
        exposed_headers: ["X-Request-ID"]
        # Allow credentials (cookies / HTTP authentication)
        allow_credentials: true
        max_age: 3600
```

### Method B: Named Middleware (Reusable)

Define the middleware in the site's `middlewares` map and reference it by name from routes:

```yaml
domain: api.example.com
middlewares:
  web-cors:
    type: cors
    config:
      allowed_origins: "https://web.example.com, https://admin.example.com"
      allow_credentials: "true"

routes:
  - match: { path_prefix: /api }
    action:
      type: proxy
      service_name: backend-svc
    middlewares: ["web-cors"]
```

As service discovery tags:

```properties
litegate.http.routers.api.middlewares=web-cors
litegate.http.middlewares.web-cors.cors.allowed_origins=https://web.example.com
litegate.http.middlewares.web-cors.cors.allow_credentials=true
```

### Switch Semantics
* **`enabled: true`**: Activates the middleware and applies the defaults above to empty fields. Credentials are **never** turned on implicitly.
* **`enabled: false`**: **Forcefully deactivates the middleware**, even if `allowed_origins` is set.
* **(Omitted `enabled`)**: Backward compatibility mode. Active when `allowed_origins` is set; otherwise inactive.

### Origin Matching
* Origins are matched exactly, ignoring case and a trailing `/`.
* `*` means any origin.

---

## 3. Credentials (Cookies) and Safety Rules

`allow_credentials: true` **must** be combined with an explicit `allowed_origins` list. This configuration is rejected at load time:

```yaml
cors:
  allowed_origins: ["*"]      # or enabled: true without allowed_origins
  allow_credentials: true     # ❌ fails to load
```

"Any origin plus credentials" would let every website call the API as the logged-in user and read the responses. Browsers also refuse `Access-Control-Allow-Origin: *` together with credentials.

Configurations translated from Kubernetes Ingress / Gateway API do not fail to load for this reason: when `*` and credentials appear together, the gateway serves anonymous CORS (no `Access-Control-Allow-Credentials`) and logs a warning.

In credentialed mode, `*` in `allowed_methods` / `allowed_headers` echoes the requested method and headers, and `exposed_headers: ["*"]` lists the headers the response actually carries, as browsers require for credentialed requests.

---

## 4. Preflight Handling

An `OPTIONS` request carrying `Origin` and `Access-Control-Request-Method` is a preflight. The gateway answers it directly with **204 No Content** and does not forward it upstream:

* Allowed origin: the full set of `Access-Control-Allow-*` headers is returned.
* Disallowed origin: a 204 without CORS headers, so the browser rejects the actual request.

Plain `OPTIONS` requests without `Access-Control-Request-Method` (for example WebDAV `OPTIONS`) are passed to the route's action as usual.

Preflights are handled before authentication, so auth middleware never blocks them.

---

## 5. Relationship With Backend CORS Headers

Once CORS is configured on a route, **the gateway owns the CORS response headers**:

* `Access-Control-*` headers returned by the backend are replaced by the gateway's policy, so there are no duplicate `Access-Control-Allow-Origin` values and a permissive backend cannot bypass the gateway.
* CORS headers are written when the response header is finally sent, so same-named backend headers cannot overwrite them.
* `Vary: Origin` is merged with the backend's `Vary` (e.g. `Accept-Encoding`) instead of being replaced, so CDNs and browser caches never serve one origin's response to another.

Leaving CORS enabled in the backend therefore causes no conflict. If you want the backend to own CORS entirely, do not configure it on the gateway.

To rewrite other response headers, use `response.*` in the `headers` middleware; it likewise overrides same-named backend headers:

```properties
litegate.http.routers.api.middlewares=security-headers
litegate.http.middlewares.security-headers.headers.response.X-Frame-Options=DENY
```

---

## 6. Troubleshooting & FAQ

### CORS errors persist after configuring?
1. **Check the origin exactly**, including scheme and port: `http://localhost:5173` and `http://127.0.0.1:5173` are different origins.
2. **Cookies are not sent**: make sure `allow_credentials: true` is set with explicit `allowed_origins`, and that the frontend uses `credentials: "include"` / `withCredentials: true`.
3. **A custom request header is rejected**: when `allowed_headers` is an explicit list, it must include every header the frontend sends (such as `Authorization` and `Content-Type`); use `*` if unsure.

---

## Further Reading
- [Configuring Reverse Proxy Actions](../04-actions/proxy.md)
- [Enforcing Authentication Filters](./authentication.md)
