# Upstream DNS

By default, upstream domains use Go's default name resolution. For corporate networks, VPNs or split DNS, define a resolver in `config.yaml`:

```yaml
resolvers:
  corp:
    servers: [192.168.1.53:53, 192.168.1.54:53]
    timeout: 2s
```

Servers must be literal IP:port addresses; bracket IPv6. The per-server query timeout defaults to 2 seconds. Failed queries try the next server; NXDOMAIN and NODATA do not. Backup servers should provide the same DNS view. The upstream connection timeout and request deadline bound the entire operation.

Reference the resolver from a V2 proxy object:

```yaml
site: app.example.com
proxy:
  to: https://a.b.com
  resolver: corp
```

Or from a named Service:

```yaml
site: app.example.com
services:
  backend:
    to: https://a.b.com
    resolver: corp
    timeout: 5s
    health: {path: /health, interval: 10s}
/api:
  service: backend
```

Legacy/advanced proxy actions accept `resolver` alongside `upstream` or `service_name`. Routes referencing a Service cannot override its resolver. Unknown resolver references, including unused Service definitions, fail validation.

HTTP, HTTPS, gRPC, fast HTTP/1, WebSocket/protocol upgrades, FastCGI TCP connections and related active probes use the selected resolver. IP addresses connect directly, and Unix sockets require no DNS. URL, Host and TLS SNI/hostname verification retain their existing semantics.

Explicit resolvers bypass system DNS, hosts and environment HTTP proxies; upstreams without a resolver retain existing behavior. Different DNS configurations have separate transport pools and active health states. UDP queries retry over TCP when truncated; A, AAAA and CNAME records are supported.

New connections re-query DNS without an additional DNS cache. Existing connections can remain open after DNS changes. Successfully recompiled sites use pools keyed by the new resolver settings; in-flight requests retain their old configuration. DNS addresses are connection candidates, not separate gateway load-balancing instances.

Filesystem sites recompile on successful global configuration reloads; removing a referenced resolver rejects the reload and preserves the old configuration. In Consul/LiteMesh `config_watch` mode, changing or removing `resolvers` requires a restart and is explicitly rejected during hot reload, avoiding stale resolver bindings.

DoH, DoT, SRV discovery and ECH are outside this feature.
