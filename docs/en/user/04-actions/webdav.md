# WebDAV file sharing (v2)

Save as `sites/webdav.yaml` or `webdav.yaml` under the active KV site prefix; both sources use the same YAML.

## Basic configuration

```yaml
site: https://cloud.example.com
webdav: ./shared
```

This example exposes read/write access and is suitable only for trusted environments. Create the directory first; relative paths resolve from LiteGate's working directory. HTTPS issuance requires suitable global configuration and domain validation.

## Path mounting and authentication

Use `litegate -hash "your-password"` to generate a bcrypt password hash, and replace users.alice with the generated hash:

```yaml
site: https://cloud.example.com
/dav:
  webdav:
    root: ./private-data
    web_ui: true
    browse: false
    direct_download: false
  auth:
    type: basic
    realm: Private Storage
    users:
      alice: "<bcrypt-hash>"
    permissions:
      alice: rw
```

Connect to `https://cloud.example.com/dav/`. The handler automatically uses the matched /dav prefix; no additional strip_prefix is required. Do not rewrite the prefix away a second time.

- auth sits alongside webdav; file-service options belong inside webdav.
- rw permits reading and writing; ro makes an account read-only. webdav.read_only: true defaults to read-only, but explicit rw accounts can override it; set every account to ro when all users must be read-only.
- web_ui enables the browser interface; browse: false and direct_download: false prevent anonymous browsing and direct downloads.
- WebDAV needs methods including PROPFIND, PUT, MKCOL, DELETE, MOVE, COPY, and LOCK. Do not restrict the route to GET/POST.
- Files reside in a local directory; WebDAV does not support kv_mode. Loading site configuration from KV does not store files in KV.

## Administrator login without anonymous sharing

This uses LiteGate's built-in form login and SSO cookie with a local administrator account; no OIDC provider is needed. Use a dedicated hostname for the whole WebDAV site so the same configuration handles `/_auth/login`:

```yaml
site: https://files.example.com
webdav:
  root: ./private-data
  web_ui: true
  browse: false
  direct_download: false
auth:
  type: sso
  sso_enabled: true
  allow_anonymous: false
  secret: "REPLACE_WITH_A_RANDOM_SECRET_AT_LEAST_32_BYTES"
  cookie_secure: true
  cookie_same_site: lax
  session_ttl: 3600
  users:
    admin: "<bcrypt-hash>"
  permissions:
    admin: rw
```

Generate the password hash with `litegate -hash "your-password"`. Replace secret with a random key of at least 32 bytes. Give this private site its own key to avoid accepting SSO cookies issued by other sites. Define only administrator accounts permitted to enter; permissions control read/write access, not a login allowlist.

Visit `https://files.example.com/` in a browser; unauthenticated visitors are redirected to login. Anonymous directory browsing and direct file downloads are disabled. Regular WebDAV clients use Basic Auth with the same admin account; they generally cannot complete browser form login. This restricts authorization. To prevent public network connections, also use private listeners, a VPN or IP restrictions.

For external identity providers such as Keycloak or Authentik, see [OIDC](../05-middleware/oidc.md). The remote_auth session differs from WebDAV's local-account SSO; enabling OIDC alone does not enforce an administrator role.

## Connecting and troubleshooting

Enter the HTTPS URL, username, and password in your OS or WebDAV client. For 401, check authentication; for 403, check account permissions, read_only, and filesystem permissions. For path errors, ensure the front proxy preserves /dav. For upload failures, check disk space and front-proxy size/time limits; do not use the nonexistent http.write_timeout field. For HTTPS failures, check DNS, certificates, and listeners first.

Validate with `litegate -t -config config.yaml`.

## Further reading

- [v2 site configuration](../03-configuration/site-config.md)
- [Basic Auth](../05-middleware/basic-auth.md)
- [Static file serving](serve.md)
