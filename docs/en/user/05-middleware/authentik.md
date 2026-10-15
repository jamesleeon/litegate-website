# authentik OIDC configuration example

LiteGate can use its built-in OIDC support with self-hosted authentik. No dedicated plugin or external account registration is required. Users sign in through authentik; LiteGate verifies their ID Token and forwards identity headers to the backend. LiteGate requires Redis for login state and sessions.

This example uses HTTP on a private network to make testing straightforward. Use HTTPS domains and valid certificates for production. Browser login, identity headers, automatic refresh, and full logout were verified with authentik **2026.8.3** and the current LiteGate source.

## 1. Prepare addresses and services

Replace the documentation address `192.0.2.10` below with your server address. Both the browser and LiteGate must be able to reach the authentik URL.

| Service | Example address |
| --- | --- |
| authentik | `http://192.0.2.10:19000` |
| LiteGate application | `http://192.0.2.10:18086` |
| Redis | `127.0.0.1:16379` |
| HTTP backend | `127.0.0.1:18087` |

Deploy authentik using its [Docker Compose installation guide](https://docs.goauthentik.io/install-config/install/docker-compose/), initialize the local administrator, and create a test user. You do not need to register on an external website. Set `COMPOSE_PORT_HTTP=19000` for the installation's HTTP port. Run Redis and the backend separately. The loopback addresses above refer to LiteGate's network environment; for a container deployment, use service addresses reachable from that container.

## 2. Create an application and provider in authentik

Create an **OAuth2/OpenID Connect Provider** and associate it with an Application:

| Setting | Value |
| --- | --- |
| Application slug | `litegate` |
| Application launch URL | `http://192.0.2.10:18086/` |
| Client type | `Confidential` |
| Client ID | `litegate-lab` |
| Client Secret | Keep the generated value for LiteGate |
| Authorization flow | `default-provider-authorization-implicit-consent` |
| Grant types, if exposed by the UI | Authorization code and Refresh token |
| Issuer mode | Keep the default separate issuer for each provider |
| Signing Key | Select an RSA certificate/key pair for `RS256` signatures |
| Encryption Key | Leave unset |
| Scope mappings | Mappings for `openid`, `profile`, `email`, and `offline_access` |
| Include claims in ID Token | Enable |

Register two **Strict** redirect URIs. In the 2026.8 UI, select the corresponding type for each:

| Type | Address |
| --- | --- |
| Authorization | `http://192.0.2.10:18086/_litegate/oauth/callback` |
| Logout | `http://192.0.2.10:18086/` |

LiteGate verifies signatures using the JWKS advertised by Discovery. Without a Signing Key, authentik uses `HS256`, which does not fit this example. Select an RSA Signing Key and leave token encryption disabled. Request `offline_access` for refresh tokens, and include user claims in the ID Token for `inject_claims`.

The issuer should be `http://192.0.2.10:19000/application/o/litegate/`. Its Discovery URL is:

```text
http://192.0.2.10:19000/application/o/litegate/.well-known/openid-configuration
```

Check that the JSON document's `issuer` exactly matches LiteGate's configuration, including the trailing `/`. Configure the issuer itself in LiteGate, not the full Discovery URL.

## 3. LiteGate global configuration

Save as `config.yaml`:

```yaml
mode: observability
entrypoints:
  web:
    address: ":18086"
auto_cert:
  enabled: false
sites_dir: ./sites

redis:
  enabled: true
  address: "127.0.0.1:16379"

auth_providers:
  authentik:
    enabled: true
    type: oidc
    issuer: "http://192.0.2.10:19000/application/o/litegate/"
    client_id: litegate-lab
    client_secret: "env:LITEGATE_AUTHENTIK_CLIENT_SECRET"
    scopes: [openid, profile, email, offline_access]
    allowed_signing_algs: [RS256]

oidc_security:
  cookie_secret: "REPLACE_WITH_RANDOM_SECRET_AT_LEAST_32_BYTES"
  cookie_same_site: lax
  me_allowed_ips: ["127.0.0.1", "::1"]
```

Replace `cookie_secret` with a random secret of at least 32 bytes; for example, generate one with `openssl rand -hex 32` and paste the value. This field takes the value directly. The `client_secret` field supports the `env:VARIABLE_NAME` syntax shown above. Set the Client Secret in the environment of the LiteGate process:

```bash
export LITEGATE_AUTHENTIK_CLIENT_SECRET='REPLACE_WITH_AUTHENTIK_CLIENT_SECRET'
litegate -config config.yaml
```

For systemd, use the service's `EnvironmentFile`; for containers, pass the environment variable to the container. Session diagnostics are restricted to localhost in this example. Add your test computer's IP to `me_allowed_ips` if you need to inspect sessions from its browser.

## 4. LiteGate site configuration

Save as `sites/app.yaml`, replacing the backend with your HTTP service:

```yaml
site: ":18086"

/public: 127.0.0.1:18087

/:
  proxy: 127.0.0.1:18087
  remote_auth:
    provider: authentik
    enforce: true
    inject_claims:
      X-Auth-User: preferred_username
      X-Auth-Email: email
      X-Auth-Subject: sub
```

`/public` allows anonymous access; other paths require authentication. The mapping direction is `header: claim`. The backend can read these headers to identify the user and should accept requests only from LiteGate. LiteGate handles the default callback path; no separate callback route is needed.

## 5. Configure logout

Visiting `http://192.0.2.10:18086/_litegate/oauth/logout` deletes the LiteGate session and redirects to authentik's End Session endpoint.

authentik's default `default-provider-invalidation-flow` preserves the global SSO session. Returning to the protected `/` route can therefore immediately sign the browser back in through SSO.

To require username and password entry after logout in this example, set the provider's **Invalidation flow** to **`default-invalidation-flow`**. This also ends the global authentik session, affecting subsequent SSO access to other authentik applications in that browser. Register the Logout redirect URI shown above as well.

This is browser-initiated logout. LiteGate does not currently implement an endpoint for authentik back-channel logout notifications.

## 6. Verify

| Action | Expected result |
| --- | --- |
| Open `http://192.0.2.10:18086/` in a browser | Redirect to authentik and return to the application after signing in |
| Inspect backend request headers | `X-Auth-User`, `X-Auth-Email`, and `X-Auth-Subject` identify the signed-in user |
| `curl -i http://192.0.2.10:18086/orders` | API request without a session returns `401` |
| `curl -i http://192.0.2.10:18086/public` | Backend responds without login |
| Supply a forged `X-Auth-User` header | Protected routes replace it with the real user; the public route strips it |
| Inspect `/_litegate/oauth/me` after login | From an allowed IP, returns `provider: authentik` and user claims |
| Temporarily set the provider access token lifetime to 2 minutes; access a protected route about 100 seconds after login | Stay signed in and see an extended `expiry` in `/me`; restore your desired lifetime afterward |
| Use the full logout flow and visit the application | authentik shows the login form again |

Browser requests with `text/html` in `Accept` redirect to login; API requests return `401`. If authentik is unavailable or Discovery fails, protected routes return `503`, and provider initialization retries in the background.

## Related documentation

- [OIDC / OAuth2 authentication guide](oidc.md)
- [Authentication overview](authentication.md)
- [authentik OAuth2/OIDC provider](https://docs.goauthentik.io/add-secure-apps/providers/oauth2/)
