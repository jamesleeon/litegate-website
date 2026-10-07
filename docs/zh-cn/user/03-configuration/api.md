# 控制 API 参考 (Control API)

LiteGate 提供了一套基于 HTTP 的管理 API，允许程序化地获取网关状态、监控指标或动态调整部分运行参数。默认情况下，API 与 Dashboard 运行在同一个端口。

---

## 1. 基础信息

- **默认地址**: `http://localhost:9999`
- **鉴权方式**: 除非在全局配置中关闭，否则 API 遵循 Dashboard 的 `username/password` 认证。

---

## 2. 常用接口

### 获取网关全局状态
- **Endpoint**: `GET /status/json`
- **返回内容**: 包含运行时间、内存使用、Goroutines 数量以及已加载的路由摘要。

### 获取当前所有站点配置
- **Endpoint**: `GET /api/v1/sites`
- **返回内容**: 当前内存中所有活跃站点的完整配置快照。

### 查询特定服务发现详情
- **Endpoint**: `GET /api/v1/discovery`
- **返回内容**: 罗列所有从 Consul 或 Litemesh 同步到的后端实例状态。

---

## 3. 监控指标 (Metrics)

LiteGate 内置了 Prometheus 抓取端点。

- **Endpoint**: `GET /metrics` (通常运行在 `9091` 端口)
- **核心指标**:
    - `litegate_http_requests_total`: 累计处理的请求数。
    - `litegate_http_request_duration_seconds`: 请求处理延迟分布。

---

## 4. 动态调整 (限流/开关)

部分中间件支持通过 API 动态开关，无需编写 YAML 文件。详细请参考具体的中间件开发文档。

---

## 安全建议
- **严禁公网暴露管理端口**: 强烈建议将 API 端口仅绑定在 `127.0.0.1` 或通过 VPN 访问。
- **使用强密码**: 面板和 API 共享 Bcrypt 加密凭据。
