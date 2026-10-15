# CSRF middleware

The CSRF middleware validates request origins for business endpoints using cookies or other browser-managed credentials. It is never attached automatically, including when SSO is enabled. Define it and explicitly reference it with site-level or route-level `use`.

```yaml
site: app.example.com
middlewares:
  browser_csrf:
    type: csrf
    config:
      allowed_origins: "https://frontend.example.com"
      allow_missing_origin: false
/api:
  use: browser_csrf
  proxy: http://127.0.0.1:8080
/webhook:
  proxy: http://127.0.0.1:8080
```

Only `/api` is protected in this example. Defining a middleware without referencing it does not protect requests.

| Setting | Default | Meaning |
| --- | --- | --- |
| `enabled` | `true` | Switch for an explicitly attached middleware |
| `allowed_origins` | Empty | Additional trusted HTTP(S) origins, comma-separated; wildcards, paths, queries and `null` are rejected |
| `allow_missing_origin` | `false` | Allow requests missing both Origin and Referer; does not allow an untrusted supplied origin |

All methods except GET, HEAD and OPTIONS are checked, including PATCH and WebDAV write methods. Origin takes precedence; Referer is used only when Origin is absent. Scheme, host and port must match, with implicit and explicit HTTP 80 / HTTPS 443 treated equally. The current request origin is always allowed; `allowed_origins` adds trusted origins. Rejections return 403 before business handling.

Cookies, Authorization and API keys never automatically exempt requests. Use separate routes without this middleware for webhooks and service clients, or explicitly enable `allow_missing_origin`, which weakens protection.

The request origin uses the actual TLS connection and Host, ignoring forwarded headers. When TLS terminates at a reverse proxy, explicitly list the public browser origin in `allowed_origins` and restrict access to the backend entry point.

Configure CORS separately: browser response-reading permissions do not replace CSRF validation. This middleware does not change Dashboard or OIDC defenses and does not implement CSRF tokens. Safe methods must not mutate business state; CSRF protection does not prevent XSS.
