# IDS Provider development and deployment

Implement pkg/plugin.IDSProvider and register Factory, Description, Options metadata and Validate through RegisterIDSProvider. Separately register a same-name Kind: ids Manifest for CLI versions and examples. Manifest and IDS Options are distinct metadata; inspect does not automatically display the complete Options Schema.

Blank-import the package in a build entry or use litegate build --with, then bind ids.provider to its registered name. Route options contain non-secret policy/references read per request. plugin_config.path/watch supplies process-side dynamic configuration. Singletons own DB/Redis/HTTP clients; key rotation should invalidate old caches and clients.

Use Dependencies logging/configuration rather than Router access. pkg/plugin/idskit provides bounded caching, IdentityLoader and response helpers to reduce duplicate lookups and cache-key mistakes. Shared Redis is not intrinsic to every Provider. Return Forward/Respond; system errors default to deny. Restore input Body and allowlist projected headers.

Use plugins list/inspect/doctor to confirm registration, then Dashboard JSON, logs, metrics and real requests to confirm instantiation/binding. Registration alone is not invocation success. Monitor timeouts, panics, concurrency rejection, breakers and calls that have not actually exited. Lifecycle/notification methods must be concurrent-safe and honor cancellation. Never log keys, complete signatures or raw bodies.

## Related documentation and code

- [IDS SDK](../../pkg/plugin/ids.go)
- [Helper kit](../../pkg/plugin/idskit)
- [MD5 compatibility provider](openapi-md5-ids-plugin.md)
