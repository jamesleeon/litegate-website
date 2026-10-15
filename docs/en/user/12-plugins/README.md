# Plugin system overview

LiteGate plugins are ordinary Go packages integrated through compile-time registration rather than dynamic .so files. External repositories use the public pkg/plugin contract and pkg/litegate entry without importing internal or forking the gateway. Platform, CGO and Go-version constraints still depend on the selected dependencies; arbitrary plugins are not guaranteed universally portable.

Extension points include Action, Middleware, KV, LoadBalancer, DNS, IDS, Discovery, Ingress and Template Func. Manifests describe versions, capabilities and configuration examples. CLI registration lists do not replace runtime health checks.

Middleware registers Descriptor, Validate, Active and Factory, implementing Wrap at runtime. Structured configuration uses strict Decode with JSON field tags. IDS WASM is a separate experimental option excluded from default builds; general plugins are not hot-loaded binaries.

## Related documentation and code

- [Build and CLI](build-and-cli.md)
- [Configuration](configuration.md)
- [Authoring](authoring-guide.md)
