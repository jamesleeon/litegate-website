# Service Registration & Instant Online: End-to-End Automation Verification

## 🎯 Core Concept

The core value of the LiteGate ecosystem lies in: **"Tag-Driven Service Instant-Online Routing."** When a microservice registers with the registry carrying specific metadata tags, LiteGate automatically completes the entire lifecycle—from domain DNS resolution to ACME SSL/HTTPS certificate provisioning—without manual intervention.

Here is the complete automation lifecycle flow:

```
Microservice "payment" registers (carrying the tag "litegate.http.host=payment.company.com")
    ↓
Litemesh registers the instance and persists the metadata states
    ↓
LiteGate monitors mutations in real time via an active SSE (Server-Sent Events) channel
    ↓
LiteGate dynamically compiles a Site configuration in isolated memory
    ↓
CamoDNS Updater registers the domain "payment.company.com" pointing to LiteGate's LAN IP
    ↓
DDNS registers the domain "payment.company.com" pointing to the gateway's public IP
    ↓
Auto-Cert triggers the ACME HTTP-01 challenge pipeline to provision SSL certificates
    ↓
✅ LAN Access: https://payment.company.com (Ready within seconds!)
✅ WAN Access: https://payment.company.com (Ready within minutes due to DNS propagation caches)
```

---

## 📋 Stages Breakdown

### 1. Registering the Microservice to Litemesh

**Service boot registration code example**:

```go
// Register service instance
service := &sdk.ServiceInstance{
    Name:     "payment",
    Addr:     "192.168.1.200",
    Port:     8080,
    Protocol: "http",
    Tags:     []string{
        "litegate.http.host=payment.company.com",  // 🔥 Magic Tag: triggers dynamic gateway provisioning
    },
    Check: &sdk.Check{
        Type:     "http",
        Target:   "http://192.168.1.200:8080/health",
        Interval: "10s",
    },
}
client.Register(service)
```

### 2. Litemesh Event Broadcasting
- Captures the registration request, writing properties to the concentrated key-value storage.
- Synces peer cluster membership states via the Gossip protocol.
- Broadcasts a lightweight `SERVICE_ADDED` notification to all listening gateway nodes via the active SSE channels.

### 3. LiteGate Dynamic Site Compilation
LiteGate's `CatalogLoader` watches for service changes, parsing upstreams carrying the `litegate.http.host` tag:
- **Dynamic Site Provisioning**: Instantiates a routing `Site` in isolated memory, avoiding local disk `yaml` writes.
- **Instant Activation**: Hot-swaps the memory pointer. Traffic arriving at `http://payment.company.com` is now proxyable instantly.

### 4. LAN DNS (LiteDNS) Auto-Syncing
LiteGate invokes the registration worker defined in `internal/certmanager/dns_update.go`:
- Writes the domain and the gateway's internal IP into LiteMesh KV (`litedns/v1/records/{domain}/{node_id}`); LiteDNS picks it up from its watch.
- **Verification**: `dig @litedns payment.company.com` returns the gateway's internal IP.

### 5. DDNS & ACME Certificate Acquisition
- **DDNS**: Automatically maps domain records to public DNS service providers (e.g., Alibaba Cloud DNS).
- **ACME**: The certificate manager discovers the new domain and launches the certificate acquisition flow. Since DNS records are active, the HTTP-01 ACME challenge validates successfully.

---

## ⏱️ Expected Timelines

| Timeframe | Event | Status |
| :--- | :--- | :--- |
| **T + 0s** | SDK completes microservice registration | 🚀 Bootstrapped |
| **T + 0.5s** | LiteGate swaps the memory routing pointer | 🌐 LAN HTTP active |
| **T + 1s** | LAN DNS propagation completes | 📡 Domain ready |
| **T + 60s** | SSL certificate acquired and sync completes | 🔒 HTTPS live cluster-wide |

---

## 🎯 High-Availability Design Highlights

1. **Decoupled Governance**: Microservice developers focus solely on domain registrations; gateway engineering details remain fully abstracted.
2. **Resilience**: If a LiteGate node crashes, CamoDNS automatically redirects clients to alternate healthy gateway peers via active heartbeat sweeps.
3. **Zero Configuration Operations**: Routing, DNS, and SSL handshakes are handled automatically, realising a true **"Architecture as Operations"** platform.

---

## ⚡ Related Deep-Dives

- [Litemesh + LiteGate Best Practices](./litemesh_integration.md)
