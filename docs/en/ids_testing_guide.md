# IDS Provider acceptance guide

Test the unified Provider contract rather than treating historical fixed Redis Session/Cookie/Key formats as built-in behavior. Build the plugin binary, confirm registration/metadata with plugins list/inspect/doctor, bind ids.provider to routes and preflight configuration.

Check Forward's default destination and allowlisted headers, Respond status/body and system-error fail_policy. Business denial must remain denied even under allow. Test static/dynamic Selector conflicts, default-only Meta fallback, wrong tenants and empty pools, including IDS protection of serve/respond.

Use real bodies to verify restoration after reading. Concurrently test singleton safety, cancellation, timeouts, panics, breakers and concurrency caps. Verify configuration reloads, key rotation, invalidation and optional Resync separately. Inspect logs/metrics without logging keys or complete signatures; visible registration is not proof of working business traffic.

```bash
litegate plugins list
litegate plugins inspect ids/openapi-md5
litegate plugins doctor
go test ./internal/middleware ./pkg/plugin/...
```

## Related documentation and code

- [Provider guide](ids-provider-plugin-guide.md)
- [Guard tests](../../internal/middleware/ids_guard_test.go)
- [Governance tests](../../internal/middleware/ids_governance_test.go)
