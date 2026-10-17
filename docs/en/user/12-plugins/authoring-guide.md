# Plugin authoring contracts

Use pkg/plugin from an independent Go module. Handle registration errors, choose non-conflicting names and declare version/description through Manifest. Do not override reserved built-in types or depend on internal implementation details.

Structured Config.Decode uses json tags and rejects unknown fields; plugin.Duration supports durations. Middleware implements Wrap and declares Descriptor and required Validate through MiddlewareRegistration, with optional Active/InlineConfig. Validation and inline conversion must be deterministic, side-effect-free and concurrent-safe. Do not implement obsolete Stage/Priority registration.

Use Dependencies for logging, discovery and configuration. Instances can be called concurrently; avoid shared mutable request data. Release resources through the extension's optional lifecycle contracts such as Start/Close, honor context cancellation and distinguish business denial from system failure.

Start from examples/plugin-template and examples/plugins. Validate registration, custom builds, configuration and real requests. Ingress, Discovery, IDS and DNS have specialized contracts. WASM is an experimental IDS option only.

## Related documentation and code

- [Public SDK](../../../../pkg/plugin)
- [Plugin template](../../../../examples/plugin-template/README.md)
- [Plugin examples](../../../../examples/plugins/README.md)
- [Discovery implementation and build walkthrough: Nomad](../../discovery-provider-plugin-guide.md)
