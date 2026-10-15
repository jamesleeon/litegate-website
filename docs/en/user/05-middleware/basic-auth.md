# HTTP Basic Auth

The named `basic_auth` middleware protects routes in the Authentication phase. Generate a bcrypt hash with `litegate -hash`; users is a comma-separated list of `username:bcrypt_hash`. Plaintext, MD5 and SHA passwords are rejected during loading. Replace the example hash with a complete generated hash.

Missing or invalid credentials return 401 with WWW-Authenticate. realm defaults to `LiteGate Restricted` and cannot contain quotes or control characters. `remove_header: true` removes Authorization after successful authentication; `enabled: false` disables the definition. Protect Basic credentials with HTTPS. Routes can share a definition. Inline `auth.type: basic` is a separate configuration entry; avoid stacking equivalent authentication.

```bash
litegate -hash 'replace-with-your-password'
```

```yaml
site: internal.example.com
middlewares:
  admin-gate:
    type: basic_auth
    config:
      users: 'admin:$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy'
      realm: Internal Tools
      remove_header: true
routes:
  - match: {path_prefix: /}
    use: [admin-gate]
    proxy: ['127.0.0.1:8080']
```

## Related documentation and code

- [Authentication](authentication.md)
- [Implementation](../../../../internal/middleware/basic_auth.go)
