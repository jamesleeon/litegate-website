# Entrypoints

An entrypoint is a process-wide shared network listener. Sites reference listeners by name, keeping socket binding separate from HTTP Host routing.

```yaml
# config.yaml
entrypoints:
  web:
    address: ":80"
  websecure:
    address: ":443"
    tls: true
  internal:
    address: ":8080"
    interface_name: "enp10s0"
```

## Sharing TCP 443 with SNI routes

`websecure` can inspect ClientHello SNI before LiteGate terminates TLS. Matching
connections are proxied as untouched TCP; unmatched connections continue to
the normal HTTPS/HTTP2 server. HTTP/3 remains on the separate UDP listener.

```yaml
entrypoints:
  websecure:
    address: ":443"
    tls: true
    default: http
    on_non_tls: reject
    on_no_sni: reject
    inspect:
      timeout: 5s
      max_pending: 2048
      per_ip_pending: 16
    routes:
      - name: a-service
        match:
          sni:
            - a.example.com
            - "*.proxy.example.com"
          sni_regex:
            - 'svc-[0-9]+\.example\.com'
        handle:
          proxy: tcp://127.0.0.1:444
          proxy_protocol: 2

      - name: local-tls-service
        match:
          sni: tcp.example.com
        handle:
          proxy: unix:///run/local-tls-service.sock

```

`match.sni` accepts a string or list. `match.sni_regex` accepts Go/RE2 regular
expressions, matched against the complete normalized hostname without case
sensitivity. Precedence is exact name → longest wildcard suffix → regex;
regular expressions retain declaration order. They are compiled during config
validation and are limited to 32 expressions per route, 256 per entrypoint,
and 512 bytes each. The same precedence applies to generated attached-Stream
routes: an explicit exact or wildcard pattern can override the identical
generated pattern, while an explicit regex still ranks below generated exact
and wildcard matches. `handle.proxy` accepts `tcp://host:port`, a bare
`host:port`, or a local `unix:///absolute/path.sock`. Unix socket targets must
use a static absolute path; the HTTP Unix upstream `{host}` template is not
supported. The backend still receives the complete, encrypted TLS stream.
`handle.proxy_protocol` may be `1` or `2` to send the restored client and
listener addresses to the selected backend before the untouched TLS bytes.

### ALPN matching

`match.alpn` narrows a route to ClientHellos that offer at least one of the
listed ALPN protocol IDs (exact, case-sensitive). It can be combined with
`sni`/`sni_regex`, or used alone:

```yaml
entrypoints:
  websecure:
    routes:
      # PostgreSQL 17+ direct TLS (sslnegotiation=direct) on the same hostname
      # as the web UI: PG clients go to the database, browsers stay on HTTPS.
      - name: pg-direct
        match:
          sni: db.example.com
          alpn: postgresql
        handle:
          stream: pg
      # ALPN alone matches any SNI, including ClientHellos without SNI
      # (clients connecting by IP address).
      - name: pg-any
        match:
          alpn: postgresql
        handle:
          proxy: tcp://10.0.0.5:5432
```

Rules:

- Precedence stays exact → longest wildcard → regex; ALPN-only routes rank
  last. Within the same SNI pattern, a route whose ALPN is offered beats the
  plain route; a route whose ALPN is not offered is skipped and matching
  continues with the next class, finally falling back to HTTPS.
- Each (SNI, ALPN) pair has one owner. A plain route and ALPN routes may share
  an SNI; two routes may not claim the same SNI with the same protocol. An
  explicit ALPN route does not suppress the route generated from a Stream's
  `hostnames`, so the Stream remains the fallback for other protocols.
- At most 16 protocols per route, each 1–255 bytes.
- ECH hides the inner ClientHello, including ALPN; only the outer values are
  visible to the router.
Alternatively, `handle.stream` dispatches the connection to a named L4 Stream,
reusing its TLS termination or passthrough, ACL, discovery, load balancing,
PROXY protocol, and metrics. Configure PROXY protocol on the Stream in this mode.
Prefer declaring `entrypoints: [websecure]` and `hostnames` on the Stream itself.
LiteGate then generates the `handle.stream` route automatically, and uses the
same hostnames as the default automatic-certificate domains. Explicit
`handle.stream` routes remain supported for overrides and compatibility.
Routes, fallback policies, timeout, global pending capacity, and per-IP capacity
are hot-swappable. The empty SNI mux is installed at startup, so the first
attached Stream route is hot-addable. Changing `inspect.dispatch_queue` still
requires a restart.

## Receiving traffic from an external L4 proxy

When HAProxy or nginx stream owns public TCP/443, LiteGate can listen on a Unix
socket and accept the inbound PROXY protocol while retaining TLS termination,
certificate management, domain routing, and HTTP routing:

```yaml
entrypoints:
  websecure:
    address: unix:///run/litegate/websecure.sock
    tls: true
    unix:
      mode: "0660"
      group: nginx
    proxy_protocol:
      accept: true
      required: true
      trusted: local
      timeout: 2s
```

The processing order is PROXY protocol → SNI inspection → TLS → HTTP. PROXY v1
and v2 are supported; v2 is recommended. Unix sockets default to mode `0660`,
and missing parent directories to `0750`. `unix.mode` overrides the final mode;
`unix.group` selects a Unix group and is unsupported on Windows. Paths must be
absolute and at most 107 bytes. Filesystem permissions form the trust boundary.
LiteGate removes stale sockets but never replaces a regular file or active socket.

For nginx HTTP proxying, where the HTTP module cannot emit a PROXY header,
LiteGate recognizes the direct Unix connection and trusts nginx's
`X-Forwarded-For`, `X-Forwarded-Proto`, and `X-Forwarded-Host`. Restrict the
socket and parent directory and configure nginx to overwrite those headers.
Once a PROXY header is decoded, normal `trusted_proxies` rules apply to its TCP
source address. Direct Unix connections without a PROXY header do not consume a
`per_ip_pending` SNI-inspection bucket because the Unix peer has no usable IP;
they remain subject to `max_pending`.

Unix stream sockets cannot carry UDP, so HTTP/3 is disabled for this entrypoint.
For a TCP entrypoint, `proxy_protocol.trusted` must instead list the directly
connected proxy IPs or CIDRs.

```yaml
# sites/internal-api.yaml
domain: internal-api.example.com
entrypoints: [internal]
routes:
  - match:
      path_prefix: /
    action:
      type: proxy
      upstream: ["http://127.0.0.1:9000"]
```

On Linux, `interface_name` uses `SO_BINDTODEVICE`. It follows address changes because it binds the socket to the device rather than to its current IP address. LiteGate needs sufficient privilege to set this socket option. Configuring it on another operating system fails explicitly at startup.

`web` and `websecure` are the standard HTTP and HTTPS entrypoints. Additional custom entrypoints currently support plain HTTP; use `websecure` for TLS. Legacy `http.port`, `http.https_port`, and site-level `port` remain supported. A legacy site without `entrypoints` retains the old behavior and may match on every listener.

When a standard entrypoint uses a Unix socket, the legacy HTTP port fields remain
public/compatibility metadata but are not treated as TCP ports bound by LiteGate.
Conflict checks and listener inventory use `entrypoints.*.address`; a Unix
listener reports its socket path and port `0`.

A site cannot define both `port` and `entrypoints`, and references to undefined entrypoints fail configuration validation.
