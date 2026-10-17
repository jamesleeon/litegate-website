# Authentication (Gateway Identity and Governance Overview)

LiteGate offers three configuration paths for authentication and governance, split by responsibility:

- **`auth`** (local authentication)
  - For static YAML routes.
  - Suits simple single-site authentication such as `basic`, `sso` and `jwt`.
- **`remote_auth`** (OIDC authentication)
  - For standard OIDC (OpenID Connect) / OAuth2 single sign-on redirects and session management.
- **`ids`** (business identity decisions)
  - For deep integration with dynamic service discovery, multi-tenant SaaS architectures and identity-driven routing.
  - A Provider implements verification, caching, direct responses, header projection and optional physically isolated routing.
  - Runs after route matching and before the Action, and can protect every Action; dynamic instance selection (Selector/Meta) only matters for proxy.

---

## 1. The three paths

### 1.1 Local authentication: `auth`
Site or route authentication written in the `auth` field. Supports `basic` / `sso` / `jwt` for simple cases that don't depend on an external identity platform.

#### Built-in login for a website

`auth.type: sso` protects a proxied or static website directly, with no extra authentication service. The configuration below protects the whole site and also covers `/_auth/login` and `/_auth/logout`, so login and logout requests reach the authentication handler:

```yaml
site: app.example.com
https: true
auth:
  type: sso
  secret: "REPLACE_WITH_A_RANDOM_SECRET_AT_LEAST_32_BYTES"
  users:
    demo: "REPLACE_WITH_BCRYPT_PASSWORD_HASH"
  session_ttl: 86400
  cookie_secure: true
proxy: 127.0.0.1:8080
```

Generate two independent values and configure an HTTPS certificate before deploying:

```bash
# Prints a bcrypt password hash for users.demo
litegate -hash 'your-password'

# Prints 32 random bytes as hex (64 characters) for secret
litegate -secret
```

`-hash` is for user password hashes; `secret` signs the session cookie and must be an independent random key, never a user password or its bcrypt hash. On first visit users are sent to the login page and returned to the original page after login; afterwards each request only checks the cookie's signature and expiry locally. Sessions last 24 hours by default; `template` customizes the login page.

The basic login flow doesn't need Redis; the per-IP failure counting and temporary lockout do. Sessions are stateless signed cookies: logout clears the browser's cookie, but there is no server-side per-session revocation. The cookie is host-only and not shared across subdomains, and the username is not injected into backend requests.

For centrally managed users, group permissions, two-factor authentication or passing identity to the backend, use [Authelia / Forward Auth](./forward-auth.md); for login through a standard identity provider, use OIDC below.

#### Protecting APIs and subscriptions with JWT

`auth.type: jwt` lets the gateway verify JWTs issued by your application, without calling back into the backend. Choose one key source:

| Field | Use when | Notes |
|---|---|---|
| `secret` | Tokens are signed with an HS256/384/512 shared key | Write a reference: `env://APP_JWT_SECRET`, `file:///etc/litegate/jwt.key` or `${APP_JWT_SECRET}`; never paste the key into the site file |
| `jwks_url` | An identity provider signs with RS/ES keys and publishes a JWKS | e.g. `https://idp.example.com/.well-known/jwks.json` |

Each source pins its algorithm family (HS only for `secret`, RS/ES only for `jwks_url`) to prevent algorithm-confusion attacks; `alg: none` is always rejected.

```yaml
site: app.example.com
/api:
  auth:
    type: jwt
    secret: env://APP_JWT_SECRET
    token_from: [header, 'cookie:lg_token'] # Authorization: Bearer first, then the cookie
    subject_claim: user_id                  # user identity
    tenant_claim: tenant_id                 # tenant identity (optional)
  proxy: 127.0.0.1:8080
```

- `token_from`: token sources, tried in order; the first non-empty value is used. If that token is invalid the request is rejected; later sources are not tried. `header` means `Authorization: Bearer` (the default) and `cookie:<name>` reads a cookie. Browser `EventSource` cannot set request headers, so subscriptions usually read an HttpOnly cookie. To avoid leaking tokens into logs, URL query tokens are not supported.
- `subject_claim` / `tenant_claim`: turn token claims into the gateway's **verified identity**. `tenant_claim` requires `subject_claim`. When configured, a token missing the claim gets 401; after verification, event notifications use them to tell subscribers (`offline: auth.subscriber`) and tenants (`{auth.tenant}`) apart. Without them only the signature is checked.
- `issuer`, `audience`: when set, `iss` and `aud` are checked.
- Once verified, long-lived connections (such as event streams) close when the token's `exp` passes, whether or not identity mapping is configured. Tokens without `exp` have no such bound and connections are limited only by their own maximum duration, so issuers should always set `exp`.
- Numeric claims are kept as-is; 18-digit snowflake IDs keep their precision.
- Identity headers sent by clients such as `X-Lito-*` and `X-Tenant-ID` are stripped at the entry and cannot be forged.

To share one configuration across routes, use the named middleware `type: jwt_auth` with the same fields (`token_from` and `audience` comma-separated).

### 1.2 OIDC authentication: `remote_auth`
Handles OIDC/OAuth2 login redirects, callbacks and session upkeep; session storage requires Redis. See the [OIDC guide](./oidc.md) and the [authentik example](./authentik.md).

### 1.3 Identity-driven routing and governance: `ids`
Different paths pick different Providers; the core only understands Forward, Respond, errors and optional Selector/Meta, not specific business actions. Business login, tokens and sessions are implemented by the Provider; headers projected to the backend go through an explicit allow list, and authentication never treats a client-supplied tenant header as authorization. See the [IDS governance guide](./ids-governance.md).

---

## 2. Further reading

- [Basic Auth middleware](./basic-auth.md)
- [IDS governance guide](./ids-governance.md)
- [OIDC guide](./oidc.md)
- [IDS Provider plugin development and configuration](../../ids-provider-plugin-guide.md)
- [Forward Auth / Authelia](./forward-auth.md)
- [Remote Auth](./remote-auth.md)
- [Notify and JWT integration](../09-advanced/notify-jwt-integration.md)
