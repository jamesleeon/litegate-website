# Durable events (persistence, offline replay and application ACK)

Configuration can live in any database, KV store, Redis or HTTP service. The owner commits changes and reliably publishes events; LiteGate handles JetStream storage, independent offline progress, SSE delivery and application acknowledgments. LiteGate does not access your configuration store.

The payload is any UTF-8 text or JSON chosen by the publisher; the gateway does not interpret it. The example below carries an event ID and an opaque version. Keep the same event ID and HTTP Idempotency-Key when retrying the same change. Publishing deduplication is bounded by the stream duplicate window; consumers must be idempotent.

```json
{"event_id":"tenant-a:routing:42","tenant_id":"tenant-a","type":"tenant.disabled","version":"42"}
```

## Shared configuration

```yaml
plugins:
  nats:
    connections:
      default:
        servers: nats://127.0.0.1:4222
shared:
  event_ack_secret: "${EVENT_ACK_SECRET}"
```

ACK signing requires at least 32 bytes and the same secret on every gateway. Never expose it to clients. The NATS plugin must be linked. Cache invalidation for IDS and other plugins does not use durable delivery: plugins declare their own subjects and receive them from the notify bus (see the plugin notifications section of the Chinese event-notification guide, docs/zh-cn/user/09-advanced/event-notification.md).

## Routes

Protect publication, subscription and ACK routes with authentication and authorization. The static `tenant: config` below is only a quota label: this route exposes all config.changed events to its authorized management clients. Use authenticated tenant templates and tenant allowlists from the SSE guide when partitioning events by tenant.

```yaml
site: events.example.com
routes:
  - match:
      path: /config/publish
      method: [POST]
    action:
      type: nats
      mode: jetstream_publish
      subject: config.changed
      stream:
        name: CONFIG_EVENTS
        create_if_absent:
          subjects: [config.changed]
          retention: limits
          storage: file
          max_age: 72h
          duplicates: 30m
          replicas: 1
  - match:
      path: /config/events
    action:
      type: nats
      mode: jetstream_subscribe
      subject: config.changed
      stream:
        name: CONFIG_EVENTS
      sse:
        tenant: config
        max_connections: 100
      reliable:
        subscription: config-updates
        consumer_from: auth.subscriber
        ack_secret_ref: shared.event_ack_secret
        ack_wait: 1m
  - match:
      path: /config/ack
    action:
      type: nats
      mode: jetstream_ack
      subject: config.changed
      stream:
        name: CONFIG_EVENTS
      sse:
        tenant: config
      reliable:
        subscription: config-updates
        consumer_from: auth.subscriber
        ack_secret_ref: shared.event_ack_secret
        ack_wait: 1m
```

Precreate the stream before the first subscription; fallback creation happens only during publication. Reliable consumption requires file storage and LimitsPolicy; use three replicas in production clusters and bound stream storage/consumer counts. One client's ACK advances only its consumer, leaving other subscribers' events available. Default nats_headers publishing keeps the body unchanged.

auth.subscriber requires verified X-Lito-Subscriber injected by authentication/IDS, not a query parameter or client header. Inbound identity headers are stripped; allowlist X-Lito-Subscriber in IDS header projection. Each independent application instance/device/tab needs a different stable identity. New authenticated sessions take over; old sessions close on failed renewal, normally within 5 seconds. A fixed consumer can replace consumer_from on a separately authorized single-subscriber route. Subscription and ACK configurations must agree. Namespace, tenant, subject and identity determine the hashed durable name; changing these creates new progress.

## Client protocol

Every connection begins with a ready event containing resync_required=true. Refresh current state before processing deliveries, covering lost volatile caches, removed consumers and expired history. A message wraps the original payload with sequence, redelivered and ack_token. After successfully refreshing configuration or invalidating caches, POST `{"ack_token":"signed-proof"}` to the ACK route with application/json. HTTP 204 confirms acknowledgment. Failed processing does not ACK, and messages can be redelivered.

Tokens are bound to the subscriber, tenant, stream and subject; they expire after twice ack_wait. ACK can reach another gateway. Each consumer allows one unacknowledged message; processing should finish within ack_wait. Last-Event-ID represents reception and is intentionally not trusted as processing progress. Invalid UTF-8, oversized data or frames exceeding the buffer are terminated for this consumer (TERM); delivery-warning reports the skipped event and the connection continues. LimitsPolicy retains original messages for other consumers and inspection. litegate_nats_terminated_events_total and logs identify stream, durable, sequence and reason. Dead-letter forwarding is not automatic. Online core subscribe instead discards invalid messages.

Go clients can use pkg/eventclient.Client with Resync and Handle callbacks; it reconnects and ACKs only after successful processing. Headers apply to both endpoints. Avoid a whole-request HTTP timeout on SSE. The [browser example](https://github.com/jamesleeon/LiteGate/blob/master/examples/nats-events/browser-client.js) uses Cookie authentication, serial processing and explicit ACK. Native EventSource cannot set custom Authorization headers; configure cross-origin credentials/CORS when needed. Applications handle login redirects on authentication failure.

## Lifecycle and recovery

SSE admission quotas span action generations within one process, not all gateway processes. Reload closes old HTTP streams but retains durable progress; reconnect delays are randomized to 2–8 seconds. A distributed lease prevents two gateways splitting one subscriber's deliveries. LITEGATE_EVENT_LEASES is a separate JetStream KV bucket, not configuration storage, with 15s TTL and 5s renewal. Its initial replicas match the event stream; administrators manage existing bucket replicas. SSE connections take over authenticated identities immediately; old sessions NAK pending messages when stopped. Crashed sessions may leave deliveries waiting for ack_wait. Lease loss stops consumption.

All nodes must reach the same lease bucket and have permissions for consumer management, lease KV and ACK. Monitor storage retention, consumer backlog and listener errors. Inactive consumers expire according to offline_retention. Recovery always reloads current configuration; retained history is not infinite.


## Lifecycle and capacity

New durable consumers use DeliverNew and receive only events after creation. Every connection first resynchronizes current configuration. Existing consumers retain delivery policy and acknowledged progress.

reliable.offline_retention defaults to 168h (7 days), configurable from 1m to 720h (30 days). This bounds inactive consumer lifetime; stream MaxAge and capacity independently bound replayable events. Expired consumers are recreated with full resynchronization. Configure stream MaxConsumers to bound identity growth. AckWait, MaxDeliver and InactiveThreshold update in place; incompatible FilterSubject/AckPolicy still fail.

Static tenant plus static consumer means one shared recipient: new connections replace old ones. Use only for an independently authorized single recipient; multi-user broadcasts need verified consumer_from identities.

MaxAckPending=1 and one HTTP ACK per event limit throughput to processing time plus RTT (about 20 events/second at 50ms RTT). This suits configuration notifications. Larger windows and batch ACK are not implemented.
