# LiteGate FastCGI Configuration Guide

This document explains how to reverse-proxy requests to a **FastCGI** backend (most commonly **PHP-FPM**) from a LiteGate YAML site config, so LiteGate can serve PHP / WordPress / Laravel and similar environments directly.

For ordinary PHP websites, prefer the [site-level `php` shorthand](user/03-configuration/site-config.md#php-websites-wordpress--laravel): configure the website root and PHP-FPM address to automatically handle static files, directory indexes and front-controller fallback. The lower-level configuration below remains available for custom routing.

> Use case: replace the Nginx role in a typical "Nginx + php-fpm" stack — LiteGate talks to php-fpm directly over a TCP port or a Unix socket.

---

## 1. Minimal config (TCP)

Assuming php-fpm listens on `127.0.0.1:9000` and the site code lives at `/var/www/html` on the backend:

```yaml
domain: example.com
routes:
  - name: php-route
    match:
      path: /index.php
    action:
      type: proxy
      upstream_type: static
      proto: fastcgi                 # Required: declare the FastCGI protocol
      fastcgi_root: /var/www/html    # Required: backend Document Root (base for SCRIPT_FILENAME)
      upstream:
        - "fastcgi://127.0.0.1:9000" # FastCGI backend address
```

Only three fields are required: **`proto: fastcgi`** + **`fastcgi_root`** + **`upstream`**.

---

## 2. Using a Unix socket

When php-fpm uses a Unix socket (better performance, no TCP overhead), set `upstream` to `unix://` followed by the absolute socket path:

```yaml
action:
  type: proxy
  upstream_type: static
  proto: fastcgi
  fastcgi_root: /var/www/html
  upstream:
    - "unix:///var/run/php/php8.2-fpm.sock"   # Note the three slashes: unix:// + /absolute/path
```

> Unix sockets require Unix Domain Socket support on both the LiteGate and PHP-FPM hosts. On Windows, prefer `fastcgi://127.0.0.1:9000`. A Windows Named Pipe is not a Unix socket and is not currently accepted as a FastCGI upstream.

---

## 3. Supported upstream forms

| Form | Notes |
|---|---|
| `fastcgi://127.0.0.1:9000` | TCP, **port required** |
| `fastcgi://[::1]:9000` | IPv6 + port |
| `unix:///var/run/php-fpm.sock` | Unix socket, **three slashes** + absolute socket path |
| `127.0.0.1:9000` | Bare TCP address (equivalent to `fastcgi://`), port still required |

A FastCGI route's `upstream` **only accepts** `fastcgi://` / `unix://` / bare `host:port`. Schemes such as `http://` or `ftp://` are rejected at load time.

---

## 4. Full field reference

| Field | Type | Default | Description |
|---|---|---|---|
| `proto` | string | — | **Required**, must be `fastcgi` to enable FastCGI. If any `fastcgi_*` field is set while `proto` is not `fastcgi`, loading fails |
| `fastcgi_root` | string | — | **Required**, backend Document Root; joined with the script path to form `SCRIPT_FILENAME` |
| `upstream` | list | — | **Required**, list of backend addresses (see table above); multiple entries are load-balanced |
| `index` | string | `index.php` | Entry file appended when the request path ends with `/` |
| `fastcgi_split_path` | string | `.php` | PATH_INFO split point, must contain `.`; splits `/a.php/b` into script `/a.php` + PATH_INFO `/b` |
| `fastcgi_extensions` | list | `[".php"]` | **Allowlist of executable extensions**; each entry must start with `.` (e.g. `.php`), or use `*` to allow all |
| `fastcgi_params` | map | `{}` | Additional safe CGI variables such as `APP_ENV` and `REDIRECT_STATUS`; built-in variables such as `SCRIPT_FILENAME`, `REQUEST_URI`, and `HTTP_*` cannot be overridden |
| `fastcgi_keep_conn` | bool | `false` | Enable **connection pooling / reuse** to the backend (like Nginx `fastcgi_keep_conn`) |
| `fastcgi_max_idle_conns` | int | `2` | Max idle connections kept in the pool; cannot be negative |
| `fastcgi_idle_timeout` | int | `0` | Idle connection reclaim time (seconds); `0` means never reclaim on idle; cannot be negative |
| `timeout` | int | `0` | Hard timeout for the whole request/response (seconds); `0` means no hard timeout |
| `host` | string | — | Override `HTTP_HOST` / `SERVER_NAME` sent to the backend |
| `strip_prefix` / `prepend_prefix` | string | — | Path rewriting; also affects `SCRIPT_NAME` and `SCRIPT_FILENAME` |

---

## 5. Enabling the connection pool (keep-alive)

By default each request opens a fresh connection to the backend and closes it afterward. For high-concurrency PHP workloads, enabling connection reuse cuts connection-setup overhead significantly:

```yaml
action:
  type: proxy
  upstream_type: static
  proto: fastcgi
  fastcgi_root: /var/www/html
  upstream:
    - "unix:///var/run/php/php8.2-fpm.sock"
  fastcgi_keep_conn: true          # enable connection pooling
  fastcgi_max_idle_conns: 16       # keep up to 16 idle connections
  fastcgi_idle_timeout: 60         # reclaim after 60s idle
  timeout: 30                      # max 30s per request
```

> A connection is returned to the pool only after the response has been **fully and cleanly read**. Connections from early client disconnects or interrupted uploads are closed outright, so they never corrupt the next request. Before reuse, a lightweight liveness probe discards stale connections that the backend already closed.

---

## 6. PATH_INFO and sub-paths

`fastcgi_split_path` (default `.php`) splits the path into "script + PATH_INFO". For example, a request to `/app.php/user/42`:

- `SCRIPT_NAME` = `/app.php`
- `PATH_INFO` = `/user/42`
- `SCRIPT_FILENAME` = `<fastcgi_root>/app.php`

The split uses a greedy "last match followed by `/` or end-of-path" rule, matching Nginx's `fastcgi_split_path_info ^(.+\.php)(/.+)$` behavior.

---

## 7. Auto-injected CGI environment variables

LiteGate builds and passes these variables to the backend automatically — **no manual config needed**:

`REQUEST_METHOD`, `REQUEST_URI`, `QUERY_STRING`, `CONTENT_TYPE`, `CONTENT_LENGTH`, `GATEWAY_INTERFACE`, `SERVER_PROTOCOL`, `SCRIPT_FILENAME`, `SCRIPT_NAME`, `PATH_INFO`, `PATH_TRANSLATED`, `DOCUMENT_ROOT`, `DOCUMENT_URI`, `REMOTE_ADDR`, `REMOTE_PORT`, `SERVER_ADDR`, `SERVER_PORT`, `SERVER_NAME`, `HTTP_HOST`, plus all `HTTP_*` request headers. When the client uses HTTPS, `HTTPS=on` is also set.

Add application variables with `fastcgi_params`:

For TLS termination at a load balancer, configure its actual address in global `real_ip.trusted_proxies`. A trusted direct peer supplying a single `X-Forwarded-Proto: https` sets `HTTPS=on` and, when Host omits a port, `SERVER_PORT=443`. Untrusted sources, repeated values and comma-separated protocol chains are not accepted.

```yaml
fastcgi_params:
  APP_ENV: production
  REDIRECT_STATUS: "200"
```

Names may contain uppercase letters, digits, and underscores, and cannot start with a digit. Built-in CGI and `HTTP_*` variables cannot be overridden, preserving script-path and request safety checks.

---

## 8. Security notes

- **Extension allowlist**: by default only `.php` is treated as an executable script. A request like `/uploads/avatar.jpg` (non-allowlisted extension) is rejected by the gateway, preventing uploaded files from being executed by mistake. **Avoid** setting `fastcgi_extensions` to `*` carelessly.
- **Path traversal protection**: requests containing `..` segments, or that would escape `fastcgi_root` after joining, are blocked.
- **httpoxy protection**: the `Proxy` request header is never passed through as `HTTP_PROXY`.

---

## 9. Limitations

LiteGate does not embed a PHP runtime or start/manage PHP-FPM. PHP scripts are executed by a separate PHP-FPM service.

Front-controller applications such as WordPress and Laravel can use the `serve` action's `try_files` fallback to internally redirect missing clean URLs to `/index.php`. The redirect preserves the client-visible `REQUEST_URI` and query string. `try_files` is not accepted on a `proxy` action; invalid configurations fail during loading.

Because `serve` checks LiteGate's local filesystem, LiteGate and a remote PHP-FPM service must share the site tree, or static assets must be deployed to a directory visible to LiteGate.

---

## 10. Complete example

```yaml
domain: php.example.com
routes:
  # Execute PHP scripts and PATH_INFO requests with PHP-FPM.
  - name: php-scripts
    priority: 100
    match:
      rule: 'PathRegex("(?i)^/.*\.php(?:/.*)?$")'
    action:
      type: proxy
      upstream_type: static
      proto: fastcgi
      fastcgi_root: /var/www/html
      index: index.php
      fastcgi_split_path: ".php"
      fastcgi_extensions: [".php"]
      fastcgi_params:
        APP_ENV: production
        REDIRECT_STATUS: "200"
      upstream:
        - "unix:///var/run/php/php8.2-fpm.sock"
      fastcgi_keep_conn: true
      fastcgi_max_idle_conns: 16
      fastcgi_idle_timeout: 60
      timeout: 30

  # Serve static files and route missing clean URLs to the front controller.
  - name: php-static-and-front-controller
    match:
      path_prefix: /
    action:
      type: serve
      root: /var/www/html
      try_files:
        - "{path}"
        - "/index.php"
```

---

Related docs: [Site Config](user/03-configuration/site-config.md) · [proxy action](user/04-actions/proxy.md)
