# Proxy Action (Reverse Proxy)

The `proxy` action is the most critical component of LiteGate, responsible for forwarding inbound traffic downstream to backend upstream instances. It integrates seamlessly with static declarations and dynamic discovery providers, offering robust load balancing, streaming, and high-availability operations.

---

## 1. Basic Configuration (Static Upstreams)

Designed for scenarios where backend server IPs are fixed and declared directly inside the site configuration.

```yaml
action:
  type: proxy
  upstream_type: static
  upstream:
    - "10.0.0.5:8080"
    - "10.0.0.6:8080"
  lb_policy: round_robin # Balancing policies: round_robin, ip_hash, weighted_round_robin, p2c (Power of Two Choices)
```

### HTTP upstreams over Unix sockets

An ordinary HTTP backend may listen only on a Unix socket. Clients can still
use HTTPS, HTTP/2, or HTTP/3 to LiteGate; the backend hop uses HTTP/1.1:

```yaml
domain: app.localhost
routes:
  - match: { path_prefix: / }
    action:
      type: proxy
      upstream: ["unix:///run/apps/app.sock"]
```

A wildcard site can safely map the request Host to a socket in one directory:

```yaml
domain: "*.localhost"
routes:
  - match: { path_prefix: / }
    action:
      type: proxy
      upstream: ["unix:///run/apps/{host}.sock"]
```

For example, `foo.localhost` selects `/run/apps/foo.localhost.sock`. `{host}`
may occur once and only in the filename. Request hosts must be valid ASCII DNS
names—not IP addresses or paths—and the expanded path must remain in the
configured directory and fit the 107-byte socket-path limit. Unix HTTP
upstreams support ordinary requests and Upgrade/WebSocket traffic, but not
upstream TLS, HTTP/2, or active health checks yet. Dynamic templates are
rejected on catch-all sites such as `*` and `0.0.0.0`; use an explicit or
wildcard site domain to bound the selectable Hosts. Keep only sockets exposed
by that site in the directory; socket and parent-directory permissions remain
the final security boundary. `action.host` changes only the HTTP Host header
sent upstream—the socket path is always selected from the original request Host.

---

## 2. Dynamic Discovery Integrations (Service Discovery)

Automate scaling: LiteGate continuously monitors and synchronizes instances directly from discovery registries without manual configuration changes. Dynamic sources include `litemesh`, `litedeploy`, `docker`, `consul`, and `discovery`. The `discovery` source is the configuration name for a blocking-query external aggregation layer such as `camodns_discovery`.

### Consul Integration
```yaml
action:
  type: proxy
  upstream_type: consul
  service_name: order-service
```

### Litemesh Service Mesh Integration
```yaml
action:
  type: proxy
  upstream_type: litemesh
  service_name: user-api
  mtls: true # Activates high-performance secure mTLS handshakes between edge gateway and backend containers
```

### LiteDeploy / Docker / Discovery Integration
```yaml
action:
  type: proxy
  upstream_type: litedeploy # can also be docker or external
  service_name: payment-api
```

> [!NOTE]
> Global `service_discovery.catalogs[].provider: discovery` maps to runtime `upstream_type: external`. If routes are generated from tags, LiteGate records the correct source internally, so most users do not need to write `upstream_type` by hand.

---

## 3. Advanced Steering & Proxy Settings

### Path Trimming (`strip_prefix`)
If you map ingress routes to `/api/v1` but downstream upstreams are listening on the root path `/`, strip prefix definitions before proxying:
```yaml
  strip_prefix: true # Automatically strips the path prefix match matched in your route definition
```

### Real-Time Streaming & Server-Sent Events (`flush_interval`)
For push APIs (such as Server-Sent Events, Model Context Protocol, or WebSockets) and large file download pipelines, bypass response buffering to achieve instant flush cycles:
```yaml
  flush_interval: -1 # Deactivates buffer flush latency buffers, enabling immediate network writes (critical for SSE, WS, and MCP)
```

### Upstream Timeout
```yaml
  timeout: 30   # whole-request timeout; Upgrade requests use it for the handshake only
  retry: 1      # must be non-negative; unsafe requests retry only when not sent
```

### Backends That Do Not Accept Chunked Requests

