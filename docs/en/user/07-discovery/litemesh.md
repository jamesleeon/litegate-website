# Litemesh Service Discovery Integration

LiteGate features native integration with Litemesh, providing significantly lower routing latency and higher cryptographic security compared to traditional poll-based Consul service discovery architectures.

---

## 1. Core Advantages

- **Event-Driven SSE Push**: Powered by standard Server-Sent Events (SSE) streaming connections. When backend services scale or experience outages, LiteGate detects changes within **100ms** (compared to seconds-level latency in polling systems).
- **Zero-Trust Security**: Native, integrated **mTLS (Mutual TLS)** encryption. P2P communications flowing from the ingress gateway down to target pod instances are cryptographically secured and verified.
- **Tenant Isolation**: Enables granular tenant traffic steering and resource scoping mapped to distinct `sid` (Service ID) allocations.

---

## 2. Global Agent Configuration

Register active Litemesh control plane agents globally inside your `config.yaml`:

```yaml
litemesh:
  enabled: true
  address: "http://litemesh-agent:8787"  # Control plane agent endpoint
  mtls: true                             # Enforces full-chain mTLS encryption
  token: "your-auth-token"               # Optional authentication token
```

---

## 3. Binding Upstreams in Route Configurations

To bind routes to Litemesh service catalogs, set `upstream_type` to `litemesh` inside your site configuration:

```yaml
domain: api.cloud.com
routes:
  - name: user-service
    match: 
      path_prefix: "/users"
    action:
      type: proxy
      upstream_type: litemesh
      service_name: "user-api" # Matches the target service registration name
      lb_policy: least_conn    # Least Connections strategy is recommended
```

---

## 4. Gossip Protocols & High Availability

Litemesh agents synchronize cluster state information asynchronously using the peer-to-peer **Gossip Protocol**. 

To guarantee high availability, LiteGate can maintain active tunnels with multiple Litemesh agent nodes simultaneously. If an active discovery agent experiences an outage, LiteGate fails over to sister agents instantly, preventing discovery blackouts.

---

## Further Reading
- [Integrating Consul Catalogs](./consul.md)
- [Deep Dive into mTLS Security Architectures](../../tls_mtls_architecture.md)
- [Implementing Zero-Config Magic Ingress](../09-advanced/magic-ingress.md)
