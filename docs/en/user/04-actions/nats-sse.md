# NATS live event subscriptions

Use `type: nats`, `mode: subscribe` to stream Core NATS messages to browsers over SSE. LiteGate reuses managed NATS connections and opens a normal subscription for each HTTP client. Gateways connected to the same NATS cluster receive broadcast copies; no queue group divides events between nodes.

This is online notification delivery, **without persistence, replay, client acknowledgments or Mercure protocol compatibility**. It emits no event IDs and does not replay `Last-Event-ID`. Refresh application state after reconnecting. Gateways must connect to the same or interconnected NATS network; installing the plugin alone does not form a cluster.

## Connection and route

Configure the existing shared NATS connection:

```yaml
plugins:
  nats:
    connections:
      default:
        servers: "nats://127.0.0.1:4222"
        connect_timeout: "3s"
        reconnect_wait: "1s"
        max_reconnects: "-1"
```

Use credentials and TLS in production. This static route exposes the topic to every caller allowed to access the route. `tenant: demo` is an operator-defined quota/metrics group, not authentication; protect private events with gateway authentication middleware.

```yaml
site: events.example.com
routes:
  - match:
      path: /events
    action:
      type: nats
      mode: subscribe
      subject: events.demo
      sse:
        tenant: demo
        max_connections: 100
        buffer_messages: 64
        buffer_bytes: 262144
        max_event_bytes: 65536
        heartbeat: 15s
        write_timeout: 5s
        max_duration: 15m
```

Publish with `nats pub events.demo '{"status":"ready"}'`, then subscribe:

```javascript
const events = new EventSource('/events');
events.onmessage = event => console.log(event.data);
events.onerror = () => { /* Refresh current state through the application API. */ };
// Call events.close() when no longer needed.
```

Only GET is accepted; other methods return 405. UTF-8 text and JSON become `message` events with each line prefixed by `data:`. Binary or oversized payloads are discarded and counted without closing streams. Encode binary data as text before publishing.

## Authenticated tenant isolation

Configure authentication middleware to provide a gateway-verified tenant, then use an explicit allowlist and tenant-bound subject template:

```yaml
site: events.example.com
routes:
  - match:
      path: /events
    action:
      type: nats
      mode: subscribe
      subject_template: events.{auth.tenant}.orders
      sse:
        tenants: [team_a, team_b]
        max_connections: 100
```

Missing or unlisted identities return 403. Query parameters cannot change the tenant. Use exactly one of `tenant` (static subject) or `tenants` (verified tenant template). Subscription templates only allow `{auth.tenant}`; client field templates, `subject_from` and subject wildcards are rejected.

Native `EventSource` cannot set arbitrary Authorization headers. Use an existing cookie session, and configure credentialed CORS if crossing origins. Clients must not set internal identity verification headers themselves. Connections expire after `max_duration` and authenticate again on reconnect; identity revocation is not applied immediately to existing streams.

## Bounds and lifecycle

Defaults: 100 connections per tenant, 64 buffered events, 256 KiB buffered bytes, 64 KiB per input event, 15s heartbeat, 5s write timeout and 15m maximum duration. Limits are local to one gateway action instance and scoped by connection name plus tenant. Routes sharing a tenant should use the same connection limit. There is also a 10000-connection total cap; authenticated allowlists contain at most 256 tenants.

`buffer_bytes` includes the event currently being written. SSE line prefixes increase encoded size. The NATS subscription has separate pending message/byte limits matching the configured buffer limits. Overflow disconnects slow subscribers rather than blocking others or growing memory indefinitely. Write deadlines interrupt stalled clients; shutdown cancels streams, removes subscriptions, frees quotas and refuses new subscriptions.

Heartbeat must be 1s..1m, write timeout at most 1m, and maximum duration at most 24h. NATS outages, detected reconnects and dropped subscription messages end streams at the heartbeat check. Browser reconnects must refresh state because Core NATS cannot fill delivery gaps.

SSE bypasses response compression and sends `X-Accel-Buffering: no`. Disable buffering in upstream proxies and set idle timeouts longer than the heartbeat. Avoid response caching or whole-response transformations on event routes. Flushing HTTP data is not a browser application acknowledgment.

## Metrics

`litegate_nats_sse_connections`, `litegate_nats_sse_messages_total`, `litegate_nats_sse_bytes_total` and `litegate_nats_sse_disconnects_total` use configuration-bounded `connection` and `tenant` labels. Disconnects include a bounded `reason` label for rejection, slow consumption, write errors, NATS availability, duration expiry and shutdown.

Historical delivery requires a separate JetStream consumer and persistent event cursor design. Adding SSE IDs alone does not make Core NATS durable.

## Reloads and invalid events

Any configuration reload creates a new action generation; delayed cleanup normally closes old SSE streams after 15 seconds. Events during reconnect may be lost; refresh application state. Each connection sends a random retry of 2000–8000 milliseconds. Streams are not retained across generations, and admission quotas are shared across generations within one process.

Buffer bytes count encoded SSE frames. A single frame exceeding the entire budget is discarded as input error; accumulated backlog still disconnects slow clients. `litegate_nats_sse_dropped_events_total` counts discards per subscriber with reason invalid_payload or frame_too_large. Empty payloads retain a data field and deliver an empty string event. Conflicting tenant quotas across routes return HTTP 500 at request time; cross-route load validation is not implemented.


For offline replay, application ACK and IDS invalidation, see [Durable configuration events](nats-events.md).
