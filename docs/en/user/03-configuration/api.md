# Management Endpoints Overview

LiteGate's management and observability endpoints live on separate ports, each enabled on its own.

| Endpoint | Config | Default listen | Authentication | Docs |
|---|---|---|---|---|
| Dashboard and management API | `dashboard` | `:9999` (all interfaces) | `X-API-Key` or login cookie | [Dashboard API](../08-observability/dashboard-api.md) |
| Prometheus metrics | `metrics` | `127.0.0.1:9090` | none | [Metrics](../08-observability/metrics.md) |
| MCP (SSE) | `mcp` | set by `port` | `token` (Bearer) | [MCP capability matrix](../../litegate_mcp_capability_matrix.md) |
| pprof | `pprof` | `127.0.0.1:6060` | none | [Debugging](../11-troubleshooting/debugging.md) |

The gateway's traffic ports also serve `/healthz` and `/readyz` for load balancers and Kubernetes probes.

## Security

- The Dashboard listens on all interfaces by default. Always set a strong password and `token`, and restrict sources with a firewall or a fronting gateway.
- The metrics and pprof ports have no authentication; open them only to scrapers or the operations network.
- Prefer `X-API-Key` for automation instead of storing the login password in scripts.
