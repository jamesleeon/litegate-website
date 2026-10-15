# IDS overview

IDS is a business-decision interface after route matching and before Action execution. It supports business-identity validation, trusted-header projection and dynamic routing. The core has no built-in tenant_id, app_id, login or JWT lifecycle; plugins query business systems and decide.

Forward continues execution, Respond returns directly, and error represents system failure governed by fail_policy. IDS can protect all Actions; Selector/Meta instance selection matters only for proxy. Use middleware for ordinary HTTP authentication/transformation and IDS for business identity and backend isolation.

Prefer Go Providers for database, HTTP, Redis and cache integration. Experimental WASM is computation-only without general I/O and is excluded from default builds. Define denial semantics, failure policy, isolation boundaries and header allowlists before implementation.

## Related documentation and code

- [Provider authoring](ids-provider-plugin-guide.md)
- [Go / WASM](ids-go-vs-wasm.md)
