# Forward Auth external authorization

The default distribution includes the pure Go Forward Auth plugin. In the Authentication phase, each protected request triggers a GET check without the application body, before the action and proxy cache. 2xx permits the request; 401/403 and supported login redirects return to the client; authorization-service failures return 503.

The full URL shorthand does not infer an authorization path. The object form supports address, uri and copy_headers. Remote-User, Remote-Groups, Remote-Name and Remote-Email are copied by default. Service names must resolve from the gateway network. Multiple authorization upstreams and identity-header renaming are currently unsupported.

Proxy the login portal separately to the identity service. Both portal and application require HTTPS, valid certificates, and the identity service's cookie and access policies. LiteGate needs no additional OIDC or Redis configuration for this flow. For local password login, built-in `auth.type: sso` is also available; it does not provide groups, MFA or cross-domain cookie sharing.

```yaml
site: auth.example.com
https: true
proxy: authelia:9091
---
site: app.example.com
https: true
forward_auth: http://authelia:9091/api/authz/forward-auth
proxy: app:8080
```

## Related documentation and code

- [Authentication](authentication.md)
- [Plugin](../../../../pkg/plugins/forwardauth)
