# HTTPS and L4 TCP on One Port 443

LiteGate can use the SNI in the TLS ClientHello to carry both ordinary HTTPS sites and non-HTTP layer-4 TCP services on the same public TCP/443 entry. Matching connections can be passed through with TLS untouched, or have TLS terminated by LiteGate and then be forwarded to a TCP or Unix domain socket upstream.

This suits cases where:

- the public network, firewall or load balancer only allows 443;
- many HTTPS sites already use `websecure`, and you also need custom TLS, database front tunnels, RPC or proxy protocols;
- local backends prefer Unix sockets to avoid exposing extra loopback TCP ports;
- HTTPS and L4 Streams should share LiteGate's auto certificates, wildcard certificates, ACLs, service discovery and metrics.

> "Port sharing" here means one TCP listener choosing a processing pipeline by SNI. It isn't `SO_REUSEPORT`, nor two processes binding `0.0.0.0:443` at once.

## 1. How it works

```text
Client TCP/443
      │
      ▼
TLS ClientHello (SNI read without consuming the original bytes)
      │
      ├─ db.example.com ──► L4 Stream
      │                         ├─ TLS passed through ─► TCP / Unix socket
      │                         └─ LiteGate terminates TLS ─► plaintext TCP / Unix socket
      │
      └─ other domains ─────► normal HTTPS / HTTP/2 Sites

UDP/443 ───────────────────► HTTP/3 (separate UDP listener, not part of TCP SNI routing)
```

`websecure` always starts with an empty SNI mux. Without L4 routes it takes a fast path and connections go straight to HTTPS; adding the first route doesn't rebuild the public listener. When an L4 route matches, LiteGate puts back the bytes read while inspecting the ClientHello, so the Stream or upstream still receives the complete data.

## 2. Quick start: LiteGate terminates TLS and forwards to a Unix socket

The global entrypoint keeps listening on 443 as usual:

```yaml
# config.yaml
entrypoints:
  websecure:
    address: ":443"
    tls: true
    default: http
    on_non_tls: reject
    on_no_sni: reject
```

Create a Stream that doesn't listen on its own port but attaches to `websecure`:

```yaml
# streams/database.yaml
name: database
listen: false
entrypoints: [websecure]
hostnames: [db.example.com]
protocol: tcp
upstream: unix:///run/litegate/database.sock
enabled: true

tls:
  enabled: true
  auto_cert: true
  min_version: "1.2"
```

`auto_cert: true` requires global `auto_cert.enabled` with an ACME validation method configured, or a usable certificate already in the shared pool. The Stream-level switch means "make sure this domain has a certificate"; it doesn't create a separate ACME account or DNS provider.

This one configuration says:

- TCP/443 connections for `db.example.com` go to the `database` Stream;
- LiteGate completes the TLS handshake;
- the decrypted byte stream is sent to `/run/litegate/database.sock`;
- other domains continue to normal HTTPS Sites;
- `hostnames` doubles as the `auto_cert` certificate domains, so `tls.domains` isn't needed.

`listen: false` is what makes port sharing work: the Stream no longer binds its own `port`, and `websecure` accepts the connections.

LiteGate doesn't allow one Stream to both listen on its own port and attach to an entrypoint. If a migration needs the old port and shared 443 at the same time, create two Streams with different names pointing at the same `upstream` or `service_name`. Don't combine `listen: true`, `port`, `entrypoints` and `hostnames` in one configuration; separate definitions keep TLS policy, session limits and metrics unambiguous.

## 3. Two TLS modes

### 3.1 TLS passthrough: the certificate stays on the backend

When the backend performs the TLS handshake itself, don't enable TLS termination on the Stream:

```yaml
name: private-tls-service
listen: false
entrypoints: [websecure]
hostnames: [tcp.example.com]
protocol: tcp
upstream: unix:///run/private-service/tls.sock
enabled: true
```

The SNI mux only reads the ClientHello to classify the connection, then forwards the complete ClientHello and subsequent ciphertext untouched. The backend must:

