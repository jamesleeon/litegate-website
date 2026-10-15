# Plugin configuration locations and validation

Compile plugins before referencing registered names. The table lists current configuration entries, not proposed syntax.

| Type | Configuration entry |
|---|---|
| Action | routes[].action.type; private fields decoded by the plugin |
| Middleware | middlewares.<instance>.type/config; V2 routes use use; compatibility routes use middlewares lists |
| LoadBalancer | action.lb_policy or corresponding Service policy |
| KV | action.kv_provider / kv_key |
| Ingress | Global ingress_plugins bound to entrypoints |
| Discovery | service_discovery.catalogs[].provider |
| DNS | auto_cert.dns_providers[].type/config |
| IDS | action.ids.provider/options |
| Template Func | Registered function name in templates |

Global plugin_config.path/watch selects dynamic plugin configuration. Route options carry per-request policy and should not store database passwords. Definitions do not automatically apply to every route. Validate must be pure, concurrent-safe and side-effect-free. Fix startup/reload validation failures before publishing. Do not use the nonexistent legacy auto_cert.dns.provider syntax.

## Related documentation and code

- [IDS provider](../../ids-provider-plugin-guide.md)
- [DNS provider](../../dns-provider-plugin-guide.md)
- [Ingress](../../ingress-plugin-guide.md)
- [Discovery](../../discovery-provider-plugin-guide.md)
