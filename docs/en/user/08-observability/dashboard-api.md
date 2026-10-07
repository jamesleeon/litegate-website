# Dashboard REST API Reference

The LiteGate administrative console exposes a comprehensive RESTful HTTP API, enabling external DevOps scripts, monitoring collectors, and automated tools to query gateway health, hot-reload configurations, and retrieve telemetry payloads programmatically.

---

## 1. Connection & Authentication

- **Default Endpoint**: `http://localhost:9999`
- **Authentication Handshakes**: Supported via two authentication schemes:
  - **Session Cookies**: Authenticate via `POST /login` supplying `username` and `password` to receive a secure session cookie.
  - **API Token Headers**: Send raw credentials by attaching the HTTP header: `X-API-Key: <token>` (globally configured under `dashboard.token` in `config.yaml`).

> [!IMPORTANT]
> **Strict Local Binding**: Never expose the administrative API dashboard port directly to the public internet. Ensure the port binds exclusively to `127.0.0.1` or is reachable solely via secure VPN/private subnet gateways.

---

## 2. Gateway Status & Telemetry

### Query System Metrics Overview
```http
GET /status/json
```
The `discovery_providers` field lists external Discovery Provider plugin instances that loaded successfully:

```json
{
  "discovery_providers": [{
    "provider": "my_registry",
    "instance": "registry-east",
    "display_name": "My Registry",
    "active": true,
    "state": "active",
    "watch_state": "watching",
    "last_success": "2026-09-05T01:20:00Z",
    "failure_count": 0,
    "supports_watch": true,
    "supports_namespace": true,
    "supports_tags": true,
    "supports_metadata": true
  }]
}
```

This is a non-sensitive runtime inventory; `service_discovery.catalogs[].config` is never returned.

`compiled_plugins` lists every external plugin component registered in the binary, including `kind`,
`name`, `version`, `api_version`, `description`, `capabilities`, `config_example`, `has_manifest`, and
`compatible`. It is separate from runtime discovery health, so compiled plugins appear even when they
are not selected by configuration. `config_example` comes from the plugin manifest and must contain only
public placeholder values, never tokens, passwords, or real credentials.

*Response Payload Example*:
```json
{
  "uptime": "72h15m",
  "goroutines": 128,
  "memory_mb": 45.2,
  "sites_count": 12,
  "streams_count": 3,
  "total_requests": 1523400,
  "qps": 125.5
}
```

### Query Live Telemetry Metrics
```http
GET /api/v1/realtime
```
* Returns live traffic logs containing instant RPS, request duration percentiles, and HTTP error rate vectors.

---

## 3. L7 Site Router Configurations

### List Active Site Configurations
```http
GET /api/v1/sites
```
* Returns an absolute JSON snapshot of all active L7 sites currently loaded in memory, including mapped routes, upstreams, and request counters.

### Query Target Site Parameters
```http
GET /api/v1/sites/{domain}
```

### Hot-Reload / Dynamically Create Site
```http
PUT /api/v1/sites/{domain}
Content-Type: application/json

{
  "domain": "new-site.com",
  "routes": [...]
}
```
* Instructs the gateway to hot-load new parameters. Changes take effect across connections instantly.

---

## 4. L4 Stream Routers

### List Active L4 Streams
```http
GET /api/v1/streams
```
* Returns a snapshot mapping all active Layer 4 TCP/UDP stream proxy handlers, tracking current concurrent connections and bandwidth metrics.

---

## 5. Microservice Discovery Catalogs

### List Discovered Service Instances
```http
GET /api/v1/discovery
```
* Returns a structured snapshot of active microservice backends and physical pod instances synchronized from Consul catalogs and Litemesh grids.

---

## 6. TLS Certificates Management

### List Bound TLS Certificates
```http
GET /api/v1/certs
```
* Lists all managed SSL/TLS certificates, tracking hostname matches, expiration countdowns, and sourcing pathways (Auto-Cert or Manual).

---

## 7. Operational Logs

### Query Log Buffer Tail
```http
GET /api/v1/logs/recent
```
* Returns the most recent 5 access log entries retained inside the gateway's localized memory ring buffer.

---

## 8. Global Ingress Configurations

### Query Global Ingress Config File
```http
GET /api/v1/config
```

### Force Hot-Reload
```http
POST /api/v1/reload
```
* Immediately triggers a hot-reload sweep, scanning files on disk to apply configuration deltas without downtime.

---

## 9. Native Prometheus Metrics Ingestion

A dedicated high-performance metrics scraper port (defaulting to `:9090` in `config.yaml`):

```http
GET /metrics
```

### Core Prometheus Metrics Reference:

| Metric Parameter | Type | Description |
| :--- | :--- | :--- |
| `litegate_http_requests_total` | Counter | Cumulative HTTP request processing counter. |
| `litegate_http_request_duration_seconds` | Histogram | Request processing latency distribution percentile tracking. |
| `litegate_active_connections` | Gauge | Instant count of active downstream TCP connections. |
| `litegate_upstream_health` | Gauge | Instant status of backend pod health checks. |
