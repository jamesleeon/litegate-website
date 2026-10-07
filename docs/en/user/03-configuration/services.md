# Named Services and Configuration Layers

This page covers `services` / `serverstransports` in site configuration, and where a capability belongs: a route, a middleware or a Service. The last section lists what to check when upgrading from an older version.

---

## 1. Four Questions, Four Places

A request passing through the gateway raises four questions. Each has a fixed place in the configuration:

| Question | Where it is configured | Typical content |
|---|---|---|
| **Where does it go?** | Route `routes[].match`, `priority` | Host, path, method and header matching |
| **What happens on the way in and out?** | Middleware `middlewares` (or inline action fields) | CORS, authentication, rate limiting, WAF, rewrite, compression, caching |
| **How is the backend reached?** | **Service** `services` | Discovery, load balancing, timeouts, retries, circuit breaking, health checks, upstream TLS |
| **Who produces the response?** | Action `type` | proxy, serve, template, respond, redirect … |

To decide where a setting belongs, ask whether it needs to know the backend:

*   **It does not need the backend** and would work in front of serve or template too: it is middleware. Examples: CORS, rate limiting, compression.
*   **It acts while picking an instance, sending the request and judging the result**: it is a Service setting. A retry tries another instance; a circuit breaker records failures of a specific instance.

---

## 2. Minimal Example

Before: each route repeats the upstream settings.

```yaml
routes:
  - match: { path_prefix: /orders }
    action:
      type: proxy
      service_name: orders
      lb_policy: least_conn
      timeout: 5
      retry: 2
  - match: { path_prefix: /v2/orders }
    action:
      type: proxy
      service_name: orders
      lb_policy: least_conn
      timeout: 5
      retry: 2
```

Now: define "how to reach the backend" once and reference it by name.

```yaml
services:
  orders:
    discovery: { name: orders }
    timeout: 5s
    loadbalancer: { strategy: least_conn }
    retry: { attempts: 2 }

routes:
  - match: { path_prefix: /orders }
    action: { service: orders }
  - match: { path_prefix: /v2/orders }
    action: { service: orders }
```

Both forms behave the same, and the old form keeps working. Routes referencing the same Service share health and circuit-breaker state; a discovery-based Service also shares one load balancer, while static `servers` keep a round-robin position per route.

---

## 3. `services` Fields

Except for YAML-only static addresses and DNS resolver references, the keys match the service discovery tags `litegate.http.services.<name>.*` one to one, and so do the validation rules. A Service means the same thing whether it is declared in site YAML or in service tags.

```yaml
services:
  orders:
    discovery:
      name: orders
      selector:
        match: { version: v2 }
        meta: { zone: a }
    timeout: 5s
    loadbalancer:
      strategy: least_conn
      server: { port: 8080, scheme: https }
      serverstransport: mesh
    healthcheck: { path: /health, interval: 10s }
    retry: { attempts: 2 }
    circuitbreaker: { enabled: true, timeout: 60, maxrequests: 1, tripthreshold: 3 }

  legacy:
    servers: ["http://10.0.0.1:8080", "http://10.0.0.2:8080"]
```

| YAML key | Service tag | Meaning |
|---|---|---|
| `discovery.name` | `discovery.name` | Service name in discovery. Mutually exclusive with `servers` |
| `discovery.selector.match.<key>` | same | Hard boundary: only instances whose metadata has this value |
| `discovery.selector.meta.<key>` | same | Soft preference: preferred instances, falling back to the whole hard-boundary set |
| `servers` | — (YAML only) | Static backend addresses. Mutually exclusive with `discovery.name`; cannot be combined with `selector` |
| `resolver` | — (YAML only) | Reference a global named DNS resolver; see [Upstream DNS](upstream-dns.md) |
| `timeout` | `timeout` | End-to-end timeout of one request, e.g. `30s`, `500ms` |
| `loadbalancer.strategy` | `loadbalancer.strategy` | `round_robin`, `weighted`, `weighted_round_robin`, `least_conn`, `p2c`, `ip_hash`, `cookie` or a plugin strategy |
| `loadbalancer.server.port` | `loadbalancer.server.port` | Overrides the instance port |
| `loadbalancer.server.scheme` | `loadbalancer.server.scheme` | `http`, `https`, `h2c`, `grpc`, `grpcs` |
| `loadbalancer.serverstransport` | `loadbalancer.serverstransport` | Referenced ServersTransport |
| `healthcheck.path` / `healthcheck.interval` | same | Active health check |
| `retry.attempts` | `retry.attempts` | Number of retries after a failure |
| `circuitbreaker.enabled` / `timeout` / `maxrequests` / `tripthreshold` | same | Circuit breaker: on/off, open duration in seconds, half-open requests, consecutive failures that trip it |

Note: these keys follow the tag spelling (`maxrequests`, `serverstransport`), not the underscore form.

## 4. `serverstransports` Fields

