# Named Matchers: Give Request Conditions a Name

Once route conditions grow, `match: {path: [...], method: [...], header: {...}}` crowds into one line and you have to parse it in your head to know what the route handles. Named matchers define the condition separately under a name, and routes write only `match: "@name"`:

```text
matchers:
  blocked: {path: [/xmlrpc.php, "*.sql"]}   # definition: what kind of request this is
routes:
  - match: "@blocked"                       # use: how to handle it
    respond: {status: 403}
```

Remember three things:

1. **It is only a name.** `match: "@blocked"` is exactly equivalent to writing the definition inline under `match:`. It is expanded at load time; there is no runtime difference.
2. **Order and position don't matter.** Priority is decided by the condition itself; see [section 3](#3-which-route-matches-first-priority-rules).
3. **`@name` must be quoted.** `@` is reserved in YAML; without quotes you get a parse error.

---

## 1. Block scanners, split writes from reads

The typical use: block common scanner paths, send `POST` to a separate write service, and send everything else to the default backend.

<!-- case: matchers-basic -->
```yaml
site: example.com
matchers:
  blocked: {path: [/xmlrpc.php, /.env, "*.sql"]}
  post: {method: POST}
routes:
  - match: "@blocked"
    respond: {status: 403, body: forbidden}
  - match: "@post"
    proxy: localhost:8081
proxy: localhost:8080
```

```check
GET  http://example.com/xmlrpc.php          => 403 "forbidden"
GET  http://example.com/.env                => 403 "forbidden"
# * matches any characters including /, so .sql files in subdirectories are blocked too
GET  http://example.com/backup/db.sql       => 403 "forbidden"
# The wildcard matches the whole path: db.sql.txt does not end in .sql
GET  http://example.com/db.sql.txt          => 8080 /db.sql.txt
POST http://example.com/orders              => 8081 /orders
GET  http://example.com/orders              => 8080 /orders
```

---

## 2. Writing conditions

A named matcher accepts the same fields as an inline `match`:

| Field | Meaning | Example |
|---|---|---|
| `path` | A string: exact match; a list: any entry matches, `*` wildcards allowed | `/login`, `[/a, "/b/*"]` |
| `prefix` | Prefix match by path segment | `/api` |
| `method` | One or a list | `POST`, `[PUT, DELETE]` |
| `header` | Request header equals a value | `{X-Canary: "1"}` |
| `query` | Query parameter equals a value | `{debug: "1"}` |
| `rule` | Rule expression for complex cases | `` PathRegexp(`(?i)^/admin`) `` |

**Different fields are combined with AND; entries in a `path` list with OR.** Below, `api-write` means "`POST`/`PUT`/`DELETE` requests under `/api`", and `canary` means "requests with header `X-Canary: 1`":

<!-- case: matchers-combine -->
```yaml
site: api.example.com
matchers:
  api-write: {prefix: /api, method: [POST, PUT, DELETE]}
  canary: {header: {X-Canary: "1"}}
routes:
  - match: "@canary"
    proxy: localhost:8082           # canary: every request with the header goes to the new version
  - match: "@api-write"
    proxy: localhost:8081           # writes go to the primary service
/api:
  proxy: localhost:8080             # other /api requests go to the read-only service
respond: {status: 404, body: not found}
```

```check
PUT  http://api.example.com/api/orders/7             => 8081 /api/orders/7
GET  http://api.example.com/api/orders/7             => 8080 /api/orders/7
GET  http://api.example.com/api/orders/7 X-Canary: 1 => 8082 /api/orders/7
# POST but not under /api: only one of api-write's two conditions holds
POST http://api.example.com/upload                   => 404 "not found"
```

`path` wildcard details:

- Only `*` is a wildcard, matching zero or more characters (including `/`); `?` and `[]` are ordinary characters.
- It matches the **whole path** (without the query), so `"*.sql"` means "ends in `.sql`" and `"/admin/*"` means "anything under `/admin/`".
- Strings starting with `*` must be quoted in YAML.
- **Case-sensitive**: `/xmlrpc.php` does not block `/XMLRPC.PHP`. For security blocking, prefer `rule` with `(?i)`:

<!-- case: matchers-ignore-case -->
```yaml
site: example.com
matchers:
  blocked:
    rule: "PathRegexp(`(?i)^/xmlrpc\\.php$`) || PathRegexp(`(?i)\\.sql$`)"
routes:
  - match: "@blocked"
    respond: {status: 403}
proxy: localhost:8080
```

```check
GET http://example.com/xmlrpc.php      => 403
GET http://example.com/XMLRPC.PHP      => 403
GET http://example.com/dump/DB.SQL     => 403
GET http://example.com/index.php       => 8080 /index.php
```

---

## 3. Which route matches first: priority rules

As in Caddy, **routes with conditions are more specific than routes that only look at a path prefix**. Within a site, routes are tried in this order and the first match wins:

| Order | Route kind | Example |
|---|---|---|
| 1 | Routes with a higher explicit `priority` | `priority: 100` |
| 2 | Exact paths | `path: /login`, `path: [/login]` |
| 3 | Condition routes without `path` / `prefix` | `@blocked` (wildcard path), `@post`, `@canary` |
| 4 | Prefix routes, longest first | `/api/v2` before `/api` |
| 5 | Site-level action (fallback) | top-level `proxy`, `spa` |

