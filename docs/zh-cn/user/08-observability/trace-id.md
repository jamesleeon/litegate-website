# Trace ID (分布式追踪)

LiteGate 自动为每个 HTTP 请求生成唯一的 Trace ID，用于全链路追踪和日志关联。

---

## 1. 工作方式

- 每个入站请求会被自动注入一个 `X-Trace-Id` Header。
- 如果请求已携带 `X-Trace-Id`，网关会原样保留（尊重上游链路）。
- Trace ID 会出现在 Access Log 的 `trace_id` 字段中。
- 转发到上游的请求也会携带此 Header，实现端到端追踪。

---

## 2. 禁用 Trace ID

### 全局禁用

在 `config.yaml` 中：

```yaml
disable_trace_id: true
```

### 站点级禁用

在站点配置 `sites/*.yaml` 中：

```yaml
domain: example.com
disable_trace_id: true
```

---

## 3. 日志关联示例

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

通过 `trace_id` 可以在上游服务日志中快速定位同一请求的完整调用链。
