# Stream Configuration Reference (Layer 4 Proxy)

LiteGate supports Layer 4 (TCP/UDP) dynamic port forwarding, suitable for non-HTTP workloads such as database proxies, DNS forwarding relays, and gaming servers.

[L4 site syntax and use cases](l4-guide.md)


---

## 1. Directory Structure

Stream configuration files are defined in YAML format and stored inside the `./streams/` directory (customizable via the `streams_dir` parameter in `config.yaml`).

---

## 2. Configuration Examples

### Static Upstream Configuration
```yaml
# streams/mysql-proxy.yaml
name: mysql-proxy
port: 3307                     # Local inbound port listener
protocol: tcp                  # Steering transport protocols: tcp or udp
upstream: "192.168.1.100:3306" # Outbound physical server address
enabled: true
idle_timeout: 300              # Idle session disconnection limit (seconds)
```

### Service-Discovery Upstream Configuration
```yaml
# streams/dns-forward.yaml
name: dns-forward
port: 5353
protocol: udp
upstream_type: litemesh         # Dynamic discovery source: litemesh / consul
service_name: coredns           # Discovery identifier
service_tag: "production"       # Optional: steering tag filter
lb_policy: round_robin          # Load balancer choices: round_robin, ip_hash
enabled: true
```

---

## 3. Parameter Reference

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `site` | string | ⬜ | Unified address: `tcp://:PORT`, `udp://:PORT`, or `tcp://HOSTNAME`. |
| `proxy` | string | ⬜ | Alias for `upstream`; cannot be combined with it. |
| `name` | string | ⬜ | Stream name, displayed in execution logs and the Dashboard. |
| `port` | int | Conditional | Local inbound port listener; omit it when `listen: false`. |
| `listen` | bool | ⬜ | Whether to bind `port` (default `true`). Set to `false` when the Stream is used only by an Entrypoint `handle.stream`. |
| `entrypoints` | list | ⬜ | Shared entrypoints to attach to; currently `[websecure]`. Generates SNI Stream routes automatically. |
| `hostnames` | list | Conditional | SNI names for shared entrypoints and the default domains for `tls.auto_cert`. |
| `protocol` | string | ✅ | Steering protocol: `tcp` or `udp`. |
| `upstream` | string | ⬜ | Static target: `host:port`, `tcp://host:port`, or `unix:///absolute/path.sock` for TCP Streams. Mutually exclusive with `service_name`. |
| `upstream_type` | string | ⬜ | Discovery provider: `litemesh` or `consul`. |
| `service_name` | string | ⬜ | Target microservice identifier resolved via discovery. |
| `service_tag` | string | ⬜ | Optional service steering tag metadata filter. |
| `lb_policy` | string | ⬜ | Active load balancing policy: `round_robin` (default) or `ip_hash`. |
| `enabled` | bool | ⬜ | Enables the Stream stream. Defaults to `true`. |
| `idle_timeout` | int | ⬜ | Session idle connection timeout in seconds. Defaults to 60 seconds. |
| `max_sessions` | int | ⬜ | Maximum concurrent sessions (defaults to `10000` for UDP). |
| `proxy_protocol` | bool | ⬜ | Injects a Proxy Protocol header prior to forwarding queries upstream. |
| `proxy_protocol_version` | int | ⬜ | Proxy Protocol version (choices: `1` or `2`). |
| `proxy_protocol_udp_each_packet` | bool | ⬜ | UDP/QUIC only. When `false` (default) the PROXY header is prepended to the **first** datagram of a session; when `true` it is prepended to **every** datagram. See note below. |
| `ip_restriction` | object | ⬜ | Stream-level IP Access Control List (ACL). |

A Stream must use exactly one ingress mode: either own a port listener or attach
to a shared Entrypoint. When `entrypoints` is configured, set `listen: false`
and omit `port`; `listen: true`, `port`, and `entrypoints` cannot be combined in
one Stream. To expose the same upstream through both a dedicated port and shared
443, define two differently named Streams that reference the same `upstream` or
`service_name`. Their session limits, TLS, ACLs, metrics, and lifecycles then
remain independent.

> **UDP / QUIC note.** For UDP upstreams (including QUIC) the PROXY protocol header is **prepended to the datagram payload**, never sent as a standalone datagram — a QUIC backend would otherwise treat a lone header packet as a corrupt frame. By default only the first datagram of each session carries the header (PROXY v2 with the `DGRAM` transport byte set). Backends that inspect every datagram independently should enable `proxy_protocol_udp_each_packet: true`. The backend must understand the PROXY protocol and strip the header before parsing QUIC. Also note that UDP sessions are keyed by the combination of the client's source IP:port and the local destination IP (which includes the interface index if non-zero), so QUIC connection migration (client address change) starts a new upstream session. Additionally, enabling PROXY protocol adds a 28-byte (IPv4) or 52-byte (IPv6) overhead to UDP/QUIC datagrams, which may trigger fragmentation or writing failures for packets near the MTU limit. Please ensure your network MTU has sufficient headroom.

