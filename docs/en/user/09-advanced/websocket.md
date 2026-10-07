# WebSocket Proxying

LiteGate provides **native out-of-the-box support** for the WebSocket protocol. When an inbound HTTP request carries connection upgrade headers, LiteGate's reverse proxy automatically detects the payload, performs the protocol handshake, and promotes the connection to a persistent, bidirectional WebSocket channel without requiring complex overrides.

---

## 1. Out-of-the-Box Configuration

Declare a standard `proxy` action matching your routing paths:

```yaml
domain: ws.example.com
routes:
  - name: websocket-streaming
    match:
      path_prefix: /ws
    action:
      type: proxy
      upstream: ["10.0.0.5:8080"]
```

LiteGate automatically intercepts, parses, and promotes the standard hop-by-hop HTTP headers:
- `Connection: Upgrade`
- `Upgrade: websocket`

---

## 2. Advanced Timeout & Streaming Tuning

Because WebSocket channels are designed for long-lived, persistent bidirectional communication, standard HTTP connection timeouts may prematurely terminate inactive streams. To prevent unexpected connection drops under low traffic, optimize the proxy flush parameters:

```yaml
action:
  type: proxy
  upstream: ["10.0.0.5:8080"]
  flush_interval: -1          # Enables real-time streaming buffers (Recommended)
```

Setting `flush_interval: -1` forces LiteGate to bypass local streaming write buffers, immediately flushing frame packets to the network client. This is recommended for real-time messaging, Server-Sent Events (SSE), and terminal sessions.

---

## 3. Secure WebSockets over TLS (WSS)

When a virtual host enables HTTPS (e.g. via `force_https: true` or ACME automation), WebSocket streams automatically inherit the host's TLS session layer. Clients can seamlessly connect using the secure **`wss://`** URI protocol scheme.

---

## 4. Load Balancing & Sticky Session Rules

> [!IMPORTANT]
> **Connection Persistence**: Once a WebSocket connection handshake is accepted, the TCP stream is bound to a single backend upstream instance for its entire lifecycle. Load balancing algorithms (such as round-robin) only apply during the initial handshake phase. If your application logic requires clients to maintain session affinity with specific backends, configure the `ip_hash` balancer strategy on your upstream block.

---

## 5. Troubleshooting & SRE Diagnostics

### Connection terminates immediately after a successful handshake?
- Verify that your downstream backend application correctly accepts and parses the WebSocket handshake request (`Sec-WebSocket-Accept`).
- If you have an intermediate layer-7 reverse proxy (like Nginx or an ALB) in front of LiteGate, ensure it is configured to permit connection upgrades.

### High system memory usage with thousands of active WebSocket streams?
- Each active, persistent WebSocket stream consumes a dedicated goroutine and connection buffer within LiteGate. Ensure your host system kernel file limits (`ulimit -n`) are set to at least `65535` in production. Refer to the [Systemd Service Sandboxing Guide](../10-deployment/systemd.md) to increase daemon limitations.
