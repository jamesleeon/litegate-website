# Notify and Business JWT Integration: Configuration, Limits and Troubleshooting

This page records the boundaries between gateway notifications, third-party JWTs, offline consumption and IDS notifications. Business state may come from a database, KV or any other system; the gateway doesn't constrain state storage, and it doesn't issue or refresh JWTs for the business system.

## 1. Choose the notification semantics first

| Need | Configuration and responsibility |
|---|---|
| Online alerts; after a disconnect, re-query current state | Omit `offline` and use Core NATS; resynchronize from the business system on every connect |
| Events during an offline period after the first subscription must be delivered later | Publish with `offline: true`, subscribe with `offline: auth.subscriber`; uses JetStream and business ACKs |
| Optional state invalidation for an IDS Provider | Implement `plugin.NotifySubscriber`; the plugin notify bus is an online signal + Resync, not a JetStream offline queue |

An IDS doesn't have to use a cache, nor subscribe to notifications. A Provider that only verifies signatures need not touch notify at all. Plugins that need notifications define their own subjects, message formats and handling.

## 2. Same-origin browsers, reliable multi-tenant subscriptions

Site configuration (v2):

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
    token_from: [cookie:lg_token]
    subject_claim: user_id
    tenant_claim: tenant_id
  subscribe: notify.{auth.tenant}.workorder
  offline: auth.subscriber
```

Plugin configuration:

```yaml
plugins:
  nats:
    connections:
      default:
        servers: nats://127.0.0.1:4222
shared:
  notify_ack_secret: "REPLACE_WITH_AT_LEAST_32_RANDOM_BYTES"
```

The ACK secret above is a placeholder; replace it with at least 32 random bytes distributed through controlled plugin configuration. `ack_secret_ref` names a plugin configuration key; the JWT `env://` reference rules don't apply to it. All gateway nodes use the same ACK secret, which is a different secret from the JWT key. Production NATS clusters can use `replicas: 3` given enough nodes.

Configure authentication separately for the publishing route:

```yaml
/internal/publish/workorder:
  auth:
    type: jwt
    secret: env://NOTIFY_PUBLISH_JWT_SECRET
    token_from: [header]
    issuer: trusted-notify-publisher
    audience: litegate-notify
  publish: notify.{body.tenant_id}.workorder
  offline: true
```

Give this publishing key only to trusted publishing services. `body.tenant_id` lets the publisher choose the target tenant, and the gateway does not check that it matches the caller's identity. When tenant users publish themselves, use `notify.{auth.tenant}.workorder` with a verified tenant claim, or add business authorization. Never give a browser a credential that can publish across tenants.

## 3. Responsibilities of the JWT and the cookie

Publishing can also pick the subject from a custom header, without a tenant field in the body:

```yaml
/internal/publish/workorder:
  publish: notify.{header.key}.workorder
  offline: true
```

A request carrying `key: tenant_a` publishes to `notify.tenant_a.workorder`. `key` is a header name of your choosing; there is no fixed name. This example has no authentication: notify doesn't force it, and access policy is up to you via the route's JWT, forward_auth or other authentication plugins. The body is kept as-is; using a header template doesn't make the gateway parse a tenant field from it.

- `secret` accepts HS256/384/512; `jwks_url` accepts RS/ES. Configure exactly one; `alg: none` is rejected. Still set `issuer` and `audience` to match how your business issues tokens.
- `token_from` takes the first non-empty token in order, such as `[header, cookie:lg_token]`. If the selected token is invalid the request is rejected; the other source is not tried. URL query tokens are not supported.
- `subject_claim` produces the trusted subscriber identity; `tenant_claim` produces the trusted tenant identity and requires `subject_claim`. When a mapping is configured but the claim is missing, the response is 401. 18-digit numeric IDs keep their precision.
- Subscription identities and template values use letters, digits, underscores and hyphens, at most 128 characters. Usernames with dots, email addresses and the like are not suitable as-is; map them to stable IDs.
- `exp` ends the stream when it passes, even without identity mapping. A JWT without `exp` still verifies, and the connection is bounded only by `max_duration`; issuers should always set an expiry.
- Shared secret references are cached for about a minute and resolved once for concurrent requests, so rotation doesn't take effect immediately. Connections that already passed verification are not re-verified after a key rotation. A rotation plan should define the transition period for old tokens and the maximum connection lifetime.

