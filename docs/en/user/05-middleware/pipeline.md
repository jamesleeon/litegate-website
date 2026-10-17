# Middleware Pipeline and Chain

Before a route is published, LiteGate compiles inline governance fields, named middleware and proxy upstream policy into one read-only PipelinePlan. Configuration can be written in different ways, but there is only one runtime order.

## Phases

Requests pass through these phases from outside in:

```text
Preflight
  → RequestTransform
  → Security
  → TrafficControl
  → Authentication
  → PostAuth
  → Response
  → Action / Upstream
```

- `Preflight`: CORS preflight and response envelope.
- `RequestTransform`: Rewrite, Headers, StripPrefix, path rewriting and redirects.
- `Security`: IP restriction, WAF.
- `TrafficControl`: RateLimit, LimitConn.
- `Authentication`: JWT, API key, inline auth, OIDC/RemoteAuth.
- `PostAuth`: handles only traffic that has passed authentication, such as Mirror.
- `Response`: Compression, Proxy Cache.
- `Upstream`: IDS, Retry, Circuit Breaker; these nodes need to understand backend instances and individual attempts and are not ordinary HTTP handlers.

Middleware plugins register through `MiddlewareRegistration` with a Descriptor (phase, order, whether multiple instances are allowed), Validate, Active and Wrap; the public interface no longer offers a parallel Stage/Priority registration. See the [plugin authoring guide](../12-plugins/authoring-guide.md).

## Reusing standard policy with Chain

`chain` is a compile-time middleware and adds no empty handler on the request hot path. It supports nesting, and cycles and undefined members are checked at load time.

```yaml
site: api.example.com
middlewares:
  security-headers:
    type: headers
    config:
      response.X-Frame-Options: DENY
      response.X-Content-Type-Options: nosniff

  api-jwt:
    type: jwt_auth
    config:
      jwks_url: https://id.example.com/.well-known/jwks.json
      issuer: https://id.example.com/

  shared-limit:
    type: ratelimit
    config:
      qps: "500"

  standard-api-security:
    type: chain
    config:
      middlewares: security-headers, api-jwt, shared-limit

/orders:
  use: [standard-api-security]
  proxy: 127.0.0.1:8080
```

A route cannot reference the same final middleware twice, even when the duplicates come from different chains; that fails to load.

## Supported named types

| Type | Phase | Key fields |
|---|---|---|
| `cors` | Preflight | `enabled`, `allowed_origins`, `allowed_methods` |
| `headers` | RequestTransform | `request.<Header>`, `response.<Header>` |
| `rewrite` | RequestTransform | `path_pattern`, `path_target`, `query_set.<name>`, `query_add.<name>`, `query_rename.<name>`, `query_remove` |
| `redirect_scheme` | RequestTransform | `scheme=http|https`, `port`, `permanent` |
| `redirect_regex` | RequestTransform | `regex`, `replacement`, `permanent` |
| `replace_path_regex` | RequestTransform | `regex`, `replacement` |
| `strip_prefix` | RequestTransform | `prefixes` |
| `csrf` | Security | `allowed_origins`, `allow_missing_origin` |
| `ip_restriction` | Security | `allow_ips`, `deny_ips` (comma-separated) |
| `ratelimit` | TrafficControl | `qps` |
| `limit_conn` | TrafficControl | `limit`, `key=global|ip` |
| `jwt_auth` | Authentication | `jwks_url` or `secret`, `issuer`, `audience`, `token_from`, `subject_claim`, `tenant_claim`, `inject_claims` |
| `api_key` | Authentication | `keys`, `extract_from`, `quotas`, `default_quota` |
| `basic_auth` | Authentication | `users`, `realm`, `remove_header` |
| `remote_auth` | Authentication | `provider`, `enabled`, `enforce`, `inject_claims`, `fail_policy` |
| `mirror` | PostAuth | `target`, `percent` |
| `compress` | Response | `enabled` |
| `retry` (deprecated) | Upstream | `attempts` |
| `circuit_breaker` (deprecated) | Upstream | `enabled`, `timeout`, `max_requests`, `trip_threshold` |
| `chain` | Compile time | `middlewares` |

`retry` and `circuit_breaker` are allowed only on the `proxy` Action. They compile into the Action's typed copy and keep using the proxy's retry budget, idempotency checks, per-instance breakers and metrics. Both types are deprecated (still usable, with a load-time notice); use the Service's `retry` / `circuitbreaker` instead, see [Named services and configuration layers](../03-configuration/services.md).

Named `rewrite`, `compress` and `remote_auth` definitions are fully equivalent to the corresponding inline action fields and run at the same position.

The `regex` of `redirect_regex` matches the full absolute URL (scheme, host, path and query), not only the path. For example, redirecting `http://example.com/old/42` to a new address:

```yaml
redirect-old:
  type: redirect_regex
  config:
    regex: "^http://example\\.com/old/(.*)$"
    replacement: "https://example.com/new/$1"
    permanent: "true"
```

## Inline and named configuration rules

- CORS, Compress, Rewrite, RemoteAuth, Retry, CircuitBreaker and RedirectScheme allow only one active instance by default.
- Using inline and named configuration for the same capability is a load error that lists the conflicting sources.
- RateLimit and LimitConn can be layered by scope: inline configuration is a route-local bucket, while named configuration is shared across the site by middleware name.
- Definitions with explicit `enabled: false` are left out of the runtime PipelinePlan and don't conflict with active instances.
- `Descriptor.AllowMultiple`, published at middleware registration, is enforced at load time; when a type that disallows multiple instances has two active definitions, the configuration fails instead of depending on wrapper override order.

MCP's `lookup_route` shows the `Effective Pipeline (outer → inner)` after chains expand; for invalid configuration, `validate_site_config` returns the specific middleware, route and conflicting sources before saving.

## Not available

Request/response buffering, DigestAuth, PassTLSClientCert, ContentType, EncodedCharacters and gRPC-Web conversion currently have no middleware type. For request body limits use the site's or route's `max_request_body_size`.

## Related docs and code

- [Named services and configuration layers](../03-configuration/services.md)
- [Public contract](../../../../pkg/plugin/middleware.go)
- [Runtime compilation](../../../../internal/router/pipeline_plan.go)
