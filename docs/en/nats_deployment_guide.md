# NATS integration deployment

Deploy the external NATS server, LiteGate NATS plugin configuration, then business consumers. Core NATS handles online publishing/subscription. Offline events need JetStream storage and business ACKs. NATS owns transport, the gateway owns HTTP entry and consumers own business processing.

plugin_config selects plugin.yaml; configure connections under plugins.nats.connections. Site publish/subscribe or explicit NATS actions use those connections and authenticated tenant subjects. request_reply without consumers may return no_responders; unavailable indicates a connection problem, requiring a different diagnosis.

Pin actual deployment versions/artifacts instead of copying unverified latest version claims. Restrict credentials and monitoring ports. Test connectivity, request/reply, then SSE and ACK reconnection. Specialized guides define protocols, buffering/slow-consumer behavior and offline guarantees.

```yaml
plugin_config:
  path: plugin.yaml
  watch: true
```

```yaml
plugins:
  nats:
    connections:
      default:
        servers: nats://127.0.0.1:4222
```

```yaml
site: events.example.com
/events:
  subscribe: notify.orders
```

## Related documentation and code

- [Events contract](user/04-actions/nats-events.md)
- [SSE](user/04-actions/nats-sse.md)
- [Examples](../../examples/nats-events/demo/README.md)
