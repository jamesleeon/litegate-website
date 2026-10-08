# Authentication Overview

LiteGate implements two distinct authentication pipelines designed to address different operational scopes:

- **`action.auth`**
  - Designed for L7 static YAML routes.
  - Supports `basic`, `sso`, and `jwt` authentication.
- **`action.remote_auth`**
  - Designed for L4/L7 dynamic service discovery registries and Litemesh Identity Service (IDS) integration.
  - Supports `remote_auth`, `ids_session`, and `oidc` authentication.

> [!TIP]
> If your primary focus is dynamic service mesh routing driven by Consul/Litemesh tags or SaaS IDS tenant isolation, jump directly to the [Remote Auth Guide](./remote-auth.md).

---

## 1. Authentication Categories

### 1.1 L7 Static Authentication: `auth`

This represents standard site or route authentication declared inside static YAML configurations under the `Action.Auth` scope.

#### Supported Types:
- **`basic`**: Standard HTTP Basic Authentication.
- **`sso`**: Lightweight built-in gateway Single Sign-On flow.
- **`jwt`**: Static JSON Web Token verification.

#### Best Suited For:
- Gateway Admin Dashboards.
- WebDAV Share Mounts.
- Simple private static pages.
- Localized security scopes that do not depend on the dynamic Litemesh Identity Service (IDS).

---

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
    token_from: [header, cookie:lg_token]   # Authorization: Bearer first, then the cookie
    subject_claim: user_id
    tenant_claim: tenant_id                 # optional
  proxy: 127.0.0.1:8080
```

- `token_from`: token sources in order. `header` (the default) is `Authorization: Bearer`; `cookie:<name>` reads a cookie. Browsers' `EventSource` cannot set headers, so notification subscriptions usually read an HttpOnly cookie. Query-string tokens are not supported because they leak into logs.
- `subject_claim` / `tenant_claim` make the token the gateway's **verified identity**. A token without the configured claim is rejected with 401. Notifications use the identity for per-subscriber progress (`offline: auth.subscriber`) and tenant subjects (`{auth.tenant}`). Without them the token is only verified.
- `issuer` / `audience` check `iss` / `aud` when set.
- Any verified token ends long-lived responses (such as notification streams) at its `exp`, whether or not an identity is mapped. A token without `exp` has no bound, so issuers should always set it.
- Numeric claims are kept exact, so 18-digit snowflake IDs keep their precision.
- Client-supplied `X-Lito-*` and `X-Tenant-ID` headers are stripped at ingress and cannot be forged.

The named middleware `type: jwt_auth` takes the same fields (comma-separated `token_from` and `audience`) for reuse across routes.

### 1.2 L4/L7 Dynamic Authentication: `remote_auth`

This serves as the primary ingress integration point for LiteGate and the Litemesh Identity Service (IDS), executing under the `Action.RemoteAuth` runtime scope.

#### Core Runtime Categories:
- **`remote_auth`**: Dynamically fetches authentication metadata keys, executing local verification protocols (such as `md5` or `jwt` token signatures).
- **`ids_session`**: Restores tenant/user context directly from session cookie stores, dynamically steering requests by tenant `sid`.
- **`oidc`**: Orchestrates OpenID Connect authorization flows.

#### Best Suited For:
- Open Developer APIs.
- Multi-Tenant SaaS Portals.
- Unified `/login` or `/api` state tracking flows.
- Identity-based policy steering.

---

## 2. HTTP Basic Authentication (`basic`)

HTTP Basic Authentication is handled securely using Bcrypt hashing for password validation.

### Configuration Example
```yaml
domain: admin.example.com
routes:
  - name: admin
    match:
      path_prefix: /
    action:
      type: proxy
      upstream:
        - 127.0.0.1:8080
      auth:
        type: basic
        realm: "LiteGate Admin"
        users:
          admin: "$2a$10$..."  # Bcrypt password hash
```

### Under the Hood
* Verification is evaluated using `bcrypt.CompareHashAndPassword` comparisons.
* Unauthenticated requests are rejected with an HTTP `401 Unauthorized` status along with a `WWW-Authenticate` header.

---

## 3. JWT Verification (`jwt`)

Standard static JSON Web Token authentication that functions independently of the Litemesh IDS control plane.

### Configuration Example
```yaml
domain: api.example.com
routes:
  - name: private-api
    match:
      path_prefix: /api
    action:
      type: proxy
      upstream:
        - 127.0.0.1:8080
      auth:
        type: jwt
        jwks_url: https://issuer.example.com/.well-known/jwks.json
        issuer: https://issuer.example.com
        audience:
          - my-api
```

### Checked Constraints
The static JWT engine validates:
- `Authorization: Bearer <token>` header payload formats.
- Cryptographic signatures against the configured JWKS endpoint.
- Optional matches against `issuer` assertions.
- Optional matches against `audience` scopes.

---

## 4. Built-in SSO Flow (`sso`)

A lightweight, local Single Sign-On flow built into LiteGate, designed for static portals and administration panels.

### Configuration Example
```yaml
domain: docs.example.com
routes:
  - name: docs
    match:
      path_prefix: /
    action:
      type: serve
      root: ./public
      auth:
        type: sso
        secret: change-me  # SSO signing secret
        users:
          admin: "$2a$10$..."
```

### Under the Hood
The SSO processor registers and manages:
* Automatic callback endpoints: `/_auth/login` and `/_auth/logout`.
* Session cookie state tracking via the `litegate_sso_token` cookie.

---

## 5. Dynamic Integrations Roadmap

If your operational objectives align with any of the following patterns, bypass `auth` and implement `remote_auth` directly:
* Declaring access control via Consul/Litemesh dynamic registration tags.
* Open platform API key signature checks (`AppId` + signature).
* Fetching keys dynamically via the Litemesh IDS control plane.
* Unified portal state routing.
* Dynamic multi-tenant routing based on tenant ID (`sid`).

---

## 6. Architecture Selection Matrix

### Choose `auth` when:
* Managing single-site deployments.
* Relying on static, file-based YAML configurations.
* Protecting straightforward backend administrative panels.

### Choose `remote_auth` when:
* Integrating with dynamic service registries (Consul / Litemesh).
* Routing multi-tenant SaaS traffic.
* Exposing public open platform APIs.
* Utilizing the dynamic IDS control plane.

---

## Further Reading
- [Configuring Remote SSO Interceptors via Remote Auth](./remote-auth.md)
- [Implementing Federated Identity via OIDC](./oidc.md)
- [IDS Control Plane Reference Docs](../../ids_development_guide.md)
- [How to Generate Bcrypt Hashes via CLI](../../user/01-getting-started/installation.md#command-line-options)