- hold the certificate for `tcp.example.com` itself;
- start the TLS handshake from the first byte of the connection;
- not expect LiteGate to have decrypted anything.

A simple single-upstream passthrough needs no `tls` section. Only when a standalone Stream also uses its own `tls_routes` for a second level of SNI routing do you need:

```text
tls:
  enabled: true
  passthrough: true
```

### 3.2 TLS termination: LiteGate manages certificates

With `tls.enabled: true` and no `passthrough`, LiteGate completes the TLS handshake and the upstream receives a plaintext byte stream:

```text
tls:
  enabled: true
  auto_cert: true
```

This suits backends that only understand plaintext TCP, or when certificates should be managed centrally by LiteGate. It isn't an HTTP reverse proxy: LiteGate doesn't parse methods, URLs or headers; it just copies bytes in both directions after terminating TLS.

## 4. Sharing certificates between HTTPS and L4 Streams

HTTPS Sites and TLS-terminating L4 Streams use the same certificate pool. `auto_cert: true` doesn't mean "always request a new certificate"; LiteGate checks the shared pool first:

1. If the Stream's own exact-domain certificate exists, the renewal window and issuing CA are checked as usual;
2. Otherwise it looks for a valid wildcard or multi-SAN certificate, shared by other domains, that covers this domain;
3. It checks the certificate's SANs, validity period, and that the remaining lifetime exceeds the renewal window;
4. Only when no qualifying shared certificate exists is a new exact-domain certificate requested.

For example, with a valid `*.example.com` loaded globally:

```yaml
hostnames: [db.example.com]
tls:
  enabled: true
  auto_cert: true
```

LiteGate reuses `*.example.com` directly and doesn't request `db.example.com`. Certificates restored from shared KV are also refreshed into the pool before the Stream certificate scan.

A standard wildcard certificate covers one label only:

- `*.example.com` covers `db.example.com`;
- it doesn't cover `primary.db.example.com`;
- it usually doesn't cover the bare domain `example.com`.

To request a wildcard certificate, still declare it explicitly in the global Auto-Cert DNS provider and use DNS-01. A Stream's `hostnames` drive connection routing; LiteGate doesn't derive and request `*.example.com` from `db.example.com`.

## 5. Why declare domains on the Stream

Recommended configuration:

```yaml
name: database
listen: false
entrypoints: [websecure]
hostnames: [db.example.com]
protocol: tcp
upstream: unix:///run/litegate/database.sock
```

LiteGate generates the equivalent `handle.stream` SNI route at runtime. Domain, TLS and L4 governance then all belong to one Stream, and `db.example.com` isn't repeated in both `config.yaml` and `streams/*.yaml`.

Configure entrypoint routes by hand only when you need raw TCP passthrough that bypasses the Stream pipeline:

```yaml
entrypoints:
  websecure:
    address: ":443"
    tls: true
    routes:
      - name: direct-tls-service
        match:
          sni: tcp.example.com
        handle:
          proxy: unix:///run/private-service/tls.sock
```

`handle.proxy` is always TLS passthrough: LiteGate never terminates TLS there, and named Stream ACLs, load balancing and session metrics don't apply. When an explicit entrypoint rule and a generated rule use the same exact or wildcard pattern, the explicit rule wins; `sni_regex` always ranks after all exact and wildcard names, so an explicit regex never overrides generated exact or wildcard rules.

When an explicit `handle.stream` references a missing or disabled Stream, or a `handle.proxy` target can't be resolved, LiteGate logs a configuration error and rejects connections matching that rule rather than letting them fall back to HTTPS sites.

## 6. Unix socket ownership and lifecycle

For:

```yaml
upstream: unix:///run/litegate/database.sock
```

LiteGate is the client (dialer), not the socket listener. It doesn't create directories or `.sock` files for the upstream, change permissions or clean up leftovers.

Every new connection dials the path again:

- the backend may start after LiteGate, but connections arriving before the socket is ready fail;
- after the backend recreates the socket at the same path, LiteGate needs no reload;
- after changing `upstream`, new connections use the new path and existing ones keep their connection;
- between the backend's `unlink` and its new `bind`, new connections may get `no such file or directory`;
- when the file exists but nothing listens, the result is usually `connection refused`;
- if permissions change when the socket is recreated, you may see `permission denied`;
- a connection whose dial fails doesn't wait for the backend to recover; later new connections retry.