So a blocking rule is not taken over by a prefix route such as `/api`:

<!-- case: matchers-order -->
```yaml
site: example.com
matchers:
  blocked: {path: ["*.sql"]}
routes:
  - match: "@blocked"
    respond: {status: 403}
  - match: {path: /export/report.sql}   # exact paths come before condition routes
    proxy: localhost:8081
/api:
  proxy: localhost:8080
spa: ./dist
```

```check
# The /api prefix route ranks after @blocked
GET http://example.com/api/backup.sql        => 403
GET http://example.com/api/orders            => 8080 /api/orders
# The exact path ranks before @blocked
GET http://example.com/export/report.sql     => 8081 /export/report.sql
GET http://example.com/settings              => 200 "<h1>dist</h1>"
```

Two things to note:

- **A method-only condition such as `@post` takes every request with that method on the site**, including those under `/api`. To limit it to a path, put `prefix` in the condition (see `api-write` in section 2).
- To make a condition route beat an exact path, give it a higher `priority`.

---

## 4. Adding conditions to a named matcher

`match` can also be a list whose items must **all** hold: each item is `"@name"`, an inline condition, or a `/prefix` shorthand. One named matcher can then be reused by several routes, each adding its own condition:

<!-- case: matchers-compose -->
```yaml
site: api.example.com
matchers:
  api: {prefix: /api, header: {X-Tenant: acme}}
  api-write: ["@api", {method: [POST, PUT, DELETE]}]   # definitions can compose too
routes:
  - match: "@api-write"
    proxy: localhost:8081
  - match: ["@api", {query: {debug: "1"}}]
    proxy: localhost:8082
  - match: "@api"
    proxy: localhost:8080
respond: {status: 404, body: not found}
```

```check
PUT  http://api.example.com/api/orders/7 X-Tenant: acme          => 8081 /api/orders/7
GET  http://api.example.com/api/orders/7?debug=1 X-Tenant: acme  => 8082 /api/orders/7?debug=1
GET  http://api.example.com/api/orders/7 X-Tenant: acme          => 8080 /api/orders/7
# Missing X-Tenant: all three routes require @api, so none matches
PUT  http://api.example.com/api/orders/7                         => 404 "not found"
```

Merge rules:

- `rule` values are joined with AND; `header` and `query` are merged, but the same key cannot appear twice (`header` is case-insensitive).
- `prefix`, `path`, `method` and the other fields may come from only one item. The same value in two items is fine; different values are an error rather than silently picking one.
- Lists cannot be nested. For layering, define matchers under `matchers` and reference them by name. Matchers may reference each other; cycles are an error.

<!-- expect-error: composed matchers set conflicting prefix -->
```yaml
site: example.com
matchers:
  api: {prefix: /api}
routes:
  - match: ["@api", {prefix: /admin}]
    respond: ok
proxy: localhost:8080
```

---

## 5. When not to use named matchers

- **A single path prefix**: write the path key `/api:` directly; it is shorter than `matchers`.
- **Several routes sharing auth, rate limits and other policies**: that is governance; use [snippets](03-governance.md#5-share-one-policy-across-apis-snippets), not matchers.
- **Security policy that must run before every route**: `@blocked` is an ordinary rejecting route and only protects while it ranks first. If you use `priority` to rank other routes ahead of it, those routes are not protected. Blocking that must cover the whole site belongs in a `use` middleware.

---

## 6. Common errors

### Missing quotes

<!-- expect-error: found character that cannot start any token -->
```yaml
site: example.com
matchers:
  post: {method: POST}
routes:
  - match: @post
    proxy: localhost:8081
proxy: localhost:8080
```

`@` cannot start an unquoted YAML string; write `match: "@post"`.

### Reference to a name that doesn't exist

<!-- expect-error: undefined matcher reference -->
```yaml
site: example.com
matchers:
  post: {method: POST}
routes:
  - match: "@posts"
    proxy: localhost:8081
proxy: localhost:8080
```

Names are case-sensitive. References look in this site's `matchers` first, then in shared definitions in `sites/_shared.yaml`; definitions in other site files are not visible.

### Empty definition or misspelled field

<!-- expect-error: at least one match criterion is required -->
```yaml
site: example.com
matchers:
  empty: {}
proxy: localhost:8080
```

Definitions are validated even when no route references them; a misspelled field (such as `methods`) is also an error.

### Wildcard path not starting with `/` or `*`

<!-- expect-error: path must start with / -->
```yaml
site: example.com
matchers:
  blocked: {path: [xmlrpc.php]}
routes:
  - match: "@blocked"
    respond: {status: 403}
proxy: localhost:8080
```

### The same condition on two routes

<!-- expect-error: duplicate normalized match -->
```yaml
site: example.com
matchers:
  post: {method: POST}
routes:
  - match: "@post"
    proxy: localhost:8081
  - match: {method: post}      # expands to the same as @post (methods are case-insensitive)
    proxy: localhost:8082
proxy: localhost:8080
```

When two routes have identical conditions, the second can never match, so it is an error. To reuse one named matcher, add a different condition per route with a list (see [section 4](#4-adding-conditions-to-a-named-matcher)).

For every field, see the [site configuration reference](../03-configuration/site-config.md#named-request-matchers).
