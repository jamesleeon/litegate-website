# LiteGate + Litemesh Integration Guide

The **LiteGate + Litemesh** suite is a high-performance, lightweight, and cloud-native microservice API gateway solution. By integrating with Litemesh, LiteGate eliminates its heavy dependency on external service discovery clusters like Consul, providing out-of-the-box distributed service discovery, dynamic configuration hot-reloads, and concentrated SSL certificate storage.

---

## 1. Why Litemesh?

By deploying Litemesh Agent instead of traditional Consul registries, LiteGate realizes key benefits:

- **Simplified Architecture**: Eliminates the operational overhead of managing, deploying, and monitoring heavy Consul KV clusters.
- **Protocol Optimization**: The Litemesh Agent and gateway core align transport protocol bindings at the lowest layers, yielding higher network throughput.
- **One-Stop Governance**: Consolidates service discovery, routing configurations, and SSL certificates into a single unified distributed database interface.
- **State-of-the-Art Cloud-Native Onboarding**: Supports stateless and diskless mode booting, syncing local parameters to cluster nodes instantly.

---

## 2. Gateway Configuration (`config.yaml`)

To enable Litemesh engines and disable Consul discovery, verify that your master `config.yaml` includes the following configuration blocks:

```yaml
# 1. Disable Consul Discovery
consul:
  enabled: false

# 2. Enable Litemesh Distributed Engine
litemesh:
  enabled: true
  address: "127.0.0.1:8787" # Local Litemesh Agent socket address
  roles:
    config_watch: true       # Monitors KV paths for dynamic reloads
    cert_storage: true       # Syncs and encrypts acquired ACME certs
    service_register: true   # Registers gateway health and endpoints
  keys:
    config_prefix: "litegate/config/sites/"
    stream_prefix: "litegate/config/streams/"
    cert_prefix: "litegate/certs/"
```

---

## 3. Workflow: "One-Click Cloud Syncing" (Sync)

If you have already configured local `config.yaml` parameters and wish to migrate to a distributed Litemesh environment:

**Run the following command:**
```powershell
.\litegate.exe -config config.yaml -litemesh-addr 127.0.0.1:8787 -sync-litemesh
```

**What it does behind the scenes:**
1. LiteGate boots up and parses your local `config.yaml`.
2. Connects to Litemesh KV storage, uploading compiled configurations (default Key: `litegate/config/main`).
3. **Success!** Since your configurations are safely stored in Litemesh, you can now permanently delete local files and boot in stateless mode.

---

## 4. Workflow: "Cloud-Native Diskless Booting" (Bootstrap)

Once your configurations are synced to Litemesh, LiteGate **bypasses local physical files at boot time** (entering stateless/diskless mode), which is perfect for dynamic scaling environments like Docker or Kubernetes.

**Boot Command:**
```powershell
.\litegate.exe -litemesh-addr 127.0.0.1:8787
```

**Gateway Boot Stages:**
1. LiteGate connects to the specified Litemesh Agent port in a zero-config state.
2. Automatically pulls bootstrap variables from `litegate/config/main` to initialize system engines.
3. **Auto-Discovery**: Registers the active node IP and health properties under the service mesh.
4. **Auto-Cert**: The built-in ACME client checks SSL requirements, securely storing renewed certificates inside Litemesh KV.
5. **Live Watching**: Utilizes active Server-Sent Events (SSE) channels to detect routing tag mutations under the `litegate/config/sites/` prefix. Swaps routing pointers in memory in milliseconds without interrupting active TCP streams.

---

## 5. Distributed Core Features

### A. Automatic Service Discovery
Upon booting, the gateway automatically registers itself under Litemesh using a configured identifier (default: `litegate`):
- **UI Dashboard**: Nodes are searchable and visible under Litemesh dashboard's "Services" tab.
- **Active Probes**: Serves endpoint health check probes under `http://<node-IP>:<port>/health`.

### B. Concentrated Certificate Sharing
When `cert_storage: true` is configured across the cluster:
- **Central Storage**: SSL certificates acquired by the built-in ACME manager are stored securely inside Litemesh under `litegate/certs/`.
- **Zero-Cost Peer Sharing**: When Node A acquires a certificate for `example.com`, Node B detects the event via KV subscription and loads the certificate immediately, **avoiding duplicate ACME requests** to Let's Encrypt and preventing rate limit blocks.
- **Cluster Jitter Shield**: Solves the classic problem where isolated nodes concurrently request SSL certificates, causing domain bans by cert providers.

### C. Millisecond Hot Reloading
When `config_watch: true` is enabled:
- Operators create or modify route metadata tags under the `litegate/config/sites/` namespace.
- LiteGate listens via highly optimized SSE streams. Routing trees compile and swap in-memory within milliseconds **without dropping existing TCP connections**.
