# Discovery Provider development

Discovery Providers supply service snapshots and endpoints for third-party registries. Implement ListServices(ctx) and Resolve(ctx, query), registering Validate, Factory and Info through RegisterDiscoveryProvider. Optional Watch/lifecycle interfaces handle change notifications and resource cleanup.

Map DiscoveryQuery.Namespace to the registry's semantics. Catalog prefers the service Namespace, otherwise its configured namespace or default. Resolve/ListServices may run concurrently. Returned slices, Tags and Metadata are snapshots that must not be mutated afterward.

The host owns endpoint validation, count limits, deep copies, filtering, health, caching, multi-source merging and balancing. Plugins do not access Router or connection pools directly; Kubernetes route controllers are outside this service/endpoint interface. Honor context, authentication and secret management, and test empty results, disconnects, reconnection and shutdown.

## Related documentation and code

- [Public contract](../../pkg/plugin/discovery.go)
- [Discovery overview](user/07-discovery/overview.md)
- [Plugin build](user/12-plugins/build-and-cli.md)
