<!-- GENERATED FILE — DO NOT EDIT.
     Source: internal/configdocs/docs/en/tag-dsl.md (package internal/configdocs)
     Regenerate: go generate ./internal/configdocs/...
     Edit the source instead; a drift test fails if this copy is edited directly. -->

# LiteGate Service Tags Guide

When a service registers with `litegate.*` tags (Litemesh / Consul metadata, Docker labels, Kubernetes annotations), the gateway builds its routes automatically, with no site YAML. This guide shows how to write them by scenario. Every tag is described in the Service Tag Reference; the design is explained in Service Tag Architecture.

## 1. Pick a form

| Need | Form |
| :--- | :--- |
| One domain (or one path) forwarded to this service, no policy | Shortcut: at most 4 tags |
| Several routes, middlewares, IDS, timeout / retry / circuit breaker, a dedicated port | Named resources: `litegate.http.routers.*` and friends |

The two forms cannot be mixed. As soon as you need any policy, rewrite the whole set as named resources.

## 2. Shortcut

```properties
litegate.http.host=api.example.com
litegate.http.path_prefix=/api
litegate.http.strip_path=true
```

| Tag | Meaning |
| :--- | :--- |
| `litegate.http.host` | Domain(s), comma separated. Unset: the catalog `default_domain`, `<service>.<default_domain>` |
| `litegate.http.path` | Exact path |
| `litegate.http.path_prefix` | Path prefix; `/` when neither `path` nor `path_prefix` is set |
| `litegate.http.strip_path` | `true` strips the matched path before forwarding; requires `path` or `path_prefix` |

The shortcut is an ordinary Router named `main`: attached to `web` (80) and `websecure` (443), forwarding to the registering service with the default policy.

## 3. Named resources: the minimum

```properties
litegate.http.routers.orders.match.hosts=orders.example.com
litegate.http.routers.orders.match.path_prefix=/api
```

These two lines are equivalent to the shortcut, except that the Router is named `orders`. Everything left out has a default:

- No `entrypoints`: attached to `web` and `websecure`.
- No `service`: the registering service with the default policy when no Service is declared; the Service when exactly one is declared.
- No Host condition: any Host on the entrypoints.

Resource names use lowercase letters, digits, `-` and `_`; property paths are lowercase.

## 4. Add policy to the service

Policy lives on the Service. With a single declared Service the Router does not need `service`:

```properties
litegate.http.routers.orders.match.hosts=orders.example.com
litegate.http.services.orders.timeout=30s
litegate.http.services.orders.retry.attempts=2
litegate.http.services.orders.healthcheck.path=/healthz
litegate.http.services.orders.healthcheck.interval=10s
litegate.http.services.orders.circuitbreaker.enabled=true
litegate.http.services.orders.loadbalancer.strategy=least_conn
```

- `timeout` bounds one request end to end (`30s`, `500ms`); for an upgrade request such as WebSocket it bounds only the handshake.
- A Service always describes the service that registers the tags. `discovery.name` is optional and, when set, must equal that service name.

## 5. Several routes

A service may have several Routers, each with its own match and middlewares:

```properties
litegate.http.routers.shop.match.hosts=shop.example.com
litegate.http.routers.admin.match.hosts=shop.example.com
litegate.http.routers.admin.match.path_prefix=/admin
litegate.http.routers.admin.priority=100
litegate.http.routers.admin.middlewares=shop-admin-limit
litegate.http.middlewares.shop-admin-limit.ratelimit.qps=20
```

Higher `priority` matches first; at equal priority the more specific path matches first.

With several declared Services every Router must name its `service`, and the name must be declared: a typo is reported with the closest name instead of silently falling back to the defaults.

## 6. Router matching

Use either `rule` or structured `match.*`:

```properties
# Structured
litegate.http.routers.orders.match.hosts=orders.example.com
litegate.http.routers.orders.match.path_prefix=/api
litegate.http.routers.orders.match.methods=GET,POST
litegate.http.routers.orders.match.headers.X-App=console
litegate.http.routers.orders.match.query.version=v2

# Rule
litegate.http.routers.orders.rule=Host(`orders.example.com`) && PathPrefix(`/api`)
```

`match.path` and `match.path_prefix` are exclusive. With no Host, no path and no `rule`, the path prefix defaults to `/<service>` so services do not fight over the root; write `match.path_prefix=/` to take the root explicitly.

## 7. Middlewares

Written `litegate.http.middlewares.<name>.<type>.<property>=<value>`; the properties are those of the same middleware type's `config` in site YAML:

```properties
litegate.http.middlewares.strip-api.strip_prefix.prefixes=/api
litegate.http.middlewares.limit.ratelimit.qps=150
litegate.http.middlewares.cors-api.cors.allowed_origins=https://app.example.com
litegate.http.routers.orders.middlewares=strip-api,limit,cors-api
```