The business backend should set the `lg_token` cookie on **login and on every renewal**, with the new JWT as its value; updating only localStorage or a `New-Authorization` response header doesn't update the cookie. On logout, delete the cookie with the same Path and Domain. Make the cookie HttpOnly, Secure under production HTTPS, with Expires aligned to the JWT; for same-origin subscriptions, for example, `Path=/events; SameSite=Lax`.

Native EventSource doesn't read localStorage and cannot set arbitrary Authorization headers. Same-origin requests carry cookies whose path matches automatically; when the page and the subscription service have different origins you need `withCredentials: true` and CORS that explicitly allows the origin and credentials. Only cross-site cases require evaluating `SameSite=None; Secure` — a different origin is not necessarily a different site. The cookie must belong to a host the subscription service can receive it on, and browser policies may restrict third-party cookies.

The subscription GET and the automatically generated same-path POST ACK are both protected by the route's authentication. The ACK path must fall within the cookie's Path. Cookie Path limits where it is sent; it is not a permission boundary. HttpOnly stops scripts from reading the cookie but cannot stop XSS from making requests with the existing session.

## 4. Tenant isolation and consumer identity

**Passing authentication doesn't mean messages are isolated.** `subscribe: notify.workorder` is a shared subject that every tenant passing route authentication can subscribe to. Only `notify.{auth.tenant}.workorder` selects the subject per tenant; subscription templates accept only `{auth.tenant}` and `{auth.subscriber}`, and clients cannot change the subscription scope through query or body.

Offline progress, leases and ACK credentials are bound to the subject, subscription namespace, quota group, trusted tenant and subscriber. The same user ID in different tenants consumes independently. **Each identity has a single active session**: a new connection takes over from the old one. With user IDs as identities, a user's tabs or devices take over from each other. If each device must receive independently, have the authentication system provide a verified stable device identity; don't trust device IDs reported by the client.

Shorthand routes count the default connection quota per site: subscriptions on the same site share a default of 100 connections. `notify.sse.tenant` can override the group; the shorthand doesn't accept `notify.sse.tenants`, so per-tenant limits require the full NATS action. A quota group is not a message permission boundary.

## 5. What reliable offline delivery actually guarantees

1. Publishing returns success only after a JetStream PubAck; failures before the gateway must still be retried reliably by the publisher. Link state commits and notification publishing through a reliable mechanism on the business side, whether the state is in a database or KV.
2. A new consumer receives messages from its creation onwards; history before the first subscription is not delivered. Offline messages can be delivered only within the stream retention period, storage capacity and consumer retention period.
3. On every `ready`, first synchronize from the business state source, then process `{sequence, ack_token, payload}` serially. After success, POST `{"ack_token":"..."}` to the same subscription path with `Content-Type: application/json`; only 204 means the ACK request succeeded.
4. Progress lives in a server-side durable consumer; **offline recovery doesn't depend on Last-Event-ID**. Last-Event-ID is not a business processing acknowledgement either.
5. Deliveries may repeat; clients need business idempotency or version checks. JetStream publish deduplication covers only the deduplication window and doesn't guarantee exactly-once business processing.

Retry publishes with the same `Idempotency-Key`, for example `tenant-a:workorder:42`. Without a stable idempotency key, don't assume two HTTP publishes will be treated as one business event. The shorthand's default deduplication window is the smaller of the retention period and 10 minutes; beyond the window duplicates are still possible.

100 different identities have 100 separate consumption progresses; one person's ACK doesn't release messages for others. Native EventSource has no reliable ACK, so an old frontend cannot support offline mode just by changing the URL. See `examples/nats-events/browser-client.js`; Go uses `pkg/eventclient`. Both follow the same protocol, but the browser uses cookies while Go can use the Authorization header.