```yaml
serverstransports:
  mesh:
    tls:
      enabled: true               # TLS to the upstream; scheme defaults to https when the Service sets none
      clientcertificate: litemesh # mutual TLS with the Litemesh identity
      insecureskipverify: false   # skip upstream certificate checks; not allowed with clientcertificate
```

---

## 5. Reference Rules

*   The Service referenced by `action.service` must be defined in the same site's `services`; otherwise loading fails.
*   `type` may be omitted when referencing a Service; it defaults to `proxy`.
*   **A route's backend has exactly one source of configuration.** A route that references a `service` cannot also set these upstream fields inline: `service_name`, `upstream`, `lb_policy`, `timeout`, `retry`, `circuit_breaker`, `health_check`, `route_selector`, `route_meta`, `service_port`, `proto`, `insecure_skip_verify`, `mtls`. Loading fails otherwise.
*   Fields that are not Service settings, such as `strip_prefix` and `headers`, stay on the action:

```yaml
routes:
  - match: { path_prefix: /api/orders }
    middlewares: [web-cors]
    action:
      service: orders
      strip_prefix: /api
```

---

## 6. Which Form to Use

| Situation | Recommendation |
|---|---|
| One backend used by one route | Inline or Service, either works |
| Several routes point at the same backend | Use a Service: defined once, state shared |
| Retries, circuit breaking, health checks, upstream TLS | Use a Service: these are all about reaching the backend |
| Services registered in Consul / LiteMesh with tags | Keep using tags; a tag Service and a YAML Service are the same model |

### Named middleware and inline fields

These named middleware types are fully equivalent to their inline action fields and run at the same position. Pick either depending on whether you want to reuse them:

| Named middleware type | Equivalent inline field |
|---|---|
| `rewrite` | `action.rewrite` |
| `compress` | `action.compress` |
| `remote_auth` | `action.remote_auth` |

These two middleware types are **deprecated**. They still work and log a warning once at load time. Use a Service instead:

| Deprecated | Use instead |
|---|---|
| `retry` middleware | `services.<name>.retry.attempts` |
| `circuit_breaker` middleware | `services.<name>.circuitbreaker.*` |

A capability cannot be configured twice, once as named middleware and once inline; loading fails.

---

## 7. Inspecting the Effective Pipeline

You can look up which steps a route runs and in what order instead of inferring it:

*   **Dashboard API**: `GET /api/routing/pipeline?site=<domain>&route=<route name>` returns the steps from outer to inner, with their source (inline / named) and phase.
*   **MCP**: the `Effective Pipeline` in the output of the `lookup_route` tool.

The pipeline and the running handler chain come from the same compilation, so they always agree.

---

## 8. Upgrading from an Older Version

**Replacing the binary is enough: existing site configurations, service tags and Kubernetes resources need no changes.** Check the following before upgrading.

### 8.1 Changes that may require configuration updates

**CORS security fixes** (see [CORS](../05-middleware/cors.md)):

*   `cors.enabled: true` no longer turns on credentials (cookies) implicitly. If you relied on it, list the origins explicitly and set `allow_credentials: true`.
*   `allowed_origins: "*"` (or `enabled: true` without origins) together with `allow_credentials: true` now **fails to load**. List the trusted origins instead.
*   Only an `OPTIONS` request carrying `Access-Control-Request-Method` is answered as a preflight; other `OPTIONS` requests (e.g. WebDAV) reach the action.
*   Once CORS is configured on a route, `Access-Control-*` headers returned by the backend are replaced by the gateway's policy.

**A `service:` key on a proxy action**: a stray `service:` key on a proxy action used to be ignored; it now references a Service and fails to load if none is defined. On other action types (including plugins) `service:` is still passed through as a plugin parameter.

### 8.2 Display-only changes

*   **The pipeline shows positions more accurately.** Named `rewrite`, `compress`, `remote_auth`, `retry` and `circuit_breaker` now appear where they actually run. They used to be listed elsewhere; the execution order itself has not changed.
*   **Chains may be expanded in a route's middleware list.** If a route references one of the types above (including through a chain), the Dashboard shows that route's middleware list with the chain expanded to its members.
*   **Key order in site YAML generated by MCP changes**; the content does not.

### 8.3 Upgrade checklist

1.  Search site configurations for `allow_credentials: true` and make sure the matching `allowed_origins` is an explicit list.
2.  Find routes that relied on `cors.enabled: true` to carry cookies and add origins plus `allow_credentials: true`.
3.  Make sure no proxy action carries a leftover `service:` key.
4.  (Optional) Consolidate repeated upstream settings into `services`, and move `retry` / `circuit_breaker` middleware into Service settings.
5.  After starting, check the log for deprecation warnings and spot-check key routes with `/api/routing/pipeline`.

---

## Further Reading

- [Site Configuration Reference](site-config.md)
- [Service Tag Reference](tag-reference.md)
- [CORS](../05-middleware/cors.md)
