# Dashboard API 参考

LiteGate 内置控制台 (Dashboard) 提供了一套 HTTP API，用于程序化地获取网关状态、管理配置和查看实时监控数据。

---

## 1. 基础信息

- **默认地址**: `http://localhost:9999`
- **鉴权方式**: 支持以下两种方式：
  - **Session**: 通过 `/login` 接口用 `username/password` 登录获取 Cookie。
  - **API Token**: 在请求头中携带 `X-API-Key: <token>` (在 config.yaml 的 `dashboard.token` 中配置)。

> [!IMPORTANT]
> **严禁公网暴露管理端口**。强烈建议仅绑定在 `127.0.0.1` 或通过 VPN 访问。

---

## 2. 状态与监控

### 获取系统状态概览

```
GET /status/json
```

响应中的 `discovery_providers` 列出已经成功加载的外部 Discovery Provider 插件实例：

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

该字段只提供非敏感运行时清单，不返回 `service_discovery.catalogs[].config`。

`compiled_plugins` 则列出当前二进制中注册的全部外部插件组件，包括 `kind`、`name`、
`version`、`api_version`、`description`、`capabilities`、`config_example`、`has_manifest` 和
`compatible`。它与运行期发现源健康状态分离，未配置使用的插件也会出现在这个清单中。
`config_example` 来自插件 Manifest，只允许放公开的占位配置，禁止包含 token、密码或真实凭证。

**返回示例**:
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

### 获取实时指标

```
GET /api/v1/realtime
```

返回最近的 QPS、延迟分布、错误率等实时指标。

---

## 3. 站点管理

### 获取所有站点

```
GET /api/v1/sites
```

返回当前内存中所有活跃站点的完整配置快照，包含路由、上游信息和请求统计。

### 获取单个站点详情

```
GET /api/v1/sites/{domain}
```

### 动态创建/更新站点

```
PUT /api/v1/sites/{domain}
Content-Type: application/json

{
  "domain": "new-site.com",
  "routes": [...]
}
```

---

## 4. Stream 管理

### 获取所有 Stream

```
GET /api/v1/streams
```

返回所有 L4 Stream 代理的状态，包括活跃连接数和流量统计。

---

## 5. 服务发现

### 获取发现的服务列表

```
GET /api/v1/discovery
```

返回从 Consul / Litemesh 同步到的所有后端服务及其实例状态。

---

## 6. 证书管理

### 获取证书列表

```
GET /api/v1/certs
```

返回所有已管理的 TLS 证书的域名、过期时间和来源。

---

## 7. 访问日志

### 获取最近日志

```
GET /api/v1/logs/recent
```

返回最近的访问日志条目（内存中缓存的最近 5 条）。

---

## 8. 配置操作

### 获取当前运行配置

```
GET /api/v1/config
```

### 重新加载配置

```
POST /api/v1/reload
```

---

## 9. Prometheus Metrics

独立的 Metrics 端口（默认 9090）：

```
GET /metrics
```

**核心指标**:

| 指标 | 说明 |
| :--- | :--- |
| `litegate_http_requests_total` | 累计处理的请求数 |
| `litegate_http_request_duration_seconds` | 请求处理延迟分布 |
| `litegate_active_connections` | 当前活跃连接数 |
| `litegate_upstream_health` | 上游健康状态 |
