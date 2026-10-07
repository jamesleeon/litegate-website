# Web Dashboard

LiteGate includes an integrated, real-time **Web Dashboard**, providing system administrators and SRE teams with a visual console to monitor gateway metrics, hot-reload site configurations, and analyze traffic logs directly in standard web browsers.

---

## 1. Activation & Settings

Configure the Dashboard port and Bcrypt credentials globally inside `config.yaml`:

```yaml
dashboard:
  enabled: true
  port: 9999           # Ingress port for dashboard access
  username: "admin"
  password: "$2a$..."  # Cryptographic password hash generated via Bcrypt
```

---

## 2. Core Functional Modules

### Real-Time Telemetry (`Status`)
- **System Metrics**: Host CPU load, physical memory footprint, active Go Goroutines, and garbage collection metrics.
- **Traffic Overview**: Real-time RPS (Requests Per Second), total accumulated request counts, and active concurrent TCP connections.
- **SSL/TLS Auditing**: Visual countdowns and alerts tracking TLS certificate expiration dates for all bound domain names.

### Ingress Site Management (`Sites`)
- **Hot-Reload Editor**: Modify L7 site YAML routing rules directly inside the browser editor; changes take effect instantly across the gateway cluster without restarting.
- **Site Diagnostics**: Real-time HTTP error rates (5xx counts) and request processing latencies (latency percentile tracking) per host domain.

### Service Discovery Catalog (`Discovery`)
- View active upstreams and discoverable endpoints from Litemesh, LiteDeploy, Docker, Consul, Kubernetes, Discovery Agent, and external Discovery Provider plugins.
- Audit active target pod IP bindings mapped behind L7 routing rules.
- The Control Plane Providers section creates one card for every successfully loaded Discovery Provider plugin instance and shows its Watch/Namespace/Tags/Metadata capabilities. Provider configuration and secrets are never included in dashboard status data.

### Compiled Plugins
- Lists Action, Middleware, LoadBalancer, KV, DNS, IDS, and Discovery plugins actually registered in the running binary.
- Shows registration name, kind, version, public API version, and capabilities. Legacy plugins without a manifest are marked as compatibility unknown.
- When a manifest supplies `ConfigExample`, its card shows the description plus an expandable, copyable setup snippet. Official plugins such as NATS, OpenAPI MD5 and forward proxy provide configuration references.
- This inventory means “compiled and registered”; Discovery Provider connection health remains visible under Control Plane Providers and Discovery Mesh.

### Connect Network
- Shows each peer's online sessions, registration generation, active connections, and published hostnames.
- CLI HTTP hostnames report **Registration** and **Cloud TLS** separately, so an accepted registration is not mistaken for working public HTTPS.
- Cloud TLS reports `ready`, `eligible`, `issuing`, `failed`, or `missing`, with exact/wildcard coverage, source, ACME challenge, expiry, and failure details where available.
- Full Connect Sites terminate TLS on Home. Cloud TLS status applies only to hostnames published with `litegate connect http`.

### Telemetry Stream (`Logs`)
- Real-time access log tails.
- Integrated search filters to trace and locate specific error payloads.

---

## 3. Production Security Hardening

> [!WARNING]
> **Dashboard Security Hardening Guidelines**:
> 1. **Deactivate Defaults**: Change the default `admin` username.
> 2. **Strong Bcrypt Pacing**: Ensure the password uses a strong Bcrypt hash with high computational costs.
> 3. **Firewall Limits**: Restrict ingress access to the Dashboard port to specific administrative IP ranges (e.g., nesting an `ip_restriction` check on the dashboard routing table).
> 4. **Protect diagnostic details**: Connect Cloud TLS failures include original ACME errors that may contain internal hostnames, provider details, or network information. Do not expose the Dashboard or its status endpoint to untrusted users.

---

## Further Reading
- [How to Generate Password Hashes](../../user/01-getting-started/installation.md#命令行参数)
- [Prometheus Ingestion Specifications](./metrics.md)
- [Publish an HTTP Service with the CLI](../09-advanced/connect-cli-http.md)
