# Routing a single OAuth callback

When an OAuth identity service registers one callback URL, select backends at that URL using original request conditions or verified business identity. Matching and rewrite are separate phases; rewriting does not make the gateway select another route.

Applications or trusted Providers must verify state signatures, expiry and session binding. The gateway does not automatically trust user-supplied tenant, redirect_uri or state values. Use IDS Selectors for hard tenant isolation and allowlist projected identity headers.

Preserve application-required code/state query parameters and avoid deleting them through query.remove/set. Test replay, expiry, wrong-tenant requests, empty backend pools and return URLs. Built-in OIDC and an application's OAuth callback are distinct configuration flows.

## Related documentation and code

- [OIDC](../05-middleware/oidc.md)
- [Rewrite](../03-configuration/rewrite.md)
- [IDS](../05-middleware/ids-governance.md)
