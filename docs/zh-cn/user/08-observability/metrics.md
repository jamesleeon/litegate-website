# Metrics (监控指标)

LiteGate 内置了企业级监控支持。它通过标准 Prometheus 协议暴露上百个关键运行指标，您可以轻松地通过 Grafana 可视化网关的吞吐量、延迟和健康状况。

---

## 1. 启用配置

在 `config.yaml` 中全局开启 Prometheus 指标抓取端点：

```yaml
metrics:
  enabled: true
  port: 9091           # Prometheus 抓取专用端口;端点固定为 /metrics
```

---

## 2. 核心监控指标 (Metrics Dictionary)

### HTTP 流量指标
- `litegate_http_requests_total`: 每一个 Site/Route 的累计请求计数。
- `litegate_http_request_duration_seconds`: 请求处理延迟分布 (Histogram)。
- `litegate_http_active_connections`: 当前活跃的 TCP 连接数。

### 后端健康指标
- `litegate_upstream_active_instances`: 当前健康的后端实例数量。
- `litegate_upstream_down_times_total`: 某个后端实例被标记为不健康的次数。

### 系统运行指标
- `litegate_memory_usage_bytes`: 网关占用的物理内存。
- `litegate_goroutines_total`: 当前运行的协程总数（系统健康的晴雨表）。

---

## 3. 集成 Prometheus

在您的 `prometheus.yml` 中添加配置：

```yaml
scrape_configs:
  - job_name: 'litegate'
    static_configs:
      - targets: ['gateway-ip:9091']
```

---

## 4. 最佳实践建议

1.  **高频抓取**: 建议设置 `scrape_interval: 10s`，以便捕捉 5xx 突发报错。
2.  **报警配置**: 推荐为 `litegate_http_request_duration_seconds{quantile="0.99"}` 设置阈值告警。
3.  **安全性**: 指标端口默认不带鉴权，请确保此端口仅能由 Prometheus 采集机访问。
