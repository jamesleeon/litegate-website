# Common Errors

Each example below is a **wrong configuration**, followed by the error LiteGate reports when loading it (an excerpt) and the correct form.
When you hit an error, search this page for the English keywords in it.

Run `litegate -t -config config.yaml` to check every site file without restarting.

---

## 1. `domain` copied from an old config

<!-- expect-error: site and domain cannot be combined -->
```yaml
site: app.example.com
domain: app.example.com
proxy: localhost:8080
```

New files use only `site`. Don't mix in legacy `domain`, `force_https` or `routes[].action`; see the mapping in [site configuration](../03-configuration/site-config.md#legacy-fields-versus-v2).

---

## 2. Two actions in one route

<!-- expect-error: exactly one terminal action is required -->
```yaml
site: app.example.com
/static:
  file_server: ./public
  spa: ./dist
```

`proxy`, `file_server`/`serve`, `spa`, `respond`, `redirect` and the other actions are one per route. For "serve the file, fall back to index" write only `spa`.

---

## 3. Port written twice

<!-- expect-error: port is already specified in site -->
```yaml
site: :9090
port: 9090
proxy: localhost:8080
```

`site: :9090` already contains the port; remove `port`.

---

## 4. Unquoted leading `*`

<!-- expect-error: did not find expected alphabetic or numeric character -->
```yaml
site: *:9090
proxy: localhost:8080
```

`*` has a special meaning in YAML. Write `site: "*:9090"`, or simply `site: :9090`.

---

## 5. The same path both case-sensitive and case-insensitive

<!-- expect-error: duplicate normalized match -->
```yaml
site: api.example.com
/goapi:
  proxy: localhost:8080
~/goapi:
  proxy: localhost:8081
```

Pick one. To accept any case, keep only `~/goapi`.

---

## 6. `strip_prefix` on an exact path

<!-- expect-error: true requires a prefix match -->
```yaml
site: api.example.com
routes:
  - match: {path: /api/login}
    proxy: localhost:8080
    strip_prefix: true
```

`strip_prefix` only makes sense for prefix matches (path key `/api:` or `match: {path_prefix: /api}`).

---

## 7. `request_headers` on static files

<!-- expect-error: route request headers require proxy -->
```yaml
site: www.example.com
/docs:
  file_server: ./public
  request_headers:
    X-Env: prod
```

`request_headers` are sent to a backend, so they only work with `proxy`. To add headers for the browser use `response_headers`.

---

## 8. Site-level cors with child routes

<!-- expect-error: with child routes, put root processing in an explicit / route -->
```yaml
site: api.example.com
cors:
  allowed_origins: ["*"]
/users:
  proxy: localhost:8080
/orders:
  proxy: localhost:8081
```

With child routes, site-level cors / auth / rate limits would apply only to the fallback root route, not to `/users` or `/orders`. To avoid the impression that they cover the whole site, this is an error.
To apply them to the fallback only, put them in an explicit `/:` route; to apply them to each API, write them on each route or reuse them with [snippets](03-governance.md#5-share-one-policy-across-apis-snippets):

<!-- case: cors-per-route -->
```yaml
site: api.example.com
snippets:
  open: {cors: {allowed_origins: ["*"]}}
/users:
  import: open
  proxy: localhost:8080
/orders:
  import: open
  proxy: localhost:8081
```

---

## 9. A backend address inside a snippet

<!-- expect-error: snippets accept route governance only -->
```yaml
site: api.example.com
snippets:
  backend:
    proxy: localhost:8080
/users:
  import: backend
```

Snippets hold governance only; write `proxy` in the route that imports the snippet. To share one backend group, use `services` + `service: name`.

---

## 10. The same policy in a snippet and locally

<!-- expect-error: field conflicts with imported configuration -->
```yaml
site: api.example.com
snippets:
  limited: {rate_limit: 100}
/sms:
  import: limited
  rate_limit: 5
  proxy: localhost:8080
```

Except for request/response headers, a snippet field cannot be written again locally (so you never think it is 5 when it is really 100).
For a different value, split into two snippets, or don't import this one on that route.

---

## 11. Reference to an undefined middleware

<!-- expect-error: undefined middleware reference -->
```yaml
site: api.example.com
use: [audit-log]
proxy: localhost:8080
```

Names in `use` must be defined under `middlewares` in the same file; see [middleware](../05-middleware/pipeline.md).

---

## Traps that don't raise errors

- **HTTPS is off by default.** New files default to `https: false`; even `site: example.com:443` does not turn it on. Write `https: true`.
- **Reserved paths.** `/healthz`, `/readyz`, `/metrics`, `/_litegate` and similar are used by the gateway. Don't route them in a site (the gateway takes them over, and release validation reports an error).
- **Prefixes match by path segment.** `/api` does not match `/apix`; to match arbitrary prefix characters use `routes` + `match.rule`.
- **`redirect: <url>` short form is 302.** For a permanent redirect write `redirect: {location: ..., status: 301}`.
