# NATS capabilities and responsibility boundaries

| Requirement | Mechanism and boundary |
|---|---|
| HTTP publishing | publish / NATS Action; route configuration owns authorization |
| HTTP request/reply | request_reply; requires the business consumer protocol |
| Online SSE | subscribe / Core NATS; resynchronize state after disconnect |
| Offline events | JetStream, trusted subscriber and ACKs; consumer state binds identity |
| Tenant subjects | Subscriptions accept trusted auth templates; publish variables need authorization |
| Replica ACKs | Shared ACK key of at least 32 bytes |
| IDS notifications | Optional online signals + Resync, not an offline queue |

The gateway does not embed NATS Server, implement application transactions or guarantee exactly-once business operations. Default single-message in-flight ACKs, buffer limits and slow-client disconnection affect throughput. Use current Action/SSE documents for parameters/error codes rather than an old sidecar design.

## Related documentation and code

- [Deployment](nats_deployment_guide.md)
- [NATS events](user/04-actions/nats-events.md)
- [SSE](user/04-actions/nats-sse.md)
- [JWT](user/09-advanced/notify-jwt-integration.md)
