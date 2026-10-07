# Consul Service Discovery Integration

LiteGate supports integrating HashiCorp Consul as an upstream service catalog provider. The gateway periodically synchronizes active instances registered under the Consul Catalog, dynamically adjusting active load-balancing pools based on Consul health check states.

---

## 1. Global Activation

Configure your Consul agent connections globally in `config.yaml`:

```yaml
service_discovery:
  catalogs:
    - enabled: true
      provider: "consul"
      url: "http://127.0.0.1:8500" # Typically targets the local Consul Agent
      token: "ACL-TOKEN-HERE"      # Mandated if ACL rules are active
```

---

## 2. Binding Upstreams in Route Configurations

Once defined globally, reference active Consul services in any route using `upstream_type: consul`:

```yaml
domain: api.example.com
routes:
  - name: user-service-route
    match: 
      path_prefix: "/users"
    action:
      type: proxy
      upstream_type: consul
      service_name: "user-api" # Matches the Consul Catalog service identifier
      lb_policy: round_robin
```

---

## 3. Dynamic Health Checking & Evictions

To safeguard traffic, LiteGate exclusively routes requests to Consul service instances marked in a **Passing** health state:
- **Periodic Syncing**: The gateway polls the catalog agent every **5 seconds** (interval is configurable) to perform delta instance evaluations.
- **Failover Eviction**: If an instance shifts to a **Critical** state in Consul, LiteGate evicts it from the active load-balancer target list during the subsequent synchronization loop.

---

## 4. Architectural Comparison: Consul vs. Litemesh

| Capability | Consul Catalog | Litemesh Mesh |
| :--- | :--- | :--- |
| **Sync Mechanism** | Pull-Based Polling | Event-Driven Push (Server-Sent Events) |
| **Latency Threshold** | Seconds (1s to 5s) | Milliseconds (< 500ms) |
| **Tenant Isolation** | Consul Namespace namespaces | Tenant Steering (via SID/Env tags) |
| **Primary Scope** | Legacy Microservice Networks | Modern Cloud-Native Zero-Trust Meshes |

---

## Further Reading
- [Integrating Litemesh Service Discoveries](./litemesh.md)
- [Understanding Load Balancing Policies](../02-concepts/actions.md#负载均衡协议)
