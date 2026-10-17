# Metrics (监控指标)

LiteGate 以 Prometheus 文本格式暴露运行指标，覆盖 HTTP 请求、代理与上游、证书、配置重载、L4 Stream、服务发现和安全拦截等方面。

## 1. 启用

```yaml
metrics:
  enabled: true
  port: 9090          # 默认 9090，端点固定为 /metrics
  address: 0.0.0.0    # 默认 127.0.0.1，只允许本机抓取
```

- 也可以用命令行 `-enable-metrics` 开启，`-metrics-addr` 覆盖监听地址。
- 默认只监听 `127.0.0.1`。Prometheus 部署在其他主机时，需要把 `address` 设为内网地址或 `0.0.0.0`，并用防火墙限制来源。独立指标端口**不带鉴权**。
- 同时开启 Dashboard 时，Dashboard 端口上的 `/metrics` 也会输出同一份指标，但需要 Dashboard 登录，适合人工查看，不适合 Prometheus 抓取。

## 2. 常用指标

下表列出排障和告警最常用的指标，完整列表以 `curl http://127.0.0.1:9090/metrics | grep '^# HELP litegate_'` 的实际输出为准。

### HTTP 与代理

| 指标 | 类型 | 标签 | 说明 |
|---|---|---|---|
| `litegate_http_requests_total` | Counter | site, method, status | HTTP 请求总数 |
| `litegate_http_request_duration_seconds` | Histogram | site, method | 请求处理耗时 |
| `litegate_http_requests_in_flight` | Gauge | site | 正在处理的请求数 |
| `litegate_http_response_bytes_total` | Counter | site | 响应字节数 |
| `litegate_http_protocol_errors_total` | Counter | — | TLS 握手、HTTP/2、HTTP/3 协议错误 |
| `litegate_proxy_requests_total` | Counter | site, route, service, method, result | 代理请求结果 |
| `litegate_proxy_duration_seconds` | Histogram | upstream | 上游请求耗时 |
| `litegate_proxy_upstream_status_total` | Counter | service, status_class | 上游响应状态分类（2xx/3xx/4xx/5xx） |
| `litegate_proxy_retries_total` | Counter | site, route, reason | 重试次数 |
| `litegate_proxy_retry_budget_exhausted_total` | Counter | site, route | 因全局重试预算耗尽而放弃的重试 |
| `litegate_proxy_active_tunnels` | Gauge | site, service, route, proto | 当前 WebSocket/Upgrade 隧道数 |
| `litegate_proxy_cache_requests_total` | Counter | result | 代理缓存命中情况 |

### 上游健康与熔断

| 指标 | 类型 | 标签 | 说明 |
|---|---|---|---|
| `litegate_upstream_health_check_up` | Gauge | target, protocol | 主动健康检查结果，1 健康 / 0 不健康 |
| `litegate_upstream_ejections_total` | Counter | service | 被动健康检查剔除次数 |
| `litegate_circuit_breaker_state` | Gauge | instance | 0=Closed, 1=Half-Open, 2=Open |
| `litegate_circuit_breaker_trips_total` | Counter | instance | 熔断打开次数 |
| `litegate_discovery_healthy_instances` | Gauge | provider, service | 服务发现中的健康实例数 |

### 安全与准入

| 指标 | 类型 | 标签 | 说明 |
|---|---|---|---|
| `litegate_requests_rejected_total` | Counter | reason | 被安全与准入控制拒绝的请求 |
| `litegate_rate_limited_requests_total` | Counter | route | 被限流拒绝的请求 |
| `litegate_waf_blocked_requests_total` | Counter | rule, source | WAF 拦截 |
| `litegate_scan_protection_banned_ips` | Gauge | — | 扫描防护当前封禁的 IP 数 |

### 证书与配置

| 指标 | 类型 | 标签 | 说明 |
|---|---|---|---|
| `litegate_tls_cert_expiry_timestamp_seconds` | Gauge | domain, source | 已加载证书的过期时间（Unix 秒） |
| `litegate_cert_issuance_total` | Counter | type, result | ACME 证书申请次数 |
| `litegate_config_reload_total` | Counter | source, status | 配置重载次数 |
| `litegate_config_last_reload_success_timestamp_seconds` | Gauge | — | 最近一次成功重载的时间 |

### L4 Stream

| 指标 | 类型 | 标签 | 说明 |
|---|---|---|---|
| `litegate_stream_connections_total` | Counter | name, proto | Stream 连接总数 |
| `litegate_stream_active_sessions` | Gauge | name, proto | 当前活跃会话 |
| `litegate_stream_bytes_total` | Counter | name, proto, direction | 传输字节数 |
| `litegate_stream_dial_failures_total` | Counter | — | 上游拨号失败 |

### 进程

| 指标 | 类型 | 说明 |
|---|---|---|
| `litegate_build_info` | Gauge | 版本信息，标签 version、go_version，值恒为 1 |
| `litegate_goroutines_current` | Gauge | 当前 goroutine 数 |

此外还有 IDS（`litegate_ids_*`）、Connect（`litegate_connect_*`）、Kubernetes 控制器（`litegate_kubernetes_*`）、NATS 插件（`litegate_nats_*`）、通知总线（`litegate_notify_*`）和 MCP（`litegate_mcp_requests_total`）等分组指标，只有启用对应功能时才有数据。Go 运行时与进程的标准指标（`go_*`、`process_*`）同样会输出。

## 3. 接入 Prometheus

```yaml
scrape_configs:
  - job_name: 'litegate'
    scrape_interval: 15s
    static_configs:
      - targets: ['gateway-ip:9090']
```

官方 Grafana 面板位于仓库 [`deploy/grafana/litegate-dashboard.json`](https://github.com/jamesleeon/LiteGate/tree/master/deploy/grafana)：在 Grafana 中选择 Dashboards → New → Import，上传该文件并选择 Prometheus 数据源即可（需要 Grafana 10 及以上）。面板按 `job`、`instance`、`site` 筛选，覆盖概览、HTTP 流量、代理与上游、证书与 DNS、安全、代理缓存、Stream/SNI/Connect、NATS 以及运行时与配置重载；未使用的功能对应的面板保持为空。

早期的精简示例 [LiteGate_Overview.json](../../prometheus/LiteGate_Overview.json) 仍保留，新部署建议使用官方面板。

## 4. 告警示例

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

`litegate_http_request_duration_seconds` 是 Histogram，延迟分位数需要用 `histogram_quantile` 计算，不能直接使用 `quantile` 标签。`litegate_config_reload_total` 的 `status` 取值为 `success`、`error`、`rejected`、`panic`。

## 相关文档

- [Dashboard](dashboard.md)
- [访问日志](access-log.md)
- [Trace ID](trace-id.md)
