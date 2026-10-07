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
- When generating tags over MCP: consult `get_tag_reference` or `explain_tag` first; the final tag set must pass `preview_service_tags` with no diagnostics before it is applied.

## 11. Removed forms

`litegate.ingress.*`, `litegate.route.*`, `litegate.router.*`, `litegate.service.*`, `litegate.upstream.*`, `litegate.middleware.*`, `litegate-http-*` and the other old forms are removed; an instance carrying them is rejected.
