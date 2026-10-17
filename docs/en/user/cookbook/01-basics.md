# Basics: Get a Site Running

Each recipe is a complete site file. Put it in the `sites/` directory (for example `sites/app.yaml`) and it is hot-reloaded.
The "result" blocks show what LiteGate does with each request.

> How to read them: `=> 8080 /orders` means the request is forwarded to `localhost:8080` and the backend sees the path `/orders`;
> `=> 404` means the gateway answers 404 itself. Every recipe is executed by automated tests and can be copied as is.

---

## 1. Reverse proxy one backend

The most common case: everything for a domain goes to local port 8080.

<!-- case: reverse-proxy -->
```yaml
site: api.example.com
proxy: localhost:8080
```

Result:

```check
GET http://api.example.com/v1/users       => 8080 /v1/users
GET http://api.example.com/?page=2        => 8080 /?page=2
# Requests for other domains do not enter this site
GET http://other.example.com/             => 404
```

- Path and query are passed to the backend unchanged.
- `proxy` also accepts `192.168.1.20:8080` or `http://backend:8080`.

---

## 2. Load balancing + health checks

<!-- case: load-balance -->
```yaml
site: api.example.com
proxy:
  to: [localhost:8080, localhost:8081]
  lb: least_conn        # default round_robin; also ip_hash, p2c, cookie, ...
  health: /health       # probed periodically; failing nodes are removed
  timeout: 5s
  retry: 2              # retry on another node when the connection fails
```

```check
GET http://api.example.com/orders         => 8080|8081 /orders
```

- With only addresses and no other options, the short form is `proxy: localhost:8080, localhost:8081`.
- To share one backend group across sites, see [named services](../03-configuration/services.md).

---

## 3. Static website

<!-- case: static-site -->
```yaml
site: www.example.com
file_server: ./public
```

```check
GET http://www.example.com/               => 200 "<h1>public</h1>"
GET http://www.example.com/about.html     => 200 "<h1>about</h1>"
GET http://www.example.com/missing.html   => 404
```

- `file_server` and `serve` are the same thing; use whichever you prefer.
- To set the index file or cache headers, use the object form: `file_server: {root: ./public, index: home.html, cache_control: "max-age=3600"}`.

---

## 4. Serve by port only (any host)

Internal tools and test environments often have only an IP and a port, no domain.

<!-- case: port-only -->
```yaml
site: :9090
proxy: localhost:8080
```

```check
GET http://192.168.1.10:9090/dashboard    => 8080 /dashboard
GET http://anything.local:9090/           => 8080 /
```

- `:9090`, `"*:9090"` and `0.0.0.0:9090` are equivalent: accept any Host on port 9090.
- A value starting with `*` must be quoted in YAML: `site: "*:9090"`.
- With `site: :9090`, do not also write `port:`; that is an error.

---

## 5. Enable HTTPS

<!-- case: https -->
```yaml
site: www.example.com
https: true
file_server: ./public
```

```check
GET http://www.example.com/about.html     => 308; Location: https://www.example.com/about.html
```

- `https: true` permanently redirects HTTP to HTTPS. Certificates are issued by global auto cert; see [Auto-Cert](../06-certificates/auto-cert.md).
- **v2 defaults to `https: false`**, unlike Caddy: even `site: example.com:443` does not turn it on. Write `https: true` explicitly.

---

## 6. Respond directly (health checks, maintenance pages)

<!-- case: respond -->
```yaml
site: status.example.com
respond: ok
```

```check
GET http://status.example.com/ping        => 200 "ok"
```

> `/healthz`, `/readyz`, `/metrics`, `/_litegate` and similar paths are reserved by the gateway. Don't route them in a site; for example `/healthz` is answered by the gateway itself.

Use the object form for a custom status and content type, for example a temporary maintenance page:

<!-- case: maintenance -->
```yaml
site: shop.example.com
respond:
  status: 503
  content_type: text/html; charset=utf-8
  body: <h1>Under maintenance, back in about 30 minutes</h1>
```

```check
GET http://shop.example.com/cart          => 503 "Under maintenance"
```
