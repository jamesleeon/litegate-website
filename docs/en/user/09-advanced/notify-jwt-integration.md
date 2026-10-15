# Notify and application JWT integration

The gateway verifies application JWTs; applications own issuance, refresh and business-state storage. Choose exactly one of secret or jwks_url, reject alg:none and set issuer/audience to the business contract. token_from selects the first non-empty token; an invalid selected token fails without trying later sources. Query tokens are unsupported. Browser EventSource can use an HttpOnly cookie.

subject_claim establishes a trusted subscriber. tenant_claim establishes a trusted tenant and requires subject_claim; missing mapped claims return 401. Notification identities accept letters, digits, underscores and hyphens, up to 128 characters. exp expiry closes the connection.

offline: auth.subscriber with notify.{auth.tenant}.workorder binds progress to tenant and identity. Reference the ACK secret through plugin shared configuration, not the JWT secret env:// rules; all nodes use the same key. Subscription templates allow only auth.tenant/auth.subscriber. Publish templates may use body/header/query, requiring authorization against cross-tenant publishing.

Shorthand quotas are shared per site; use a full NATS action's sse.tenants for tenant quotas. Applications handle revocation, reconnect, invalid ACKs and duplicates. Optional IDS notifications do not provide JetStream offline semantics.

```yaml
site: app.example.com
notify:
  ack_secret_ref: shared.notify_ack_secret
  retention: 168h
  replicas: 1
/events/workorder:
  auth:
    type: jwt
    secret: env://APP_JWT_SECRET
    token_from: ['cookie:lg_token']
    subject_claim: user_id
    tenant_claim: tenant_id
  subscribe: notify.{auth.tenant}.workorder
  offline: auth.subscriber
```

```yaml
plugins:
  nats:
    connections:
      default:
        servers: nats://127.0.0.1:4222
shared:
  notify_ack_secret: REPLACE_WITH_AT_LEAST_32_RANDOM_BYTES
```

## Related documentation and code

- [Authentication](../05-middleware/authentication.md)
- [SSE contract](../04-actions/nats-sse.md)
- [Event delivery](../04-actions/nats-events.md)
