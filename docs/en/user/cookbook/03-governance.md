# Governance: CORS, Headers, Rate Limits, Access Control

These features are written directly under a route (or the site), next to `proxy` / `file_server`. No middleware definition is needed first.

---

## 1. Enable CORS for an API

The frontend is at `https://web.example.com`, the API at `api.example.com`:

<!-- case: cors -->
```yaml
site: api.example.com
/api:
  proxy: localhost:8080
  cors:
    allowed_origins: [https://web.example.com]
    allowed_methods: [GET, POST, PUT, DELETE, OPTIONS]
    allowed_headers: [Content-Type, Authorization]
    allow_credentials: true
    max_age: 86400          # cache preflight results for a day, fewer OPTIONS requests
```

```check
# Browser preflights are answered by the gateway and never reach the backend
OPTIONS http://api.example.com/api/orders Origin: https://web.example.com Access-Control-Request-Method: POST => 204; Access-Control-Allow-Origin: https://web.example.com; Access-Control-Allow-Credentials: true
GET     http://api.example.com/api/orders Origin: https://web.example.com => 8080 /api/orders; Access-Control-Allow-Origin: https://web.example.com
# Origins not on the list get no CORS permission
GET     http://api.example.com/api/orders Origin: https://evil.example   => 8080 /api/orders; Access-Control-Allow-Origin: (none)
```

- For public APIs without cookies you can write `allowed_origins: ["*"]`; `*` cannot be combined with `allow_credentials: true`.

---

## 2. Security response headers + headers for the backend

<!-- case: headers -->
```yaml
site: app.example.com
response_headers:                 # site level: added to every response
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  Strict-Transport-Security: max-age=31536000
/api:
  proxy: localhost:8080
  request_headers:                # sent to the backend only
    X-Gateway: litegate
    X-Client-IP: "{ip}"
  response_headers:
    Cache-Control: no-store       # route level: merged with the site level; route wins on conflicts
file_server: ./public
```

```check
GET http://app.example.com/              => 200 "<h1>public</h1>"; X-Frame-Options: DENY; Cache-Control: (none)
GET http://app.example.com/api/me from 198.51.100.7 => 8080 /api/me; Echo-X-Gateway: litegate; Echo-X-Client-Ip: 198.51.100.7; X-Frame-Options: DENY; Cache-Control: no-store
```

- `request_headers` only applies to `proxy`; writing it on a static-file route is an error.
- Common variables: `{ip}` client IP, `{host}` request host, `{header.X-Name}` a request header, `{query.name}` a query parameter.

---

## 3. Rate limiting

<!-- case: rate-limit -->
```yaml
site: api.example.com
/api/sms:
  proxy: localhost:8080
  rate_limit: 2            # 2 requests per second (burst is also 2)
/api:
  proxy: localhost:8080    # other APIs are unlimited
```

```check
POST http://api.example.com/api/sms/send   => 8080 /api/sms/send
POST http://api.example.com/api/sms/send   => 8080 /api/sms/send
POST http://api.example.com/api/sms/send   => 429
GET  http://api.example.com/api/orders     => 8080 /api/orders
```

- This quota is **shared by every client of the route**: once one client uses it up, others are rejected too.

Count per client IP instead (like Nginx `limit_req zone=$binary_remote_addr`):

<!-- case: rate-limit-per-ip -->
```yaml
site: api.example.com
/api/login:
  proxy: localhost:8080
  rate_limit: {rate: 1, key: ip}    # 1 per second per IP
```

```check
POST http://api.example.com/api/login from 198.51.100.1  => 8080 /api/login
POST http://api.example.com/api/login from 198.51.100.1  => 429
# Another IP is not affected
POST http://api.example.com/api/login from 198.51.100.2  => 8080 /api/login
```

- The client IP follows the global trusted-proxy settings. Behind a CDN or load balancer, configure trusted proxies first, otherwise everyone shares the proxy's IP.
- Per-IP keys work only with the default `static` policy; `rate_limit_policy: adaptive` adjusts overall by machine load and cannot split by IP.
- Concurrently tracked clients are capped (100,000). Beyond that, new clients temporarily share the route quota, so forged IP floods cannot exhaust memory.
- For quotas shared across routes see [Rate Limit](../05-middleware/rate-limit.md); `limit_conn` caps in-flight requests and suits slow endpoints.

---

## 3.1 Hide backend details, block forged identity headers

A `-` before a header name deletes it (like Nginx `proxy_hide_header` and `proxy_set_header X "";`):

<!-- case: header-delete -->
```yaml
site: api.example.com
response_headers:
  -Server: ""             # drop the backend's software and version
  -X-Powered-By: ""
/api:
  proxy: localhost:8080
  request_headers:
    -X-User-Id: ""        # discard client-supplied identity headers; the backend sets them after auth
```

```check
GET http://api.example.com/api/me X-User-Id: admin => 8080 /api/me; Echo-X-User-Id: (none); Server: (none)
```

- Deleted headers must have an empty string value; the same header cannot be both deleted and set.
- If the site deletes a header and a route sets it again, the route wins.

---

## 4. Admin area from the internal network only

<!-- case: ip-restriction -->
```yaml
site: app.example.com
/admin:
  proxy: localhost:8081
  ip_restriction:
    allow_ips: [10.0.0.0/8, 192.168.0.0/16]
proxy: localhost:8080
```

```check
GET http://app.example.com/admin/users from 10.1.2.3      => 8081 /admin/users
GET http://app.example.com/admin/users from 203.0.113.9   => 403
GET http://app.example.com/products    from 203.0.113.9   => 8080 /products
```

- Use `deny_ips` for a block list instead. At site level it applies to the whole site.
- Behind a CDN or load balancer, set trusted proxies in the global configuration, otherwise you see the proxy's IP.

---

## 5. Share one policy across APIs (snippets)

Several backends need the same CORS and response headers, without copying them everywhere:

<!-- case: snippets -->
```yaml
site: api.example.com
snippets:
  public-api:
    cors:
      allowed_origins: ["*"]
      allowed_methods: [GET, POST, OPTIONS]
      allowed_headers: [Content-Type]
    response_headers:
      X-Content-Type-Options: nosniff
      X-Api-Version: "1"
/users:
  import: public-api
  proxy: localhost:8080
/orders:
  import: public-api
  response_headers:
    X-Api-Version: "2"     # a local header overrides the snippet's
  proxy: localhost:8081
```

```check
GET http://api.example.com/users/1  Origin: https://any.example => 8080 /users/1; Access-Control-Allow-Origin: *; X-Content-Type-Options: nosniff; X-Api-Version: 1
GET http://api.example.com/orders/1 Origin: https://any.example => 8081 /orders/1; Access-Control-Allow-Origin: *; X-Api-Version: 2
```

- Snippets hold governance fields only (cors, auth, rate limits, response headers, strip_prefix, use, ...), **not actions such as proxy / file_server, and not paths**.
- Apart from request/response headers, which may be overridden locally, repeating a snippet field (such as cors) locally is an error, so nothing is silently overridden.
- A route can import several snippets: `import: [public-api, audit]`.