---

## 4. IP Access Constraints

### Global Stream IP Filters
To apply restrictions globally across all L4 Stream ports, declare rules in `config.yaml`:
```yaml
stream_ip_restriction:
  allow_ips: ["192.168.0.0/16"]
  deny_ips: ["1.2.3.4"]
```

### Stream-Specific IP Overrides
Declare rules inside individual stream configs to override global settings:
```yaml
name: ssh-proxy
port: 2222
protocol: tcp
upstream: "10.0.0.5:22"
ip_restriction:
  allow_ips: ["10.0.0.0/8"]
```

---

## 5. Practical Use Cases

### MySQL / PostgreSQL Database Proxy
```yaml
name: db-proxy
port: 13306
protocol: tcp
upstream: "db-master:3306"
enabled: true
ip_restriction:
  allow_ips: ["10.0.0.0/8", "172.16.0.0/12"]
```

### DNS Forwarder Relay (UDP)
```yaml
name: dns-relay
port: 53
protocol: udp
upstream: "8.8.8.8:53"
max_sessions: 20000  # Enlarge limits to handle intensive high-frequency DNS workloads
enabled: true
```

### SSH Bastion Jump Host
```yaml
name: ssh-jump
port: 2222
protocol: tcp
upstream_type: litemesh
service_name: ssh-server
proxy_protocol: true
proxy_protocol_version: 2
```

---

## 6. TLS Termination

LiteGate supports TLS termination at the layer 4 stream entry. It decrypts client TLS traffic and proxies it to the backend target server as plain TCP. Currently, this option is only applicable when `protocol: tcp` is used.

To share TCP/443 with HTTPS, define a Stream that does not bind its own port:

```yaml
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
```

LiteGate generates the SNI route from `hostnames`. The SNI mux only classifies
the connection; the named Stream performs TLS termination and the remaining L4
pipeline. When `tls.domains` is omitted, `tls.auto_cert` reuses `hostnames`, so
the domain is declared only once.
Before requesting a certificate, LiteGate checks the certificate pool shared by
HTTPS and L4 Streams. If a currently valid exact or wildcard certificate already
covers the hostname (for example, `*.example.com` covers `db.example.com`), it is
reused and no duplicate certificate is requested.

### TLS Options

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `tls.enabled` | bool | ✅ | Enable TLS termination. |
| `tls.auto_cert` | bool | ⬜ | Automatically ensure a certificate is available. Uses explicit `domains`, or falls back to the Stream `hostnames`; no request is made when the shared pool already has a valid covering certificate. |
| `tls.domains` | list | ⬜ | Certificate domains; usually omitted for a shared-entrypoint Stream. |
| `tls.cert_file` | string | ⬜ | Path to your manual certificate file. Must be configured together with `key_file`. |
| `tls.key_file` | string | ⬜ | Path to your manual private key file. Must be configured together with `cert_file`. |
| `tls.min_version` | string | ⬜ | Supported minimum TLS version: `1.2` (default) or `1.3`. Invalid values fail configuration validation. |

### Static Configuration Examples

```yaml
# streams/db-tls.yaml — manual certificate
name: db-tls
port: 8443
protocol: tcp
upstream: "10.0.0.5:3306"
enabled: true
tls:
  enabled: true
  cert_file: /etc/litegate/certs/db.crt
  key_file: /etc/litegate/certs/db.key
  min_version: "1.2"
```

```yaml
# streams/db-tls-auto.yaml — ACME automatic certificate
name: db-tls-auto
port: 8443
protocol: tcp
upstream: "10.0.0.5:3306"
enabled: true
tls:
  enabled: true
  auto_cert: true
  domains:
    - db.example.com
```

> The examples use port `8443`: layer-4 streams cannot bind to the global HTTP/HTTPS ports (default `80`/`443`). To use `443` as the entry, change `https_port` in `config.yaml` first (see "HTTP/HTTPS Port Conflicts" below).

### Core Behavioral Details

1. **HTTP/HTTPS Port Conflicts (Port 443)**:
   Layer-4 Stream listeners are strictly prohibited from binding to ports reserved by global HTTP/HTTPS configurations (usually 80 and 443). If you want to use port 443 as a TLS Stream entry, you must disable the global HTTPS port or reconfigure `https_port` in `config.yaml` to an alternative port (e.g., `8443`).