- A middleware must be defined in the tags before a Router references it; middlewares run in the listed order.
- Middleware names are shared per domain: if two services on the same domain use one name with different configurations, that middleware is disabled. Prefix names with the service, e.g. `orders-limit`.

## 8. Instance selection and IDS

The Service selector decides which instances are used:

```properties
litegate.http.services.shared-app.discovery.selector.match.sid=c1
litegate.http.services.shared-app.discovery.selector.meta.version=v2
```

- `selector.match.<key>` is a hard boundary: only instances whose metadata `<key>` equals the value.
- `selector.meta.<key>` is a soft preference: matching instances when there are any, otherwise the complete hard-match set.

Instances declare their identity at registration. When the provider reports metadata, write `sid=c1`; otherwise `litegate.instance.labels.sid=c1` (hard match) / `litegate.instance.meta.version=v2` (soft preference). Instance tags may differ per instance; routing and resource tags must be identical on every instance.

IDS is a Router property. Several Routers can share one service with different operations:

```properties
litegate.http.routers.login.match.path=/login
litegate.http.routers.login.ids.provider=session
litegate.http.routers.login.ids.operation=login

litegate.http.routers.api.match.path_prefix=/api
litegate.http.routers.api.ids.provider=session
litegate.http.routers.api.ids.operation=resolve
```

The selector IDS returns can only narrow the service's instances; a value that conflicts with the Service's hard selector rejects the request. `ids.failpolicy` defaults to `deny`.

## 9. Entrypoints and dedicated ports

A Router may reference any config.yaml entrypoint by name:

```properties
litegate.http.routers.internal.entrypoints=admin
```

Tags may also open a new HTTP listener, but its port must be listed in the gateway's `service_discovery.tag_entrypoints.allowed_ports` and must not reuse a config.yaml entrypoint name or port:

```properties
litegate.entrypoints.api-8080.address=:8080
litegate.http.routers.api.entrypoints=api-8080
litegate.http.routers.api.match.path_prefix=/
```

config.yaml needs:

```yaml
service_discovery:
  tag_entrypoints:
    allowed_ports: [8080]
```

## 10. Validation

- A wrong tag is never silently ignored: unknown properties, invalid references and conflicts reject the whole instance, with a "did you mean" suggestion.
- The dashboard's service tag page lists every tag of every instance with its classification and diagnostics.
- When generating tags over MCP: consult `get_tag_reference` or `explain_tag` first; the final tag set must pass `preview_service_tags` with every error fixed and every warning reviewed before it is applied.

## 11. Removed forms

`litegate.ingress.*`, `litegate.route.*`, `litegate.router.*`, `litegate.service.*`, `litegate.upstream.*`, `litegate.middleware.*`, `litegate-http-*` and the other old forms are removed; an instance carrying them is rejected.


## Traffic protection on registered services

Register this identical resource tag set on every orders instance. Rate limiting admits at most 100 requests per client IP in a one-minute sliding log window. Circuit breaking tracks completed upstream outcomes independently per backend address over 30 seconds, opening at 20 samples and a failure ratio of 0.5. Rate-limit window accepts a duration (1m) or integer milliseconds; breaker window is integer seconds (30). Deregistration removes an instance after the discovery update reaches the gateway; requests during that propagation interval can still fail. Backend failures remain breaker samples. Do not mix named resources with shortcut tags.

```properties
litegate.http.routers.orders.match.hosts=api.example.com
litegate.http.routers.orders.match.path_prefix=/orders
litegate.http.routers.orders.service=orders
litegate.http.routers.orders.middlewares=orders-limit
litegate.http.middlewares.orders-limit.ratelimit.qps=100
litegate.http.middlewares.orders-limit.ratelimit.key=ip
litegate.http.middlewares.orders-limit.ratelimit.algorithm=sliding_window_log
litegate.http.middlewares.orders-limit.ratelimit.window=1m
litegate.http.services.orders.circuitbreaker.enabled=true
litegate.http.services.orders.circuitbreaker.strategy=failure_rate
litegate.http.services.orders.circuitbreaker.window=30
litegate.http.services.orders.circuitbreaker.minimumrequests=20
litegate.http.services.orders.circuitbreaker.failureratio=0.5
```

For MCP generation, read `get_config_guide(topic="traffic")`, then run `preview_service_tags`: errors must be fixed; review warnings before applying. For YAML, run `validate_site_config` before `save_site_config`.

## Operator-owned shared resources

Define shared resources in the main configuration:

```yaml
resources:
  middlewares:
    security:
      type: headers
      properties:
        response.X-Content-Type-Options: nosniff
  serverstransports:
    backend:
      dialtimeout: 2s
      responseheadertimeout: 10s
      tls:
        enabled: true
        servername: backend.example.com
  tlsoptions:
    modern:
      min_version: "1.3"
```

