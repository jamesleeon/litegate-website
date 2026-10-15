# Event notifications and offline delivery

LiteGate's NATS plugin connects to an external NATS server; it does not embed one. Online notifications use Core NATS and SSE, with business-state resynchronization after reconnect. Offline delivery uses JetStream, stable business identity and explicit ACKs. Replay follows consumer state from the first subscription onward.

Use offline: auth.subscriber with an identity established by authentication. Tenant-isolated subjects use {auth.tenant}. Publishing may additionally use body/header/query templates; application authorization must control the publisher's ability to select tenants. Replicas share an ACK key of at least 32 bytes, distinct from the JWT signing key.

IDS NotifySubscriber provides optional online invalidation signals and Resync, not an offline business queue. Applications implement ACK handling, retries and business deduplication according to the actual contract. Delivery is not an exactly-once business-operation guarantee.

## Related documentation and code

- [SSE](../04-actions/nats-sse.md)
- [NATS events](../04-actions/nats-events.md)
- [JWT integration](notify-jwt-integration.md)
