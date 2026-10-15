<!-- GENERATED FILE — DO NOT EDIT.
     Source: internal/configdocs/docs/en/stream-config.md (package internal/configdocs)
     Regenerate: go generate ./internal/configdocs/...
     Edit the source instead; a drift test fails if this copy is edited directly. -->

# L4 Stream Guide

## Unified `site` syntax

New configurations can use `site` and `proxy`, as HTTP sites do. Keep L4 files in
`streams/`; HTTP files remain in `sites/`. This shorthand compiles into the same
Stream runtime configuration. Existing `name`, `port`, `protocol`, `upstream`,
`listen`, and `hostnames` configurations remain supported.

```yaml
# streams/mysql.yaml: dedicated TCP port
site: tcp://:3307
proxy: 192.168.1.100:3306
---
# streams/dns.yaml: dedicated UDP port
site: udp://:5353
proxy: 192.168.1.100:53
---
# Shared TCP 443, selected by TLS SNI
site: tcp://db.example.com
entrypoints: [websecure]
proxy: 192.168.1.100:3306
```

- `tcp://:PORT` and `udp://:PORT` open a dedicated port. The port must be 1–65535.
  They do not support a binding IP or path. Do not combine them with `listen: false`
  or shared entrypoints.
- `tcp://HOSTNAME` sets `hostnames`, `listen: false`, and defaults to `[websecure]`
  unless Connect publication is enabled. It does not perform DNS-based routing
  for plain TCP. A shared-443 client must send TLS with matching SNI; raw MySQL,
  SSH, and plain TCP need a dedicated port or authenticated Forward access.
  With no terminating `tls` configuration, the upstream handles TLS.
- UDP cannot route by a hostname. `udp://HOSTNAME` is rejected.
- `proxy` is a string alias for `upstream`; specifying both is rejected.
  For discovery, omit both and use `service_name` and `upstream_type`.
- `name` is optional: generated names are `tcp-3307`, `udp-5353`, and
  `tcp-db.example.com`. Set a stable explicit name when referencing a Stream
  through Forward or an Entrypoint `handle.stream`.
- `enabled` defaults to true. Single mappings, lists, and `---` documents use
  the same strict parser; unknown fields and conflicting shorthand are rejected.

### Authenticated Forward target

A private target has no listening `site` address. Give it an explicit name and
reference that name from the HTTP Forward site:

```yaml
# streams/private-mysql.yaml
name: private-mysql
protocol: tcp
listen: false
proxy: 192.168.1.100:3306
```

```yaml
# sites/forward.yaml
site: forward.example.com
forward:
  target: {type: stream, name: private-mysql}
  token_file: ./secrets/forward.token
```

### Connect publication

On the Private node, enable Connect client globally and publish a Stream without
opening a local public port:

```yaml
site: tcp://mysql.home.example.com
name: home-mysql
connect_publish: forward_only
proxy: 192.168.1.20:3306
```

`forward_only` requires authenticated Forward access on Cloud. Use `public` only
when deliberately exposing TLS SNI access on Cloud; it does not add authentication.
See [Connect](../09-advanced/connect.md) for tunnel configuration.

### SOCKS5 and validation

```yaml
name: private-socks5
protocol: socks5
listen: false
socks5:
  allowed_destinations: ["10.0.0.0/8:3306", "192.168.1.0/24:22"]
```

SOCKS5 selects destinations per connection and requires an allowlist; it does not
use a fixed `proxy`. Use `litegate -t` before applying configuration. MCP clients
should read `get_config_guide(topic=stream, lang=en)` (use `lang=zh` for Chinese) or `get_stream_config_schema`, validate with `validate_stream_config`,
then save with `save_stream_config`. Saving is not proof that reload succeeded;
inspect runtime streams and test connectivity after applying changes.


## TLS termination and field reference

Shared SNI routing forwards TLS bytes to the upstream by default. To terminate
TLS in LiteGate and send plain TCP to the backend, enable Stream TLS:

```yaml
site: tcp://db.example.com
proxy: 192.168.1.100:3306
tls:
  enabled: true
  auto_cert: true
```

Enable global `auto_cert` and configure certificate issuance first. Stream
`tls.domains` defaults to the site's hostname; an existing valid covering
certificate is reused. For a manual certificate, replace `auto_cert` with
`cert_file` and `key_file`. Do not expose the same hostname as both an HTTP site
and a shared Stream unless the Stream taking precedence is intentional.

| Field | Meaning |
| --- | --- |
| `site` | TCP/UDP port address or TCP TLS SNI hostname. |
| `proxy` / `upstream` | One static backend, including TCP Unix sockets. Choose one spelling. |
| `name` | Stable runtime identifier; generated from `site` if omitted. |
| `entrypoints` | Currently `[websecure]`; shared ingress does not own a listener. |
| `listen` | Defaults true for legacy configurations; hostname shorthand sets false. |
| `enabled` | Defaults true; explicit false disables the Stream. |
| `service_name`, `upstream_type`, `service_tag` | Discovery target, registry and optional tag filter. |
| `lb_policy`, `backends` | Load balancing policy and backend list. |
| `connect_publish` | `public`, `forward_only`, or false / `disabled`. |
| `tls` | TLS termination or `passthrough`; UDP does not support TLS termination. |
| `ip_restriction` | Stream IP allow/deny rules. |
| `idle_timeout` | Idle timeout in seconds; omitted or zero defaults to 60 seconds. |
| `max_sessions` | Concurrent session limit. |
| `proxy_protocol`, `proxy_protocol_version` | PROXY protocol headers; the backend must support them. |
| `socks5.allowed_destinations` | Mandatory destination allowlist for `protocol: socks5`. |

See [Stream field reference](stream-config.md) for advanced TLS routes, UDP,
PROXY protocol, service discovery and operational details.

### Load-balancing policies and scope

- `lb_policy` supports `round_robin` (default), `ip_hash`, `weighted` / `weighted_round_robin` (smooth weighted round robin), `least_conn`, `p2c`, and registered plugin policies. L4 does not support the HTTP `cookie` policy.
- When every entry in `backends` (including `tls_routes[].backends`) is a static `upstream`, `lb_policy` selects the backend. The default is round robin. Weighted round robin uses each backend's `weight`; omitted or non-positive weights count as 1. IP hash preserves the backend for a client IP while the candidate pool remains unchanged.
- Discovered `service_name` instances use `lb_policy`. Lists containing discovery targets retain two selection stages: backend weights randomly select a target service/backend, then `lb_policy` selects an instance within that service. IP hash in these lists provides affinity within a service, not across target services.
- `least_conn` compares active TCP connections or UDP virtual sessions and selects uniformly at random among ties. UDP selects a backend when a client-source/destination session is created and reuses it for subsequent datagrams. Idle expiry or closure releases the session count.
- `p2c` compares two candidates by active count, then EWMA latency. TCP measures successful connection establishment; UDP measures the first upstream datagram to the first backend response, once per session. One-way sessions without a response do not supply latency samples. These are not per-request application latency measurements.
- Static backend selection changes from weighted random to round robin by default. Set `lb_policy: weighted` explicitly for weighted traffic distribution.