Use `litegate.http.routers.api.middlewares=security@file`, `litegate.http.services.app.loadbalancer.serverstransport=backend@file`, and `litegate.http.routers.api.tls.options=modern@file`. Unqualified names resolve only locally; a local definition cannot shadow `@file`. Other suffixes, missing resources and qualified declaration names are rejected. Local middleware names are isolated by provider instance, namespace and Service, including Services sharing one Host. Shared middlewares use the same types and properties as the label DSL.

TLS options require an existing TLS entrypoint and govern a Host across all ports. Conflicting effective policies reject the entire candidate. Central options cannot be assigned to catch-all Hosts. Existing legacy catch-all TLS settings remain supported and cannot bypass a concrete Host's client-certificate policy. Custom site certificates and cached identities survive policy updates. Options configure protocol versions, TLS 1.2 ciphers and optional/required client authentication; they do not select a named certificate resolver or change unified ACME configuration.

Operator transports may use `tls.rootca_file`; TLS options may use `client_ca_file` and `client_crl_file`. Workload transport labels accept PEM content, never gateway file paths. Trust files are captured during preparation and are not reread at Commit. Reload the main configuration to apply changed trust files. Invalid updates, including deletion of a referenced resource, preserve the accepted generation. MCP preview uses the accepted runtime resolver.

Site YAML can also reference a shared transport from `services.<name>.loadbalancer.serverstransport`, a shared middleware from a route's `middlewares` list, and shared TLS options from `tls.options`.

## Docker and Swarm failure behavior

Swarm Service declarations are independent of running Tasks. Scaling a declared HTTP service to zero keeps its router and publishes an empty backend pool: ordinary and upgrade requests receive **503**. Unhealthy or explicitly pending active-health targets are also unavailable selections. A connection failure after selecting a reachable target remains **502**. Deleting the Swarm Service removes its declaration and router. The standalone Docker provider continues to discover running containers; removing or stopping the last container removes that container's declaration.

Docker and Swarm publish labels and instances from a complete source snapshot. A service-list, Task-list, or transient container-inspection error keeps the last successful snapshot; it does not publish a partial deletion. A confirmed container-inspection 404 is treated as disappearance. Standalone containers keep their own resource declarations, including conflicting labels during a rolling update. Invalid resource labels reject their routes rather than inventing endpoints.

In successfully resolved standalone published-port mode, each HTTP Service's `loadbalancer.server.port` identifies a **container** port. LiteGate resolves that port to its own published host address and port, including IPv6. An absent mapping excludes the endpoint from that Service and produces a diagnostic; another Service's mapping is never reused. If provider host-port discovery falls back entirely to direct container networking, the existing direct-network behavior remains. Published binding provenance stays internal and cannot be supplied through workload metadata.

Active-health startup remains optimistic by default for compatibility. Set `healthcheck.initialready=false` together with an enabled active check to prevent traffic until the first successful probe and configured healthy threshold. Diagnostics expose source declarations separately from instances, so a zero-instance service remains inspectable.

# Swarm Service VIP

Set the Service label `litegate.swarm.lbswarm=true` to use its Service VIP. Select the network explicitly with `litegate.docker.network` or catalog `swarm_network`; the provider validates the matching network and excludes ingress. Task IP fallback is forbidden when the Service uses DNSRR, lacks a matching VirtualIP, or has an invalid network selection. Diagnostics remain attached to the declaration. Zero running Tasks retain the route with an empty pool and return 503. `false` keeps the default Task address behavior; standalone containers cannot use Service VIPs.

VIP mode hides individual Tasks. Static instance selectors, metadata selectors and gray policies reject route compilation. Request-time selectors (including IDS with `selector_merge_policy: override`), metadata, tag preferences and gray routing fail closed with 503 on ordinary and upgrade requests, even if the Service metadata appears to match. IDS decisions still run before endpoint selection.

## Composing HTTP Services

A named Service can be a leaf, a weighted group, or a failover group. Groups reference other named Services; cycles, missing references, duplicate children, mixed kinds and nonpositive weights reject the configuration. Each weighted slot requires both fields:

```text
litegate.http.routers.graph.match.hosts=graph.example.com
litegate.http.routers.graph.service=root
litegate.http.services.root.weighted.services.a.name=one
litegate.http.services.root.weighted.services.a.weight=1
litegate.http.services.root.weighted.services.b.name=two
litegate.http.services.root.weighted.services.b.weight=3
litegate.http.services.one.loadbalancer.server.port=8080
litegate.http.services.two.loadbalancer.server.port=8081
```

