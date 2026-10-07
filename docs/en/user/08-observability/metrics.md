# Prometheus Metrics

LiteGate provides enterprise-grade telemetry support, exposing hundreds of high-precision runtime indicators via standard Prometheus endpoints. Operators can query these metrics to build rich dashboards in Grafana, tracking gateway throughput, latency percentiles, and backend upstreams health.

---

## 1. Configurations

Configure the dedicated telemetry scraper port globally inside `config.yaml`:

```yaml
metrics:
  enabled: true
  port: 9091           # dedicated port for Prometheus scraping; the endpoint is always /metrics
```

---

## 2. Telemetry Dictionary

### L7 HTTP Traffic Metrics
- `litegate_http_requests_total`: Counter tracking total processed requests, labeled by site and routing ID.
- `litegate_http_request_duration_seconds`: Histogram tracking L7 request execution durations.
- `litegate_http_active_connections`: Gauge tracking instant downstream TCP connections.

### Backend & Upstream Health Metrics
- `litegate_upstream_active_instances`: Gauge tracking the number of healthy backend instances.
- `litegate_upstream_down_times_total`: Counter tracking how many times backend instances have been marked unhealthy by health checks.

### System Runtime Metrics
- `litegate_memory_usage_bytes`: Gauge tracking host physical memory consumption.
- `litegate_goroutines_total`: Gauge tracking active Go Goroutines, serving as a key indicator of gateway health.

---

## 3. Prometheus Ingestion

Add a target scraper job to your `prometheus.yml` configuration:

```yaml
scrape_configs:
  - job_name: 'litegate'
    scrape_interval: 10s # Captures transient 5xx spikes
    static_configs:
      - targets: ['gateway-ip:9091']
```

---

## 4. Production SRE Recommendations

1. **High-Frequency Ingestion**: Configure your scraper interval to **10 seconds** to ensure transient HTTP 5xx error spikes or brief connection drops are captured.
2. **Latency Alerts**: Create Prometheus alert rules targeting the P99 latency percentile:
   `litegate_http_request_duration_seconds{quantile="0.99"} > 0.5` (raises alerts if 99% of requests exceed 500ms).
3. **Network Isolation**: The metrics scraper port does not enforce authorization by default. Apply private subnet firewall rules or ACLs to guarantee only authorized Prometheus scraper engines can query the endpoint.
