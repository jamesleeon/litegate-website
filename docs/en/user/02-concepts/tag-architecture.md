<!-- GENERATED FILE — DO NOT EDIT.
     Source: internal/configdocs/docs/en/tag-architecture.md (package internal/configdocs)
     Regenerate: go generate ./internal/configdocs/...
     Edit the source instead; a drift test fails if this copy is edited directly. -->

# LiteGate Service Tag Architecture

Why service tags are designed the way they are, how the gateway turns them into routes, and how they divide work with site YAML. See the Service Tags Guide for how to write them and the Service Tag Reference for every tag.

## 1. Why tags

Site YAML is maintained by the gateway operator; service tags travel with the service when it registers. Routes appear and disappear with registrations as services deploy, scale and retire, with no gateway change. Tags suit what the service itself decides, such as "which domain and path expose me". Gateway-level concerns such as certificates, listening ports and global security policy stay in config.yaml and site YAML.

## 2. Principles

1. **Two forms, never mixed.** The shortcut (4 keys) covers the common "one domain to this service"; named resources cover everything else.
2. **Whatever can be derived is not written.** Entrypoints default to `web` + `websecure`, the Service defaults to the registering service, no Host matches any Host.
3. **A mistake is rejected, never silently ignored.** Unknown properties, invalid references and conflicts reject the whole instance (fail closed) with a "did you mean" suggestion, avoiding the Traefik-style "a misspelled label, odd behaviour, hours of debugging".
4. **One source of truth.** The runtime, the dashboard's tag classification and MCP `explain_tag` / `preview_service_tags` call the same parser, and the tag reference is generated from its property lists. They cannot disagree.

## 3. Resource model

```text
EntryPoint                    listener address and protocol (config.yaml, or a restricted tag definition)
  ├── HTTP Router             matches Host / path / method / header / query, references the resources below
  │     ├── Middlewares       request and response processing (rate limit, CORS, strip prefix, ...)
  │     ├── IDS               identity and tenant decisions, returns an instance selector
  │     └── HTTP Service      the registering service: instance selection, load balancing, timeout, retry, circuit breaker, health checks
  │           └── ServersTransport   TLS / mTLS to the upstream
  └── L4 Stream               TCP / UDP proxy: port binding, optional TLS termination, direct stream forwarding
```

- **The Router decides which requests; the Service decides how they are forwarded.** Host belongs to the Router; timeout and retry belong to the Service.
- **The Service is always the registering service.** Tags cannot send traffic to another service; `discovery.name` can only equal the registering service's name.
- **IDS can only narrow.** The selector IDS returns filters the Service's instances further; a conflict with the Service's hard selector rejects the request.
- **L4 Stream** handles non-HTTP Layer-4 TCP/UDP traffic: declares listening ports and optional TLS settings via tags, forwarding directly to registered service instances without passing through Layer-7 HTTP routers or middlewares.

## 4. From tags to routes

```text
instance tags / metadata
  → instance tags (litegate.instance.*, plain metadata) are set aside; they never define routes
  → shortcut: compiled to a Router named main
    named resources: parsed and validated by ParseTagResources
  → CompileTagResources: one route per Router × entrypoint (e.g. orders@web, orders@websecure)
  → L4 stream tags (litegate[.<group>].tcp/udp.*): compiled to dynamic StreamConfig
  → entrypoint policy: config.yaml entrypoints by name; new ports only within allowed_ports
  → merged into catalog sites by domain, and with a site YAML of the same domain
```

Every instance of a service must carry the same routing and resource tags. When instances disagree, the dashboard highlights the drifting keys and the gateway keeps one declaration until the instance tags converge.

## 5. Routing tags and instance tags

| | Routing and resource tags | Instance tags |
| :--- | :--- | :--- |
| Keys | The 4 shortcut keys, `litegate.entrypoints.*`, `litegate.http.*`, `litegate[.<group>].tcp/udp.*` | `litegate.instance.*`, plain metadata such as `sid=c1` |
| Describe | How the service is exposed (Layer 7 route or Layer 4 stream) | Who this instance is |
| Across instances | Must be identical | May differ |
| Used by | Route and stream compilation | Selector / IDS matching per request |

A Service's `discovery.selector.match.<key>` pairs with an instance's `<key>=<value>` (or `litegate.instance.labels.<key>`); `selector.meta.<key>` pairs with `litegate.instance.meta.<key>`.

## 6. Request path