Weights choose child groups independently of replica counts. Replace the four weighted fields with `root.failover.service=one` and `root.failover.fallback=two` (with the same `litegate.http.services.` prefix) for failover. An empty or unhealthy primary uses the fallback without consuming an attempt; a dial failure or configured retry status switches branches only within the root retry budget and existing body replay rules. Each leaf has its own port, transport, health checks and balancing pool. A prior connection failure remains 502; no available leaf returns 503.

Tag leaves always use their registering workload source. Site YAML leaves can use static `servers`, or an explicit Docker source under `discovery: {provider: docker, namespace: default, name: backend}`. Optional `instance: "0"` selects the configured Docker provider instance; ambiguous sources are rejected. Other explicit source providers are currently unsupported. A source not yet discovered keeps the route available with a 503 response until discovery succeeds.

Group `discovery.selector.match` values are hard boundaries for every descendant leaf; a leaf adds its own hard conditions. The final IDS selector intersects these boundaries even with override enabled. Primary-only conditions are not inherited by a sibling fallback. Declare a common tenant boundary on the root when both branches must share it. Every variable in a hard condition must resolve to a nonempty value; unknown, missing or malformed placeholders reject the whole request rather than permitting fallback.

Composition supports ordinary HTTP and HTTPS requests. Upgrade requests return 503; gRPC and gRPC-Web return RPC unavailable (status 14) without contacting an upstream. Sticky cookies and child retry/timeout policies are rejected; configure the single timeout and retry policy on the root. IDS evaluates once, the request body is buffered once when replay is permitted, and the final response hook runs once. Upstream redirects are returned to the client.

# Named TCP and UDP resources

Named L4 resources compile to the existing stream engine. Resource names are local to the provider, namespace and registering service. A Service references that workload's current endpoints, including an empty declaration or a typed Swarm VIP; it cannot redirect to another workload. Unknown properties and references reject the candidate generation.

```text
# Raw TCP
litegate.entrypoints.database.address=:8090
litegate.entrypoints.database.protocols=tcp
litegate.tcp.routers.database.entrypoints=database
litegate.tcp.routers.database.service=db
litegate.tcp.services.db.loadbalancer.server.port=8090
# UDP
litegate.entrypoints.datagrams.address=:8091
litegate.entrypoints.datagrams.protocols=udp
litegate.udp.routers.datagrams.entrypoints=datagrams
litegate.udp.routers.datagrams.service=udp
litegate.udp.services.udp.loadbalancer.server.port=8091
# TLS passthrough
litegate.entrypoints.sharedtls.address=:8444
litegate.entrypoints.sharedtls.protocols=tcp
litegate.tcp.routers.secure.entrypoints=sharedtls
litegate.tcp.routers.secure.service=tlsbackend
litegate.tcp.routers.secure.match.sni=one.acceptance.invalid
litegate.tcp.routers.secure.tls.enabled=true
litegate.tcp.routers.secure.tls.passthrough=true
litegate.tcp.services.tlsbackend.loadbalancer.server.port=8443
```

The gateway must authorize tag listeners through `service_discovery.tag_entrypoints.allowed_ports: [8090, 8091, 8444]`. TCP/UDP tag listener addresses are `:port` or `0.0.0.0:port`; the backend port is separate and uses the matching TCP/UDP published binding in Docker host mode. Global stream IP restrictions remain effective.

TLS passthrough routes from multiple registered services can share one TCP listener. Exact SNI wins, followed by the most specific wildcard. Missing or unmatched SNI is rejected without reaching a backend; ClientHello and the subsequent byte stream are forwarded unchanged. Duplicate SNI, mixed plaintext/TLS listener policies, multiple plaintext or UDP routers on one port, and operator/static/HTTP listener conflicts reject publication and retain the previously accepted generation. A deleted declaration removes its route; an empty declaration retains the route and rejects new traffic until endpoints recover.

UDP endpoint updates and zero-instance transitions close old UDP sessions, including sessions from persistent clients, and recovery selects current endpoints. Established TCP sessions may finish on their previous endpoint; new connections resolve the current pool.

Removing an allowed tag port or weakening/removing an operator entrypoint while named resources still depend on it rejects the whole main-config candidate and retains the accepted generation. Remove the dependent declarations first. Main configuration changes require the existing explicit reload operation; editing that file alone does not trigger reload.

Tag-defined TLS termination, certificate file paths, certresolver, L4 middleware/IDS policies and service composition are unsupported and rejected. Operator TLS configuration remains unchanged. An operator entrypoint may be used for TCP passthrough only when its `default`, `on_non_tls` and `on_no_sni` are all `reject`, its address is a TCP network listener, and its SNI ownership does not overlap an existing HTTP or static stream route. Attachment beside operator regex/catch-all routes is rejected. UDP cannot attach to an operator TCP listener and rejects every TLS or SNI property, even a false value.