The default retention is 7 days, configurable from 1 minute to 30 days. Existing streams' retention isn't updated when the shorthand changes; adjust them with NATS administration tools. Recreating a consumer, changing the consuming identity or changing the NATS storage cluster loses the previous progress, so keep a full resynchronization as a fallback.

Each consumer has one unacknowledged message at a time, so single-message HTTP ACK throughput is bound by latency: a 50 ms round trip allows about 20 messages per second in theory, and processing time lowers that. This suits configuration notifications, not high-frequency messaging in the current implementation. Each identity has a durable consumer, so administrators should limit capacity and consumer counts.

A bad message is TERMed for the current consumer and a `delivery-warning` is sent; later messages continue. The original event stays in the stream; there is no automatic dead-letter forwarding. Monitor termination counts and the stream, durable and sequence in the logs.

## 6. Tenant suspension, logout and the IDS boundary

Local JWT verification only confirms the signature and claims; it cannot know about logout, token revocation or tenant suspension. Clearing the cookie doesn't revoke an established SSE either. Existing connections end when the JWT expires, the maximum duration passes or another disconnect condition occurs.

An IDS Provider that uses a cache invalidates it on notification, and `Evaluate` then reads the new state and returns 401/403 explicitly. The framework doesn't assume a cache exists, doesn't force plugins to subscribe, and doesn't turn cache invalidation into revoking long-lived connections.

So "reject new requests immediately after a tenant is suspended" and "stop delivering on existing SSE immediately" are two separate requirements. The latter needs an additional active disconnect or continuous authorization mechanism and cannot be guaranteed by JWTs and IDS cache invalidation alone. Browsers must also handle expired logins: EventSource's error callback has no HTTP status, so check login state through an endpoint before reconnecting rather than reconnecting blindly.

## 7. Multiple nodes, hot reload and troubleshooting

A shared NATS/JetStream supports multiple gateways, and every node must use the same ACK secret. The default random secret suits a single process only; cross-node ACKs return 403. After a process restart old tokens are invalid, and reconnecting redelivers with new tokens. Front proxies should disable SSE buffering and use idle timeouts longer than the heartbeat interval.

Site hot reloads may close connections of the old instance, so clients must reconnect. Online mode may lose signals and should resynchronize fully; reliable mode recovers unacknowledged deliveries and should also synchronize current state. Don't describe hot reload as seamless.

| Symptom | Check first |
|---|---|
| Subscription 401 | Cookie host/Path, whether renewal updates it, JWT exp, key, issuer/audience, missing claims |
| Messages visible across tenants | Still using a fixed subject? Does publishing authorization restrict the target tenant? |
| Messages keep repeating | Is the client ACKing? Is processing longer than ack_wait? Do all nodes share the ACK secret? |
| ACK 403 | Identity/tenant/subject consistency; credentials expired or from another process's secret |
| Tabs disconnect each other | They share one subscription identity |
| No history after a long offline period | Stream retention/capacity, consumer reclamation, changed consuming identity |
| A suspended tenant still receives pushes | Existing long connections aren't revoked by cache invalidation |

## 8. MCP configuration

MCP's `get_config_guide` and `resource://documentation/site-config` read the configuration guide compiled into the binary and don't scan newly added documents. After updating the built-in guide, rebuild and restart the running MCP service.

`enable_jwt_for_site` supports JWKS or a shared secret, cookie sources and identity mapping, but **adds the named JWT middleware to proxy routes only**; it doesn't protect notify publishing, subscriptions or ACKs. For notifications, go through `get_site_config` → `get_config_guide` → `validate_site_config` → `save_site_config`, keep the existing site content and configure auth explicitly on notification routes. "The tool call succeeded" doesn't mean the whole site is protected.

See also: [Event notification and plugin notifications](./event-notification.md), [Reliable delivery protocol](../04-actions/nats-events.md), [JWT authentication fields](../05-middleware/authentication.md).