`disable_chunked: true` buffers the request body to calculate `Content-Length`. The current per-request buffer limit is 2 MiB; larger bodies receive `413` instead of silently falling back to chunked transfer. Traffic mirroring copies only safely replayable small bodies. Unknown-length or large streaming bodies skip mirroring without affecting the primary request.

---

## 4. Active Telemetry & Health Checks

LiteGate continually inspects backend upstream health, pulling failed instances out of rotation.

```yaml
  health_check:
    enabled: true
    path: "/health"      # Query endpoint evaluated during inspections
    interval: 10s       # Intercept polling interval duration
    timeout: 3s         # Outgoing dial check timeout
```

---

## 5. Built-In WebSocket Upgrades

LiteGate features native out-of-the-box support for WebSocket connections. The gateway automatically detects upgrade headers and transitions connections to full-duplex channels without extra configuration. `timeout` bounds connection establishment and the Upgrade handshake, not the lifetime of an established tunnel. HTTPS/WSS upstreams also honor `root_ca`, SNI, and mTLS verification.

---

## 6. gRPC (`proto: grpc`)

Set `proto: grpc` to proxy gRPC backends as a first-class protocol. The gateway forces HTTP/2 and transparently forwards gRPC trailers (`grpc-status`, `grpc-message`, `grpc-status-details-bin`).

```yaml
action:
  type: proxy
  proto: grpc                 # gRPC over cleartext HTTP/2 (h2c)
  upstream:
    - "127.0.0.1:50051"
```

- **Cleartext (h2c)**: `proto: grpc` talks to the backend over plaintext HTTP/2 — the common case for internal services.
- **TLS / mTLS**: enabling `mtls: true` automatically upgrades the connection to TLS-based HTTP/2 (`grpcs`); no separate flag is needed.

```yaml
action:
  type: proxy
  proto: grpc
  upstream_type: litemesh
  service_name: order-grpc
  mtls: true                  # gRPC over mTLS (auto-upgraded to grpcs)
```

> gRPC reflection-based routing is planned for a later phase.

> [!NOTE]
> **Retry limitation for gRPC status 14**: The gateway only retries when the failure status is returned in the initial headers (headers-only response). If the error status (such as `grpc-status=14`) is sent in the trailing headers after data has already been written to the client, a retry is impossible as the response body has already started transmitting.

---

## 7. Cookie Session Stickiness (`lb_policy: cookie`)

`lb_policy: cookie` pins a client to the same backend across requests — useful for stateful sessions and long-lived connections. The gateway issues an encrypted cookie identifying the chosen backend and routes subsequent requests accordingly.

```yaml
action:
  type: proxy
  upstream:
    - "10.0.0.5:8080"
    - "10.0.0.6:8080"
  lb_policy: cookie
  sticky_cookie_name: "LG_STICKY_BACKEND"   # optional, this is the default
  sticky_cookie_ttl: 1800                    # optional, seconds (default 1800 = 30m)
```

- The cookie value is **AES-GCM encrypted** (backend address is neither exposed nor forgeable), `HttpOnly`, `SameSite=Lax`, and `Secure` over HTTPS.
- If the pinned backend is unhealthy, the gateway falls back to round-robin and re-pins.
- A cookie is written even with a single backend, so already-connected clients don't drift when the pool scales out later.

### Multi-node consistency (`sticky_key`)

By default each process uses a random encryption key, so a cookie issued by node A cannot be decrypted by node B. For a multi-node deployment, set a shared 32-byte hex key in `config.yaml`:

```yaml
sticky_key: "0102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f20"
```

---

## 8. URL Rewrite (`rewrite`)

`rewrite` rewrites the request path via a regular expression **before** any WAF, IP policy, auth, or rate-limit middleware runs — so security controls always inspect the final, rewritten path.

```yaml
action:
  type: proxy
  upstream: ["127.0.0.1:8080"]
  rewrite:
    pattern: "^/old/(.*)$"     # Go regular expression
    target: "/new/$1"          # replacement ($1, $2 … capture groups)
```

| Field | Type | Description |
| :--- | :--- | :--- |
| `pattern` | string | Go regexp matched against `URL.Path`; invalid patterns fail at config load |
| `target` | string | Replacement, supports `$1`/`$2` capture references |

> `rewrite` only changes the path within the matched route — it does not re-run route matching (unlike Nginx `rewrite ... last`). For "clean URL → entry script" fallback (WordPress/Laravel, SPA), see [`try_files`](./serve.md#5-try_files).
