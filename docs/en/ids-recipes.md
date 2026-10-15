# IDS business decision recipes

Begin with business requirements rather than making login, caching or Redis core assumptions. Successful signature verification can Forward without Route, keeping the default backend; business denial returns Respond 401/403. Use Selector for tenant clusters and Meta for canary versions within a cluster, falling back only to that isolated pool's default instances.

For shared applications with separate databases, query trusted tenant state, return a Selector and project database context through allowlisted headers. Login/refresh/logout use separate routes or options; Providers own the actual token lifecycle.

Dynamic limiting uses Forward RateLimitDecision. idskit offers bounded cache helpers. Notifications are optional invalidation signals followed by Resync after disconnect; offline events use dedicated NATS paths. Test wrong tenants, empty pools, key rotation, body replay and Provider timeouts for every recipe.

## Related documentation and code

- [Configuration](user/05-middleware/ids-governance.md)
- [Provider guide](ids-provider-plugin-guide.md)
- [Events](user/09-advanced/event-notification.md)
