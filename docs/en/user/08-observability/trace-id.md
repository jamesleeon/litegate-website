# Trace ID (Distributed Tracing)

LiteGate automatically generates a cryptographically unique Trace ID for every inbound HTTP request. This ID is propagated across services to enable distributed end-to-end transaction tracing and centralized log correlation.

---

## 1. Trace ID Propagation

- **Inbound Injection**: Every matched request is automatically injected with an `X-Trace-Id` HTTP header.
- **Trace Context Retention**: If an incoming request already carries a valid `X-Trace-Id` header (emitted by an upstream CDN or API client), the gateway respects and preserves the existing ID to maintain trace continuity.
- **Structured Log Correlation**: The active Trace ID is recorded inside the `trace_id` JSON property within access log files.
- **Downstream Propagation**: The gateway forwards the `X-Trace-Id` header to downstream backends to enable end-to-end tracing.

---

## 2. Deactivating Trace IDs

### Global Deactivation
To turn off Trace ID generation globally, set the following parameter in `config.yaml`:

```yaml
disable_trace_id: true
```

### Site-Level Deactivation
To turn off Trace ID generation for a specific site, configure the parameter inside `sites/*.yaml`:

```yaml
domain: example.com
disable_trace_id: true
```

---

## 3. Structured Log Correlation Example

When Trace ID is active, access logs record the trace context:

```json
{
  "level": "info",
  "mod": "access",
  "host": "api.example.com",
  "method": "GET",
  "path": "/api/users",
  "status": 200,
  "cost_ms": 15,
  "trace_id": "a1b2c3d4-e5f6-7890",
  "upstream": "10.0.0.5:8080"
}
```

Using the `trace_id` value, DevOps teams can query log aggregators (e.g. ELK, Grafana Loki, or Jaeger) to trace the execution path of a request across all microservices.
