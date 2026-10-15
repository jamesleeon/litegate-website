# Middleware pipeline and chains

Before publication, inline fields, named middleware and upstream policies compile into an immutable PipelinePlan. The order is Preflight → RequestTransform → Security → TrafficControl → Authentication → PostAuth → Response → Action/Upstream.

CORS runs in Preflight; rewrite, headers, strip_prefix and redirects in RequestTransform; IP/WAF in Security; rate/concurrency limits in TrafficControl; identity checks in Authentication; mirror in PostAuth; compression/proxy cache in Response. IDS and proxy-internal retries and breakers follow their own execution contracts.

`chain` expands at compile time and supports nesting. Undefined members, cycles and duplicate references after expansion fail loading. Middleware plugins use MiddlewareRegistration Descriptor/Validate/Active and Wrap. The current public contract no longer exposes dual Stage/Priority registration.

Named rewrite, compress and remote_auth execute at the same locations as inline fields. Named retry/circuit_breaker are deprecated, remain compatible and require proxy actions. Put new upstream policies in Services.

```yaml
site: api.example.com
middlewares:
  safe-headers:
    type: headers
    config: {response.X-Content-Type-Options: nosniff}
  api-policy:
    type: chain
    config: {middlewares: safe-headers}
routes:
  - match: {path_prefix: /api}
    use: [api-policy]
    proxy: ['127.0.0.1:8080']
```

## Related documentation and code

- [Services](../03-configuration/services.md)
- [Public contract](../../../../pkg/plugin/middleware.go)
- [Runtime](../../../../internal/router/pipeline_plan.go)