```text
request → entrypoint (web / websecure / ...)
        → site by Host
        → route within the site: higher priority first, then the more specific path; a route only accepts requests from its own entrypoints
        → Middlewares → IDS
        → Service: hard selector gives the base set; the meta preference's matches if any, otherwise the base set
        → load balancer picks an instance → forward (timeout / retry / circuit breaker)
```

## 7. Layer 4 (L4) stream proxy

For non-HTTP protocols such as databases (MySQL, PostgreSQL), caches (Redis), and IoT devices, services do not declare Layer-7 HTTP routers or middlewares; they use Layer-4 Stream tags directly.

### 7.1 Tag syntax and groups

```properties
# Minimal single-port syntax
litegate.tcp.port=3306

# Multi-port and TLS termination
litegate.mysql.tcp.port=3306
litegate.mysql.tcp.tls.enabled=true
litegate.mysql.tcp.tls.domains=db.example.com
litegate.dns.udp.port=5353
```

- **Protocol and port**: `litegate[.<group>].tcp.port` and `litegate[.<group>].udp.port` listen on the specified port and forward raw connections to registered service instances.
- **Multi-port grouping**: When a service exposes multiple Layer-4 ports (e.g., separating business traffic from admin/probe ports), distinguish them using the optional `<group>` prefix (such as `mysql` or `dns`).
- **TLS termination**: Supports `litegate[.<group>].tcp.tls.enabled=true` with optional `auto_cert`, `domains`, `cert_file`, `key_file`, and `min_version`. UDP does not support TLS termination.

### 7.2 Compilation and lifecycle

```text
L4 connection → listener (dedicated port or shared 443 SNI)
              → StreamConfig by protocol and port
              → optional TLS termination (auto_cert / cert_file)
              → stream connection pool → forward to service endpoint
```

- **Compiled into StreamConfig**: The parser aggregates all instances of the service by `protocol + port`, producing a dynamic stream configuration named `auto-<service>-<protocol>-<port>`.
- **Discovery isolation**: Instance endpoints register into a discovery cache tagged as `stream:<protocol>:<port>`, isolated from HTTP site connection pools.
- **Fail-closed conflicts**: When instances on the same port declare conflicting TLS configurations, the gateway logs an error and skips the stream (fail closed) to avoid accidental plaintext exposure or security downgrade.
- **Port sharing**: In addition to dedicated listening ports, on global entrypoints configured with SNI Mux (such as `websecure` on port 443), traffic can be routed to the stream based on the SNI in the TLS ClientHello, sharing the public listener with Layer-7 HTTPS.

## 8. Tags and site YAML

| Capability | Service tags | Site YAML |
| :--- | :--- | :--- |
| Forward to the registering service | Yes | Yes |
| Forward to another service, static files, redirects, templates and other actions | No | Yes |
| Host / path / method / header / query matching | Yes | Yes |
| Middlewares | Yes, defined in the tags | Yes |
| Timeout, retry, circuit breaker, health checks, load balancing | Yes (Service properties) | Yes |
| Site certificate, IP restriction, force HTTPS and other site settings | No | Yes |
| New listening port | Only within allowed_ports | Defined in config.yaml |
| Layer 4 TCP/UDP stream proxy | Yes (tcp.port / udp.port) | Yes (streams/*.yaml) |

When a domain has both a site YAML and tag routes, they merge into one site:

- Routes are sorted together: higher priority first, then the more specific path, so a YAML `/` never shadows a tag `/api`.
- Site-level settings (certificate, IP restriction, title, ...) come from the YAML.
- On a middleware name clash with a different configuration the YAML wins; the tag definition is ignored and an error is logged.

## 9. Troubleshooting

| Symptom | Cause |
| :--- | :--- |
| The instance shows diagnostics in the dashboard and has no route | An unknown property, invalid reference or conflict rejected the whole instance; follow the "did you mean" |
| No route on 443 | `entrypoints=web` was written explicitly; omit it to attach to both `web` and `websecure` |
| A middleware comes and goes | Two services on one domain use the same middleware name with different configurations; names are shared per domain, prefix them with the service |
| Some requests reach another service | Two services declare the same match; the higher priority wins, and at equal priority one is chosen by service name |
| Only `/<service>` matches although no path was written | With no Host, path or rule the path prefix defaults to `/<service>`; write `match.path_prefix=/` to take the root |
| The new port is not listening | The port is not listed in `service_discovery.tag_entrypoints.allowed_ports` |
| Layer-4 port not listening or rejected | TLS configuration conflict across instances, auto_cert missing domains, or port already in use |
