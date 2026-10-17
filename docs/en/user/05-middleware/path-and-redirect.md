# Path Rewrite and Redirect Middleware

These named middleware all run in the **RequestTransform** phase — **before** WAF, authentication and rate limiting — so security components see the final normalized path.

Keep the two kinds apart:

| Kind | Middleware | Behavior | Visible to the client? |
| :--- | :--- | :--- | :--- |
| **Internal rewrite** | `strip_prefix`, `rewrite`, `replace_path_regex` | Changes the path/query sent upstream; the client URL stays the same | No |
| **External redirect** | `redirect_scheme`, `redirect_regex` | Returns a `3xx` to the client so the browser goes to the new address | Yes |

---

## 1. `strip_prefix` — remove a path prefix

Remove a prefix such as `/api` before proxying — the most common gateway need.

```yaml
site: api.example.com
middlewares:
  strip-api:
    type: strip_prefix
    config:
      prefixes: "/api,/v1"   # comma-separated, each must start with /

/api:
  use: [strip-api]
  proxy: 127.0.0.1:8080      # /api/users -> /users
```

- The **first** matching prefix is stripped and matching stops; an empty result falls back to `/`.
- Every prefix must start with `/`, or loading fails.

---

## 2. `rewrite` — regex path rewrite + query editing

`rewrite` is the most complete internal rewriter: one middleware handles both path and query.

For the full inline configuration, execution order, query semantics and examples of migrating from Nginx `last`, see [Rewrite: path and query rewriting](../03-configuration/rewrite.md).

```yaml
middlewares:
  api-rewrite:
    type: rewrite
    config:
      path_pattern: "^/api/(.*)$"       # regex
      path_target: "/$1"                # target path, must start with /
      query_set.version: "v2"           # set ?version=v2 (overwrite)
      query_add.trace: "1"              # append ?trace=1
      query_rename.uid: "user_id"       # rename ?uid= to ?user_id=
      query_remove: "debug,internal"    # remove these query parameters (comma-separated)
```

| Field | Description |
| :--- | :--- |
| `path_pattern` / `path_target` | Used as a pair. `path_pattern` is a regex; `path_target` supports `$1`, `$2` back-references and must start with `/`. |
| `query_set.<name>` | Set a query parameter (replacing an existing one). |
| `query_add.<name>` | Append a query parameter (may coexist with existing values of the same name). |
| `query_rename.<name>` | Rename parameter `<name>` to the target name given as its value. |
| `query_remove` | Comma-separated names of parameters to remove. |

- At least one path or query operation is required, or loading fails.
- When `path_pattern` doesn't match the current path, the whole rewrite (query operations included) is skipped, keeping it atomic.
- `rewrite` has `AllowMultiple = false`: a route has at most one active rewrite, and **inline `rewrite` and named `rewrite` cannot be combined**; that is a load error.

> When you only need a regex path replacement without query changes, `replace_path_regex` is lighter.

---

## 3. `replace_path_regex` — regex path replacement only

```yaml
middlewares:
  legacy-path:
    type: replace_path_regex
    config:
      regex: "^/old/(.*)$"
      replacement: "/new/$1"   # must start with /
```

- Affects only `req.URL.Path`, not the query string.
- After rewriting, the original path is written to the `X-Replaced-Path` header, and the original URI is kept for logging.
- `AllowMultiple = true`: several can be stacked and run in declaration order.

---

## 4. `redirect_scheme` — scheme/port redirect

The standard way to force HTTP to HTTPS.

```yaml
middlewares:
  force-https:
    type: redirect_scheme
    config:
      scheme: "https"        # http or https
      permanent: "true"      # true = 301, false/omitted = 302
      # port: "8443"         # optional target port
```

- When the current scheme (and optional port) already equals the target, there is no redirect and the request passes.
- The scheme is determined from `req.TLS` and `X-Forwarded-Proto`, so it works behind reverse proxies and load balancers.

---

## 5. `redirect_regex` — regex redirect on the full URL

> **Important**: the `regex` of `redirect_regex` matches the **full absolute URL** (`scheme://host/path?query`), **not just the path**.

```yaml
middlewares:
  redirect-old-domain:
    type: redirect_regex
    config:
      regex: "^https?://old\\.example\\.com/(.*)$"
      replacement: "https://new.example.com/$1"
      permanent: "true"
```

- `replacement` supports `$1` back-references.
- Targets containing newlines or other control characters return 500 (injection protection).
- `permanent: true` → 301, otherwise 302.
- `AllowMultiple = true`: several rules can be configured.

---

## 6. Execution order summary

Within RequestTransform, middleware run from outside in by their registered `Order`; equal `Order` follows declaration order on the route. MCP's `lookup_route` shows the `Effective Pipeline (outer → inner)` after chains expand, confirming the final order.

Because the whole group runs **before security checks**, WAF and authentication always see the final rewritten path — important for path allow lists and signature policies.

Rewrites only affect the request sent to the current upstream and **never re-select the route**: the route was chosen from the original path before rewriting. All regexes use Go `regexp` syntax.

---

## Further reading

- [Rewrite: path and query rewriting](../03-configuration/rewrite.md)
- [Redirect action](../04-actions/redirect.md)
- [Middleware pipeline and chain](./pipeline.md)
- [Reverse proxy action](../04-actions/proxy.md)
- [Rate limiting and concurrent connection limits](./rate-limit.md)
