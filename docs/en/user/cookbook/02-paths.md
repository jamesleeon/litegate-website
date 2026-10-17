# Paths: Split by Path, Rewrite, Redirect

Two rules underlie every recipe below:

1. **Path keys match by path segment.** `/api` matches `/api` and `/api/orders` but **not** `/apix`.
2. **More specific paths win; the site-level action is the fallback.** The order you write them in does not matter.

---

## 1. SPA frontend + backend API

The usual Vue / React deployment: `/api` goes to the backend, everything else to the frontend.

<!-- case: spa-api -->
```yaml
site: app.example.com
/api:
  proxy: localhost:8080
  strip_prefix: true      # turn on when the backend has no /api prefix
spa: ./dist
```

```check
GET http://app.example.com/api/orders         => 8080 /orders
GET http://app.example.com/                   => 200 "<h1>dist</h1>"
# Refreshing on a frontend route still gets index.html
GET http://app.example.com/settings/profile   => 200 "<h1>dist</h1>"
GET http://app.example.com/assets/app.js      => 200 "console.log"
```

- `spa` vs `file_server`: when a file is missing, `spa` returns `index.html` and `file_server` returns 404.
- If the backend itself expects the `/api` prefix, remove `strip_prefix`.

---

## 2. Split backends by path

<!-- case: path-split -->
```yaml
site: api.example.com
/users:
  proxy: localhost:8080
/orders:
  proxy: localhost:8081
/orders/export:           # the more specific path wins regardless of order
  proxy: localhost:8082
respond:
  status: 404
  body: unknown api
```

```check
GET http://api.example.com/users/42           => 8080 /users/42
GET http://api.example.com/orders/7           => 8081 /orders/7
GET http://api.example.com/orders/export/csv  => 8082 /orders/export/csv
# Segment matching: /usersx is not under /users
GET http://api.example.com/usersx             => 404 "unknown api"
```

---

## 3. Strip or replace a prefix

A legacy backend serves its API under `/legacy-app/`, but you want to expose it as `/v1`:

<!-- case: prefix-rewrite -->
```yaml
site: api.example.com
/v1:
  proxy: localhost:8080
  strip_prefix: true
  prepend_prefix: /legacy-app
```

```check
GET http://api.example.com/v1/orders?id=3     => 8080 /legacy-app/orders?id=3
```

- `strip_prefix: true` removes the matched prefix (`/v1` here); `prepend_prefix` then adds the new one.
- For more complex rewrites (regex, query changes) use `rewrite`; see [path rewrite and redirect](../05-middleware/path-and-redirect.md).

---

## 4. Case-insensitive paths

Users or old clients request `/GoApi`, `/GOAPI` and other mixed-case forms. Prefix the path with `~`:

<!-- case: ignore-case -->
```yaml
site: api.example.com
~/goapi:
  proxy: localhost:8080
  strip_prefix: true
```

```check
GET http://api.example.com/goapi/orders       => 8080 /orders
GET http://api.example.com/GoApi/orders       => 8080 /orders
# The rest of the path keeps its case
GET http://api.example.com/GOAPI/Orders       => 8080 /Orders
GET http://api.example.com/goapix             => 404
```

- `/goapi` without `~` is case-sensitive. The same path cannot be written both as `/goapi` and `~/goapi`.
- `~` is not a regex; only ASCII letters are matched case-insensitively.

---

## 5. Redirects

Move a whole site to another domain (for example `www` to the apex), keeping the path:

<!-- case: redirect-domain -->
```yaml
site: www.example.com
redirect:
  location: https://example.com{uri}
  status: 301
```

```check
GET http://www.example.com/blog/post-1?ref=x  => 301; Location: https://example.com/blog/post-1?ref=x
```

Redirect one old address and serve everything else normally:

<!-- case: redirect-path -->
```yaml
site: example.com
/old-docs:
  redirect:
    location: https://docs.example.com/
    status: 301
file_server: ./public
```

```check
GET http://example.com/old-docs/intro         => 301; Location: https://docs.example.com/
GET http://example.com/                       => 200 "<h1>public</h1>"
```

- The short form `redirect: https://...` uses 302 (temporary). For a permanent redirect use the object form with `status: 301`.
- Common variables: `{uri}` path plus query, `{path}` path only, `{host}` request host.

---

## 6. Exact paths and complex conditions

Path keys are prefix matches. To match one exact path, or to split by method or header, use the `routes` list:

<!-- case: exact-match -->
```yaml
site: example.com
routes:
  - match: {path: /}                 # only the home page itself
    redirect: /home.html
  - match: {path_prefix: /api, method: [POST, PUT, DELETE]}
    proxy: localhost:8081            # writes go to the primary service
/api:
  proxy: localhost:8080              # other /api requests (GET, ...) go to the read-only service
file_server: ./public
```

```check
GET    http://example.com/                    => 302; Location: /home.html
GET    http://example.com/about.html          => 200 "<h1>about</h1>"
POST   http://example.com/api/orders          => 8081 /api/orders
GET    http://example.com/api/orders          => 8080 /api/orders
```
