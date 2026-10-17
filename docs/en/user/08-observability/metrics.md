# Prometheus Metrics

LiteGate exposes runtime metrics in the Prometheus text format, covering HTTP requests, proxying and upstreams, certificates, configuration reloads, L4 streams, service discovery and security rejections.

## 1. Enabling

```yaml
metrics:
  enabled: true
  port: 9090          # default 9090; the endpoint is always /metrics
  address: 0.0.0.0    # default 127.0.0.1, local scraping only
```

- The command-line flag `-enable-metrics` also enables it, and `-metrics-addr` overrides the listen address.
- By default the listener binds to `127.0.0.1`. When Prometheus runs on another host, set `address` to an internal address or `0.0.0.0` and restrict sources with a firewall. The dedicated metrics port has **no authentication**.
- When the Dashboard is also enabled, `/metrics` on the Dashboard port serves the same metrics behind Dashboard login. That is for people, not for Prometheus scraping.

## 2. Common metrics

The tables list the metrics most useful for troubleshooting and alerting. The authoritative list is the output of `curl http://127.0.0.1:9090/metrics | grep '^# HELP litegate_'`.

### HTTP and proxy

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `litegate_http_requests_total` | Counter | site, method, status | HTTP requests |
| `litegate_http_request_duration_seconds` | Histogram | site, method | Request handling time |
| `litegate_http_requests_in_flight` | Gauge | site | Requests being served |
| `litegate_http_response_bytes_total` | Counter | site | Response bytes |
| `litegate_http_protocol_errors_total` | Counter | — | TLS handshake, HTTP/2 and HTTP/3 protocol errors |
| `litegate_proxy_requests_total` | Counter | site, route, service, method, result | Proxy request results |
| `litegate_proxy_duration_seconds` | Histogram | upstream | Upstream request time |
| `litegate_proxy_upstream_status_total` | Counter | service, status_class | Upstream status classes (2xx/3xx/4xx/5xx) |
| `litegate_proxy_retries_total` | Counter | site, route, reason | Retry attempts |
| `litegate_proxy_retry_budget_exhausted_total` | Counter | site, route | Retries skipped because the global retry budget was exhausted |
| `litegate_proxy_active_tunnels` | Gauge | site, service, route, proto | Active WebSocket/Upgrade tunnels |
| `litegate_proxy_cache_requests_total` | Counter | result | Proxy cache lookups |

### Upstream health and circuit breaking

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `litegate_upstream_health_check_up` | Gauge | target, protocol | Active health check result, 1 healthy / 0 unhealthy |
| `litegate_upstream_ejections_total` | Counter | service | Passive health check ejections |
| `litegate_circuit_breaker_state` | Gauge | instance | 0=Closed, 1=Half-Open, 2=Open |
| `litegate_circuit_breaker_trips_total` | Counter | instance | Times a breaker opened |
| `litegate_discovery_healthy_instances` | Gauge | provider, service | Healthy instances in service discovery |

### Security and admission

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `litegate_requests_rejected_total` | Counter | reason | Requests rejected by security and admission controls |
| `litegate_rate_limited_requests_total` | Counter | route | Requests rejected by rate limiting |
| `litegate_waf_blocked_requests_total` | Counter | rule, source | WAF blocks |
| `litegate_scan_protection_banned_ips` | Gauge | — | IPs currently banned by scan protection |

### Certificates and configuration

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `litegate_tls_cert_expiry_timestamp_seconds` | Gauge | domain, source | Expiry of each loaded certificate (Unix seconds) |
| `litegate_cert_issuance_total` | Counter | type, result | ACME issuance attempts |
| `litegate_config_reload_total` | Counter | source, status | Configuration reloads |
| `litegate_config_last_reload_success_timestamp_seconds` | Gauge | — | Time of the last successful reload |

### L4 streams

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `litegate_stream_connections_total` | Counter | name, proto | Stream connections |
| `litegate_stream_active_sessions` | Gauge | name, proto | Active sessions |
| `litegate_stream_bytes_total` | Counter | name, proto, direction | Bytes transferred |
| `litegate_stream_dial_failures_total` | Counter | — | Upstream dial failures |

### Process

| Metric | Type | Meaning |
|---|---|---|
| `litegate_build_info` | Gauge | Version info with labels version and go_version; value is always 1 |
| `litegate_goroutines_current` | Gauge | Current goroutines |

Further groups exist for IDS (`litegate_ids_*`), Connect (`litegate_connect_*`), the Kubernetes controller (`litegate_kubernetes_*`), the NATS plugin (`litegate_nats_*`), the notify bus (`litegate_notify_*`) and MCP (`litegate_mcp_requests_total`); they carry data only when the feature is enabled. Standard Go runtime and process metrics (`go_*`, `process_*`) are exported too.

## 3. Prometheus scrape config

```yaml
scrape_configs:
  - job_name: 'litegate'
    scrape_interval: 15s
    static_configs:
      - targets: ['gateway-ip:9090']
```

The official Grafana dashboard is [`deploy/grafana/litegate-dashboard.json`](https://github.com/jamesleeon/LiteGate/tree/master/deploy/grafana) in the repository: in Grafana choose Dashboards → New → Import, upload the file and pick your Prometheus data source (Grafana 10 or newer). It filters by `job`, `instance` and `site` and covers overview, HTTP traffic, proxy and upstreams, certificates and DNS, security, proxy cache, streams/SNI/Connect, NATS, and runtime and configuration reloads; panels for unused features stay empty.

The earlier minimal sample [LiteGate_Overview.json](../../prometheus/LiteGate_Overview.json) is still available; new deployments should use the official dashboard.

## 4. Alert examples

```yaml
groups:
  - name: litegate
    rules:
      - alert: LiteGateHighP99
        expr: histogram_quantile(0.99, sum by (le, site) (rate(litegate_http_request_duration_seconds_bucket[5m]))) > 1
        for: 5m
      - alert: LiteGateUpstream5xx
        expr: sum by (service) (rate(litegate_proxy_upstream_status_total{status_class="5xx"}[5m])) > 1
        for: 5m
      - alert: LiteGateCertExpiringSoon
        expr: litegate_tls_cert_expiry_timestamp_seconds - time() < 7 * 86400
      - alert: LiteGateReloadStale
        expr: increase(litegate_config_reload_total{status!="success"}[10m]) > 0
```

`litegate_http_request_duration_seconds` is a histogram: compute percentiles with `histogram_quantile`; there is no `quantile` label. The `status` label of `litegate_config_reload_total` is one of `success`, `error`, `rejected` or `panic`.

## Related

- [Dashboard](dashboard.md)
- [Access log](access-log.md)
- [Trace ID](trace-id.md)
