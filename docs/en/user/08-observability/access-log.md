# Access Log

LiteGate structured access logs capture detailed metrics for every single incoming HTTP(S) request passing through the edge gateway. They serve as the primary source of truth for traffic analysis, API troubleshooting, and security audit telemetry.

---

## 1. Global Logging Configurations

Configure active access log behaviors globally inside your `config.yaml` under the `log` section:

```yaml
log:
  format: json            # json or console — controls all log output, including access logs
  access_log:
    enabled: true
    stdout: true          # write access logs to the console
    level: info           # none, error, warn, info, debug
    file_enabled: false   # set true to write access logs to file
    file: ""              # optional; defaults to ./logs/access.log when file_enabled is true
    max_size: 100         # optional; max size of a single log file (MB)
    max_age: 7            # optional; max number of days to retain old log files
    max_backups: 30       # optional; max number of old log files to retain
    compress: true        # optional; gzip-compress rotated log files
    routing_detail: false # set true for detailed routing-decision logs
```

---

## 2. Structured JSON Field Reference

LiteGate outputs rich L7 routing and networking metadata variables in standard JSON formats to streamline ingestion into downstream Big Data analytics pipelines:

| Property Field | Description | JSON Value Example |
| :--- | :--- | :--- |
| `time` | ISO-8601 timestamp when request processing finished | `"2026-03-22T10:00:00Z"` |
| `client_ip` | Extracted true downstream client IP address | `"1.2.3.4"` |
| `method` | Requested HTTP standard verb | `"POST"` |
| `path` | Requested absolute URL routing pathway | `"/api/v1/user"` |
| `status` | Emitted HTTP response status code | `200` |
| `latency` | Combined gateway L7 processing overhead latency (ms) | `15.5` |
| `upstream` | Physical backend instance IP address mapped by selector | `"10.0.0.5:8080"` |
| `site` | Target site domain | `"api.example.com"` |
| `route` | ID of the matched routing rule | `"user-service-route"` |

---

## 3. Collection Modes & Performance

Access logs support three output targets (`stdout` / `file` / `webhook`), which can be enabled simultaneously. However, their impact on the request hot path differs **drastically** — choose by scenario:

| Output Target | Write Mode | Impact on Request Performance | Use Case |
| :--- | :--- | :--- | :--- |
| `webhook` | **Asynchronous** (memory copy + non-blocking enqueue, background batched POST) | Near zero, **does not block requests** | **Production default (centralized)** |
| `file` | Synchronous disk write (incl. rotation I/O) | Written synchronously inside the request goroutine, **occupies the hot path** | Low request volume / local debugging |
| `stdout` | Synchronous console write | Written synchronously inside the request goroutine, **occupies the hot path** | Development debugging |

> ⚠️ **Important**: only `webhook` is asynchronous; both `stdout` and `file` are written **synchronously** inside the request goroutine. In high-throughput production, disable `stdout` and `file` and keep only `webhook` — otherwise synchronous I/O becomes a forwarding bottleneck.

**Two recommended deployment modes:**

1. **Centralized Mode (production default, recommended)**: Use `webhook` to asynchronously push logs to a unified MQ ingress service, then have an independent consumer persist them (e.g. OpenObserve / Elasticsearch). Delivery is *best-effort* — when the queue is full or the downstream is unavailable, logs are **dropped rather than blocking**, guaranteeing zero impact on LiteGate's forwarding performance.

    ```yaml
    log:
      format: json
      access_log:
        enabled: true
        stdout: false       # disable in production to avoid sync console writes on the hot path
        file_enabled: false # disable in production to avoid sync disk I/O on the hot path
        webhook:
          enabled: true
          url: http://<mq-ingress>/access-log  # MQ ingress that enqueues and returns immediately
          batch_size: 100   # max entries per batch, default 100
          interval: 1s      # batch flush interval, default 1s
    ```

2. **File Mode (low request volume only)**: No external dependency, writes straight to disk with built-in rotation/cleanup. Because writes are **synchronous**, only recommended for low traffic or when no centralized logging platform is available.

    **Safe-by-default fallback**: when `file_enabled: true` is set without rotation parameters, the gateway rotates each file at 100 MB and retains only the last 7 days, preventing unbounded disk growth. Tune per available disk space:

    ```yaml
    log:
      access_log:
        file_enabled: true
        max_size: 100      # optional; max size of a single log file (MB)
        max_age: 7         # optional; max days to retain old files (defaults to 7 when both max_age and max_backups are unset)
        max_backups: 30    # optional; max number of archived log files to retain
        compress: true     # optional; gzip-compress rotated log files
    ```

---

## 4. Other Best Practices

1. **Dedicated Storage Volumes**: When using file mode, direct log directories to a dedicated disk partition to prevent log growth from impacting core system operation.
2. **Graceful Shutdown**: On shutdown, the gateway flushes the webhook buffer after it stops accepting requests, minimizing log loss (in centralized mode, delivery is best-effort and logs may still be dropped under extreme conditions).
3. **ELK Ingestion**: In file mode, pair with Filebeat to ship JSON logs directly into Elasticsearch.


## Custom access log templates

```yaml
log:
  format: json
  access_log:
    enabled: true
    stdout: true
    file_enabled: true
    file: ./logs/access.log
    template: '{client_ip} - [{timestamp}] "{method} {uri}" {status} {size_bytes} "{referer}" "{user_agent}" {cost_ms}'
```

`template` formats access log stdout and files. Leave it empty to preserve existing output. Application logs still use `log.format`; webhooks and dashboard data remain structured. Rotation, asynchronous output and level filtering still apply.

Fields: `timestamp`, `client_ip`, `method`, `path`, `uri` (including the query), `host`, `status`, `size_bytes`, `cost_ms`, `upstream`, `route`, `site`, `trace_id`, `referer`, `user_agent`. Timestamps use the existing structured log timestamp; costs are milliseconds with fractional precision. Empty Referer and User-Agent values become `-`. Missing values become `-`. Newlines, control characters, quotes and backslashes in field values are escaped to prevent forged log lines. Templates must be single-line; unknown or malformed placeholders fail configuration validation. This uses LiteGate `{field}` syntax rather than Nginx `$variables`.

Restart LiteGate after changing `log.access_log.template`. Only `log.level` is hot-reloadable among global log settings. MCP saves validate the configuration and request a reload, but a successful save does not mean startup-only settings are active. `litegate -init` includes an empty template and a custom template example in its generated configuration.
