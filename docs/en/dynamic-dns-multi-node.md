# Internal DNS Publishing - Multi-Node Gateway Support

## 🎯 Design Goal

**Internal clients resolve gateway domains directly to LiteGate's internal IP. When several LiteGate nodes are online, each contributes an A record; a node that goes away drops out automatically.**

Public resolution stays with DDNS (public IP → DNS provider). Internal resolution is handled here:

```text
LiteGate site a.b.com
  ├─ public IP   → DDNS → DNS provider      external clients
  └─ internal IP → LiteMesh KV → LiteDNS    internal clients
```

---

## 🔥 Core Design: Per-Domain LiteMesh KV Keys with a TTL Heartbeat

Every LiteGate node writes one key per domain:

```text
litedns/v1/records/{domain}/{node_id}
```

```text
LiteGate node 1 (192.168.1.100)
    ↓ refresh every 30s
litedns/v1/records/api.example.com/gw-1 → 192.168.1.100

LiteGate node 2 (192.168.1.101)
    ↓ refresh every 30s
litedns/v1/records/api.example.com/gw-2 → 192.168.1.101

LiteDNS:
- watches the litedns/v1/records/ prefix
- aggregates by domain and answers with both A records
- drops an IP once its key expires
```

Value format (identical to LiteDNS `DNSRecordSet`):

```json
{
  "name": "api.example.com",
  "type": "A",
  "values": ["192.168.1.100"],
  "ttl": 30,
  "owner": "gw-1"
}
```

---

## 📋 Workflow

### 1. Node Boot and Domain Enrollment
When LiteGate starts or loads a new site, the domain joins the `DNSUpdater` set and is written to KV immediately. Removing a site deletes its key immediately.

### 2. Heartbeat Renewal
A background goroutine in `internal/certmanager/dns_update.go`:
- **Frequency**: `heartbeat_interval`, 30 seconds by default.
- **Execution**: rewrites every maintained key, refreshing its KV TTL.
- The KV TTL is three heartbeats, so two missed heartbeats are tolerated.

### 3. Eviction
When a node dies its heartbeats stop, LiteMesh deletes the key once the KV TTL expires, and LiteDNS drops the IP on its next full resync (15 seconds by default).

### 4. Graceful Shutdown
A cleanly stopping gateway deletes every key it published; LiteDNS removes the records as soon as it sees the KV events.

---

## 🏗️ Multi-Node Deployment Settings

Every node needs litemesh enabled and the same `key_prefix`:

```yaml
auto_cert:
  dns_update:
    enabled: true
    auto_service_host_sync: true
    ip: ""                             # Leave blank to auto-detect the default-route interface IP
    key_prefix: "litedns/v1/records/"  # Must match LiteDNS litemesh.dns_record_prefix
    node_id: ""                        # Defaults to the hostname
    record_ttl: 30
    heartbeat_interval: 30s
```

`node_id` defaults to the hostname, so a restarted node overwrites its own key instead of leaving a duplicate. Set distinct `node_id` values when running several LiteGate instances on one host.

---

## 💪 Architectural Advantages

### 1. Autonomous Self-Healing
Node dies → heartbeats stop → KV key expires → LiteDNS evicts the IP. No manual intervention.

### 2. Seamless Scaling
A new node joins the domain's A record set as soon as it starts.

### 3. No Extra Moving Parts
No separate DNS management API or API key. LiteGate and LiteDNS only meet in LiteMesh KV, and LiteDNS can run as multiple instances.
