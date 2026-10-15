# Authentication and IDS governance

Choose among three responsibilities: auth supplies local basic/sso/jwt; remote_auth handles OIDC/OAuth2 login and sessions; ids uses business Providers for validation, direct responses, header projection or dynamic isolation, across all Actions.

Local SSO provides a login page, signed cookies, return-to-page flow and logout without an additional identity service. Use an independent random secret of at least 32 bytes and bcrypt users. Basic login needs no Redis; failure counting/IP lockout does. Cookies default to 24 hours and support session_ttl, cookie_secure and template settings. Logout clears browser cookies but provides no per-session server revocation, automatic subdomain sharing or username injection. Use an external service for group policy/MFA.

JWT requires exactly one of secret (HS256/384/512) and jwks_url (RS/ES), rejecting alg:none. Use env://, file:// or supported key references and optional issuer/audience checks. token_from selects the first non-empty value; invalid selected tokens fail. Query tokens are unsupported. Browser SSE can read HttpOnly cookies.

subject_claim/tenant_claim establish trusted notification identity; missing mapped claims return 401. tenant_claim requires subject_claim and numeric IDs retain precision. Without mappings, only validation is performed. JWT exp expiry closes long-lived connections; applications must define lifecycles for tokens without exp. Named jwt_auth shares policy.

Authentication does not turn client-supplied tenant headers into authorization. IDS headers need explicit allowlists; Providers implement business login/token/session semantics. OIDC needs separate configuration and Redis; see its guide.

```bash
litegate -hash 'replace-with-your-password'
litegate -secret
```

```yaml
site: app.example.com
https: true
auth:
  type: sso
  secret: REPLACE_WITH_A_RANDOM_SECRET_AT_LEAST_32_BYTES
  users:
    demo: REPLACE_WITH_BCRYPT_PASSWORD_HASH
  session_ttl: 86400
  cookie_secure: true
proxy: 127.0.0.1:8080
```

```yaml
site: app.example.com
/api:
  auth:
    type: jwt
    secret: env://APP_JWT_SECRET
    token_from: [header, 'cookie:lg_token']
    subject_claim: user_id
    tenant_claim: tenant_id
  proxy: 127.0.0.1:8080
```

## Related documentation and code

- [Basic](basic-auth.md)
- [Forward Auth](forward-auth.md)
- [OIDC](oidc.md)
- [authentik OIDC configuration example](authentik.md)
- [Remote Auth](remote-auth.md)
- [IDS](ids-governance.md)
- [Notify/JWT](../09-advanced/notify-jwt-integration.md)
