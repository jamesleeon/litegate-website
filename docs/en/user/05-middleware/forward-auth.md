# Unified Login for LiteGate Sites with Authelia

If an application has no login system of its own, or you want to check users, groups and two-factor authentication centrally before requests reach the application, use `forward_auth`. The browser reaches LiteGate first, the gateway asks Authelia about identity and access, and only then hands the request to the business service.

To add username/password login to a single website, LiteGate's built-in `auth.type: sso` works without deploying Authelia. It provides a login page, return to the original page after login, a session cookie and logout, and checks the cookie's signature and expiry locally on every request. Users and bcrypt password hashes are kept in the site configuration, and a custom login page template can be used. See [local authentication](./authentication.md#11-local-authentication-auth).

The built-in SSO focuses on protecting the entry: it offers no group policies, no two-factor authentication and doesn't pass user identity to the backend, and its cookie has no cross-domain Domain. When you need those, use the Authelia setup below.

The default build includes a pure-Go Forward Auth middleware plugin, no CGO required. It runs in the Authentication phase, before business actions and the proxy cache. Every protected HTTP request is checked once; after login the user carries a session cookie and normally doesn't enter a password again. LiteGate needs no OIDC or Redis for this path; Authelia's own sessions and storage are configured separately.

## 1. Configure the login portal and protected site

The login portal and the application are two sites, which can share a file separated by `---`:

```yaml
site: auth.example.com
https: true
proxy: authelia:9091
---
site: app1.example.com
https: true
forward_auth:
  address: authelia:9091
  uri: /api/authz/forward-auth
  copy_headers: [Remote-User, Remote-Groups, Remote-Name, Remote-Email]
proxy: app1:8080
```

The four Authelia identity headers above are copied by default, so usually this is enough:

```yaml
site: app1.example.com
https: true
forward_auth: http://authelia:9091/api/authz/forward-auth
proxy: app1:8080
```

The full-URL shorthand also works for other authorization services that speak the same protocol. The plugin never guesses Authelia's path. Container names such as `authelia` and `app1` only work when LiteGate's network can resolve them; when LiteGate runs on the host, use real addresses such as `127.0.0.1:9091`.

LiteGate sends a GET without the business request body to the authorization endpoint; a 2xx lets the business request continue, 401/403 and common login redirects are returned to the client, and authorization service failures return 503. Multiple authorization upstreams and renaming identity headers are not supported.

## 2. Prepare domains, HTTPS and Authelia

The example uses the login portal `https://auth.example.com` and the application `https://app1.example.com`, with Authelia and the application listening on local ports `9091` and `8080`.

Both domains must resolve to LiteGate, and the HTTPS certificate must cover them. `https: true` enables the site's HTTPS behavior; certificates come from [auto cert](../06-certificates/auto-cert.md) or existing certificate configuration. Authelia uses Secure cookies, so plain HTTP or bare IPs cannot complete this browser login flow. Internal networks can use domains with test certificates.

With an existing Authelia, just check the cookie and access rules below. A new test instance can use the file user database, SQLite and the default in-memory sessions.

Create the directory and generate a user password hash:

```bash
mkdir -p authelia
docker run --rm authelia/authelia:4.39.28 \
  authelia crypto hash generate argon2 \
  --password 'replace-with-your-test-password' --no-confirm
```

Put the printed `Digest` into `authelia/users_database.yml`:

```yaml
users:
  demo:
    displayname: Demo User
    password: 'PASTE_ARGON2_DIGEST_HERE'
    email: demo@example.com
    groups: [admins]
```

A single-instance `authelia/configuration.yml`. Use different random values for the three secrets, for example from three runs of `openssl rand -hex 32`; don't keep the placeholders.

```yaml
server:
  address: tcp://0.0.0.0:9091
log:
  level: info
identity_validation:
  reset_password:
    jwt_secret: REPLACE_WITH_RANDOM_SECRET_1
authentication_backend:
  file:
    path: /config/users_database.yml
access_control:
  default_policy: deny
  rules:
    - domain: app1.example.com
      policy: one_factor
session:
  secret: REPLACE_WITH_RANDOM_SECRET_2
  same_site: lax
  cookies:
    - domain: example.com
      authelia_url: https://auth.example.com
      default_redirection_url: https://app1.example.com
storage:
  encryption_key: REPLACE_WITH_RANDOM_SECRET_3
  local:
    path: /config/db.sqlite3
notifier:
  filesystem:
    filename: /config/notification.txt
```

This example uses `one_factor` to verify the username, password and redirect flow first. The file notifier is for testing; configure SMTP for production notifications, and use shared session storage for multiple instances. See [Authelia session configuration](https://www.authelia.com/configuration/session/introduction/).

Validate, then start the container, mapping the authorization port only to the host loopback:

```bash
docker run --rm -v "$PWD/authelia:/config" authelia/authelia:4.39.28 \
  authelia validate-config --config /config/configuration.yml

docker run -d --name authelia --restart unless-stopped \
  -p 127.0.0.1:9091:9091 \
  -v "$PWD/authelia:/config" authelia/authelia:4.39.28
```

## 3. Configure the two LiteGate sites

Login portal `sites/auth.yaml`:

```yaml
site: auth.example.com
https: true
proxy: 127.0.0.1:9091
```

**Don't attach `forward_auth` to the login portal**, or users can't reach the login page.

Application `sites/app1.yaml`:

```yaml
site: app1.example.com
https: true
forward_auth: http://127.0.0.1:9091/api/authz/forward-auth
proxy: 127.0.0.1:8080
```

Validate before saving:

```bash
litegate -t -config config.yaml
```

A running LiteGate hot-reloads site files. If you're coming from an old binary, upgrade to a version that includes the Forward Auth plugin first.

Open the application domain: you should be redirected to Authelia, log in with `demo` and the password from the user database, and return to the application. The backend receives `Remote-User`, `Remote-Groups`, `Remote-Name` and `Remote-Email`.

## 4. Protect only some paths, or reuse the configuration

Site-level `forward_auth` is inherited by all routes, including static files and PHP. To protect only the admin area, put it on the route:

```yaml
site: app1.example.com
https: true
/admin:
  forward_auth: http://127.0.0.1:9091/api/authz/forward-auth
  proxy: 127.0.0.1:8080
proxy: 127.0.0.1:8080
```

To share one configuration across routes, the named middleware form is still supported:

```yaml
site: app1.example.com
https: true
middlewares:
  login:
    type: forward_auth
    config:
      address: 127.0.0.1:9091
      uri: /api/authz/forward-auth
      timeout: 3s
      copy_headers: [Remote-User, Remote-Groups, Remote-Name, Remote-Email]
/admin:
  use: login
  proxy: 127.0.0.1:8080
/private:
  use: login
  proxy: 127.0.0.1:8080
respond: public
```

Inline `forward_auth` can also be reused through `snippets` / `import`. A route's configuration replaces the whole site-level configuration rather than merging deeply; `false` doesn't mean "authentication off" and is an error. For public paths, put authentication only on protected routes or configure explicit access rules in Authelia. Don't attach the same kind of authentication middleware to one route both inline and through `use`.

## 5. Admin permissions and MFA

The gateway decides whether to call authorization; Authelia decides who can access what. For example, only `admins` may access admin pages:

```yaml
access_control:
  default_policy: deny
  rules:
    - domain: app1.example.com
      resources: ['^/admin(?:/.*)?$']
      subject: ['group:admins']
      policy: one_factor
    - domain: app1.example.com
      resources: ['^/admin(?:/.*)?$']
      policy: deny
    - domain: app1.example.com
      policy: one_factor
```

Rule order matters: allow admins first, then deny everyone else on the same path, and finally allow logged-in users to reach ordinary pages. Change the relevant rules' `policy` to `two_factor` to require MFA; users must still complete the corresponding enrollment and authentication in Authelia. The demo verified password login and group rules; verify the MFA enrollment flow against your actual notification and second-factor settings.

## 6. Parameters and response behavior

| Field | Default | Meaning |
|---|---|---|
| `address` | required | Full HTTP(S) URL, or a bare address accessed over HTTP |
| `uri` | doesn't override the address | Authorization path and query; cannot duplicate a path or query already in the address |
| `timeout` | `5s` | Positive duration, such as `500ms`, `3s` |
| `request_headers` | `[Cookie, Authorization, Accept]` | Allow list of request headers sent to the authorization service; an empty array forwards none |
| `copy_headers` | the four `Remote-*` identity headers | Headers copied from a successful authorization response into the business request; an empty array copies none |
| `response_headers` | same as `copy_headers` | Legacy field; cannot be combined with `copy_headers` |

- Only 2xx passes; 401/403 reject; 302/303/307/308 return the browser login redirect. Timeouts, connection errors, 5xx and unexpected statuses return 503 and never pass; there is no authorization cache.
- The gateway generates `X-Forwarded-Method/Proto/Host/Uri/For`; the URI includes the original query. IP and HTTPS state come from the host's resolved trusted information. With other proxies in front, configure LiteGate's trusted proxies correctly.
- The default identity headers and target headers in the copy allow list are first removed from the client request; only allow-listed headers returned by the authorization service can be injected. The backend should accept traffic only from the gateway, and later configuration shouldn't overwrite identity headers.
- `Set-Cookie` from the authorization response is kept; `WWW-Authenticate` is kept on rejection. The body is generated by the gateway; the authorization service's HTML isn't forwarded.
- Authorization over HTTPS verifies with system certificates; internal calls don't use environment HTTP proxies. Client cancellation cancels the authorization request.
- WebSocket handshakes are authorized; messages after the upgrade are not authorized one by one.

## 7. Verification and troubleshooting

Check in order: without a session the application returns 302; after login it returns 200 with the right identity; an ordinary user gets 403 on admin paths; forged identity headers can't bypass login; with the authorization service down the result is 503.

These five checks were verified on a Linux test machine with Authelia 4.39.28 and a LiteGate build; the repository also has tests for configuration shorthands, path rewriting, body preservation, cancellation and error redirects.

| Symptom | Where to look |
|---|---|
| Endless redirects after login | Does the cookie domain cover both the application and the portal? HTTPS? Does the browser accept the certificate and store the cookie? |
| Immediate 403 without login | Authelia domain, access rules and session cookie domain |
| 503 | Is the authorization address reachable? Endpoint path, service health, timeout and TLS verification |
| Unknown `forward_auth` | Is this the latest default build? Does a custom entrypoint import the plugin package? |
| Empty identity headers | `copy_headers`, the header names the application reads, and whether later configuration overwrites them |
| Wrong redirect on a non-standard HTTPS port | Do `authelia_url` and `default_redirection_url` include the actual port, such as `:18443`? |

Further reading: [Authelia proxy authorization protocol](https://www.authelia.com/reference/guides/proxy-authorization/) · [LiteGate OIDC integration](oidc.md). OIDC uses LiteGate's own login session while Forward Auth uses Authelia's per-request authorization; they are configured separately.

Plugin implementation: [pkg/plugins/forwardauth](../../../../pkg/plugins/forwardauth).