This is L4 byte forwarding: dial failures don't return `502` like an HTTP reverse proxy; clients usually just see the connection closed or reset.

On Linux use a shared group and least privilege:

```bash
install -d -o database -g litegate -m 0750 /run/litegate
# after the backend creates the socket:
chown database:litegate /run/litegate/database.sock
chmod 0660 /run/litegate/database.sock
```

The LiteGate user needs execute/traverse permission on the parent directory and the permissions required to connect to the socket file. In containers, both sides must mount the same Unix socket volume; Unix sockets can't cross hosts or container namespaces that don't share a filesystem.

The path must be a static absolute path of at most 107 bytes. The `{host}` template used by HTTP Unix upstreams isn't supported, nor are UDP Streams.

## 7. Real client addresses and PROXY protocol

A Unix socket backend can't learn the public client IP from the operating system's peer address. If the backend supports PROXY protocol, enable it on the Stream:

```yaml
proxy_protocol: true
proxy_protocol_version: 2
```

LiteGate writes the PROXY protocol header first, then sends TLS ciphertext or decrypted application bytes. The backend must explicitly enable parsing of that version; otherwise it treats the header as application data and fails with a protocol error.

Don't also configure `handle.proxy_protocol` on the generated entrypoint route. When a connection is handed to a named Stream, the Stream sends PROXY protocol.

## 8. Hot reload behavior

| Change | Restart needed? | Effect on existing connections |
| :--- | :--- | :--- |
| Adding the first attached Stream route from zero | No | Accepted connections keep their path; new connections use the new route |
| Changing `hostnames` | No | New connections use the new routing table |
| Changing a TCP or Unix socket `upstream` | No | Existing sessions keep the old upstream; new sessions use the new address |
| Adding or removing attached Streams | No | Public 443 isn't rebound |
| Changing `inspect.timeout`, `max_pending`, `per_ip_pending` | No | New inspections use the new budget |
| Changing `inspect.dispatch_queue` | Yes | The internal channel capacity can't be resized in place |
| Changing the `websecure` listener address or underlying listener properties in place | Usually | The listening pipeline must be rebuilt |

Routing table updates are atomic, but established long connections aren't migrated — expected behavior for a layer-4 proxy.

Once `websecure` has at least one explicit or generated SNI route, ClientHello inspection applies to every new connection on that entrypoint, including those that end up at ordinary HTTPS Sites. LiteGate logs an Info line when switching from no routes to this mode, listing the current inspection budget. Defaults: `inspect.timeout` `5s`, `max_pending` `2048`, `per_ip_pending` `16`. `per_ip_pending` limits ClientHello inspections in progress per source IP, not established connections; but CDN origins, NAT or corporate egress may share one source IP during handshake bursts, so raise it to the real peak and watch the rejection metrics.

If an attached Stream's `hostnames` overlap an HTTPS Site domain on the same entrypoint, the L4 Stream takes the connection before TLS termination. LiteGate logs the conflict at startup and on hot reload but doesn't guess which side to keep; remove such overlaps before going live.

## 9. Protocol limitations

### The client's first packet must be a TLS ClientHello

Routing by domain depends on the ClientHello SNI, so the target protocol must speak TLS from the connection's first byte and the client must send SNI.

These protocols can't share 443 this way directly:

- plaintext SSH, Redis or other non-TLS protocols;
- protocols that negotiate at the application level first and upgrade to TLS later;
- native MySQL TLS: the server sends a handshake packet first and the client requests TLS afterwards;
- PostgreSQL SSLRequest: the client sends a PostgreSQL protocol request first and TLS starts after the server confirms.

Ticking "enable SSL" in a MySQL/PostgreSQL client doesn't turn it into a raw TLS tunnel. Options:

- **PostgreSQL 17+**: with `sslnegotiation=direct` on the client, the first packet is a ClientHello with ALPN `postgresql`, so [`match.alpn`](../03-configuration/entrypoints.md#alpn-matching) can share 443 directly with no extra client;
- **Other databases or older PostgreSQL**: use [Forward](forward-and-connect.md) — the client listens on a local database port and connects to the server Stream through a 443 TLS tunnel; see [secure database access](../../database-proxy-solution.md);
- or use a TLS wrapper that speaks TLS from the first byte, such as stunnel, or a dedicated port.

### SNI, ECH and clients without SNI

- Clients connecting by IP or not sending SNI can't select a Stream by domain;
- `on_no_sni: reject` rejects such connections;
- when ECH hides the inner ClientHello, the gateway sees only the visible outer name and can't route by the hidden domain;
- `hostnames` supports exact domains and `*.example.com`, not a global `*`.

### HTTP/3

This feature shares TCP/443. HTTP/3 uses UDP/443 with a separate listener; it doesn't go through TCP SNI Stream routing and can't be forwarded to Unix stream sockets.

## 10. Relation to Nginx stream

LiteGate's capabilities roughly correspond to Nginx's `stream`, `ssl_preread` and Unix socket upstreams:

| Capability | Nginx | LiteGate |
| :--- | :--- | :--- |
| Read SNI without terminating TLS | `ssl_preread` | `websecure` SNI mux |
| HTTPS and other TLS TCP on one external 443 | The outer stream splits traffic to different listeners | Unmatched connections go straight into the built-in HTTPS pipeline |
| TLS passthrough | Supported | Supported |
| Stream TLS termination | Supported | Supported |
| Unix socket upstreams | Supported | Supported |
| Ownership of domains and L4 configuration | Usually a combination of `map`, `upstream`, `server` | The Stream declares `entrypoints + hostnames` itself |
| Certificate reuse between HTTPS and L4 | Depends on how certificates are configured | One certificate pool, Auto-Cert and wildcard coverage checks |
| Adding the first route online | Usually via a configuration reload | Atomic hot update without rebinding 443 |

This is a capability comparison; it doesn't mean configuration syntax is compatible, nor that load balancing, health checks or retry semantics are identical.

- [Nginx `ssl_preread` documentation](https://nginx.org/en/docs/stream/ngx_stream_ssl_preread_module.html)
- [Nginx stream proxy documentation](https://nginx.org/en/docs/stream/ngx_stream_proxy_module.html)

## 11. Troubleshooting

| Symptom | Common cause | Where to look |
| :--- | :--- | :--- |
| Disconnects right after the TLS handshake | The Unix socket doesn't exist or nothing listens | Stream logs, `litegate_stream_dial_failures_total`, socket path |
| Backend receives `0x16 0x03...` | This is TLS passthrough but the backend expects plaintext | Enable Stream TLS termination, or let the backend handle TLS |
| Backend errors after receiving `PROXY TCP4...` | PROXY protocol is enabled but the backend doesn't parse it | Enable the same version on the backend or turn it off |
| `permission denied` | Wrong group or permissions on the socket/parent directory | `namei -l`, `stat`, process user and group |
| `no such file or directory` | Backend not started, recreation window, or container volume not shared | Backend readiness, mount paths |
| The domain still reaches an HTTPS Site | No SNI sent, hostname mismatch or Stream disabled | Client SNI, Stream status, generated route logs |
| A separate certificate was requested for a subdomain | The existing wildcard is invalid, not loaded or covers a different level | SANs, validity, certificate pool and wildcard level |
| MySQL/PostgreSQL clients can't handshake | They use in-protocol TLS upgrade, not raw TLS from the first packet | Add a TLS wrapper or use a dedicated port |

## 12. Related docs

- [L4 SNI routing on port 443 combined with L7](sni-routing-recipes.md)
- [Entrypoints](../03-configuration/entrypoints.md)
- [Stream configuration reference](../03-configuration/stream-config.md)
- [Auto-Cert](../06-certificates/auto-cert.md)
- [On-Demand TLS](../06-certificates/on-demand-cert.md)
- [Metrics](../08-observability/metrics.md)