2. **Manual Certificate Hot Reloading**:
   LiteGate keeps track of manual certificate files' modification times (`mtime`) on configuration loading. If the certificate files are updated without path changes, modifying or reloading the stream YAML configuration will prompt LiteGate to detect this mtime variance and perform a hot listener restart, renewing the certificate under the hood.
3. **Database TLS Tunnel Proxy Mode Caveats (e.g. MySQL)**:
   When proxying a database through a layer-4 TLS Stream (e.g., `tcp 443 -> LiteGate Decrypted -> Plain 3306`), the database client (e.g., MySQL CLI, DBeaver) **must treat LiteGate as a raw TLS tunnel**.
   This is semantically different from the native database "STARTTLS" mechanism (which negotiates SSL upgrades through application protocol layer commands after establishing plain TCP). When connecting to LiteGate, the client should configure connection settings to use a raw SSL tunnel (e.g., enabling SSL options), and LiteGate back-to-database communication remains plain TCP.

### Dynamic Service Discovery Tags (Auto-Generated L4 Streams)

When an upstream instance registers with Consul / Litemesh, it can declare L4 ports via **metadata or tags**, and the gateway will auto-generate the corresponding TCP/UDP stream (no YAML required). Generated streams are named `auto-<service>-<protocol>-<port>`.

**Port declaration tags**:

| Tag | Description |
| :--- | :--- |
| `litegate.tcp.port=8080` | The gateway listens for TCP on `8080` and forwards to the port the instance registered. |
| `litegate.udp.port=5353` | The gateway listens for UDP on `5353` and forwards to the port the instance registered. |
| `litegate.<group>.tcp.port=8080` | Named group, allowing a single instance to declare multiple independent ports (see below). |

- **Multiple ports**: a single instance may declare several distinct port tags, each generating its own stream.
- **Only an explicit tag opens a port**: registering with protocol `tcp`/`udp` alone never makes the gateway listen; write a port tag.
- **Port allow-list**: the port must be listed in the gateway's `service_discovery.tag_entrypoints.allowed_ports` and must not collide with a config.yaml entrypoint, a static stream or a reserved port (metrics, dashboard, ...).
- **Port conflicts**: when two services declare the same port, the stream already running keeps it and the newcomer is rejected; between two new ones the stream name decides. The rejected service shows a diagnostic on the dashboard's service tag page; other services are unaffected.
- **Failover**: when a TCP connection to an instance fails, another instance is tried (up to 3 attempts) and the failure feeds the same passive health checking as HTTP (instances failing repeatedly are ejected for a while).
- **Deduplication**: if the same port is declared redundantly via both metadata and tags, or pointed to by multiple named groups, only one stream is generated and the backend instance is not double-counted in load balancing.

**TLS tags** (layered on top of a port to enable ingress TLS termination; the named group must match the corresponding port tag):

| Tag | Description |
| :--- | :--- |
| `litegate.(<group>.)tcp.tls.enabled=true` | Enable TLS termination. |
| `litegate.(<group>.)tcp.tls.auto_cert=true` | Enable ACME automatic certificate requests. |
| `litegate.(<group>.)tcp.tls.domains=db.example.com` | Auto-cert domains, comma-separated for multiple. |
| `litegate.(<group>.)tcp.tls.cert_file=/etc/certs/db.crt` | Manual certificate file path. |
| `litegate.(<group>.)tcp.tls.key_file=/etc/certs/db.key` | Manual private key file path. |
| `litegate.(<group>.)tcp.tls.min_version=1.2` | Minimum protocol version, `1.2` or `1.3`. |

> **Purpose of the named group `<group>`**: when one instance exposes multiple L4 ports that each need a **different TLS configuration**, use distinct group names to separate them; TLS tags are matched to the corresponding port by group name.
>
> **Error handling**:
> - UDP streams do not support TLS termination. TLS tags declared on UDP are ignored with a warning log.
> - An invalid port value, invalid TLS tags (e.g. `auto_cert` without `domains`, `cert_file`/`key_file` not paired, certificate load failure, invalid `min_version`) or instances declaring conflicting TLS settings mean **the stream for that port is not created** (never downgraded to plaintext), with a diagnostic on the dashboard; the other services in the batch still apply.

---

## 7. Live Telemetry Scopes

Operational metrics (active sessions, packet traffic size) can be monitored in real-time in the Admin Dashboard.

| Telemetry Key | Description |
| :--- | :--- |
| Active Sessions | Real-time active TCP connections or UDP sessions. |
| Upload Bytes | Cumulative outbound data payload size. |
| Download Bytes | Cumulative inbound data payload size. |
| Dropped Sessions | Queries dropped due to exceeding `max_sessions` thresholds (UDP only). |
| Timeout Closes | Connections closed by the gateway due to idle timeouts. |
