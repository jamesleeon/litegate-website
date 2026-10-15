# IDS request governance

IDS invokes a registered Provider after route matching and before the Action, covering proxy, static content, direct responses and third-party actions. Providers can inspect HTTP requests and business systems, returning Forward, Respond or error. Business denial should use Respond; only system errors follow fail_policy, defaulting to deny.

Forward without a Route keeps the original backend. Selector is a hard isolation boundary. Meta is a preference within that boundary; a missing version can fall back only to the default pool under the same Selector. selector_merge_policy defaults to intersect: conflicting values for an existing static Selector key deny the request. override explicitly authorizes replacement.

Only header_projection.allowed_headers are projected. Route options are passed per request and update without restart. Concurrent-safe Provider singletons own connection pools and caches. Restore Body after reading it and never retain request objects across calls.

```yaml
site: api.example.com
routes:
  - match: {path_prefix: /api}
    ids:
      provider: saas-session
      fail_policy: deny
      selector_merge_policy: intersect
      options: {token_header: Authorization}
      header_projection:
        allowed_headers: [X-Tenant-Ref, X-Database-Ref]
    proxy: ['127.0.0.1:8080']
```

## Related documentation and code

- [Authoring](../../ids-provider-plugin-guide.md)
