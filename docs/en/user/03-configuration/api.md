# Control API Reference

LiteGate provides an HTTP-based administration and control API, allowing you to programmatically inspect the gateway state, gather telemetry indicators, and dynamically tweak active operational parameters. By default, the administrative API runs on the same port as the Admin Dashboard.

---

## 1. Basic Inbound Information

- **Default Address**: `http://localhost:9999`
- **Authentication**: Unless explicitly deactivated in the global configuration, the API strictly enforces Basic Auth using the Dashboard's `username/password` credentials.

---

## 2. Dynamic Endpoints

### Retrieve Gateway Status
- **Endpoint**: `GET /status/json`
- **Payload Response**: Returns active uptime, memory allocations, running goroutine count, and loaded routing statistics.

### Fetch Active Site Map Configurations
- **Endpoint**: `GET /api/v1/sites`
- **Payload Response**: Captures a real-time configuration snapshot of all active routing entries residing in-memory.

### Retrieve Service Discovery Details
- **Endpoint**: `GET /api/v1/discovery`
- **Payload Response**: Lists all registered backend nodes synchronized from active Consul or Litemesh meshes.

---

## 3. Telemetry Indicators (Metrics)

LiteGate contains a built-in Prometheus metric scrape endpoint.

- **Endpoint**: `GET /metrics` (Typically exposed on a dedicated telemetry port: `9091`)
- **Key Indicators**:
  - `litegate_http_requests_total`: Cumulative counter of all processed HTTP requests.
  - `litegate_http_request_duration_seconds`: Histogram distribution of request latency.

---

## 4. Hot Tweaking (Rate Limits / Switchers)

Certain middlewares support dynamic bypass adjustments via API calls, bypassing the need to persist updates into YAML site definitions. For integration specs, refer to specific middleware manuals.

---

## Operational Security Guidelines

- **Isolate the Admin Endpoint**: We strongly recommend binding the administration interface strictly to `127.0.0.1` or protecting access behind a secure VPN gateway.
- **Enforce Strong Credentials**: The API shares authentication hashes with the Dashboard, utilizing strong Bcrypt cryptographical validation.
