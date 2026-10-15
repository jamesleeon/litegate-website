# Remote Auth (OIDC / OAuth2)

remote_auth is the compatibility entry for browser OIDC/OAuth2 federation. Open-platform signatures, tenant sessions and dynamic isolation have moved to IDS and cannot be configured through remote_auth. IDS protects all Actions, not only proxy.

Declare an oidc/oauth2 Provider under global auth_providers, then set enabled, provider, enforce and required inject_claims under the site's Action remote_auth. Login redirects and sessions require Redis, so configure it as well. Callback URLs must match identity-provider registration and gateway callback paths. See the OIDC guide for full fields.

enforce controls whether missing sessions require login. fail_policy defaults to deny; explicit allow bypasses system failures and requires deliberate risk assessment. Invalid Provider types must not be treated as successful authentication; inspect loading warnings and real requests. IDS trusted headers use ids.header_projection.allowed_headers, not the obsolete ids.allowed_headers field.

## Related documentation

- [OIDC](oidc.md)
- [Authentication](authentication.md)
- [IDS](../../ids-provider-plugin-guide.md)
- [OIDC implementation](../../../../internal/middleware/oidc.go)
