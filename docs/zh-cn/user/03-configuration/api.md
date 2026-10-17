# 管理接口概览

LiteGate 的管理与观测入口分布在以下几个端口，各自独立开关。

| 入口 | 配置 | 默认监听 | 鉴权 | 文档 |
|---|---|---|---|---|
| Dashboard 与管理 API | `dashboard` | `:9999`（所有网卡） | `X-API-Key` 或登录 Cookie | [Dashboard API](../08-observability/dashboard-api.md) |
| Prometheus 指标 | `metrics` | `127.0.0.1:9090` | 无 | [Metrics](../08-observability/metrics.md) |
| MCP（SSE） | `mcp` | `port` 指定 | `token`（Bearer） | [MCP 能力表](../../litegate_mcp_capability_matrix.md) |
| pprof | `pprof` | `127.0.0.1:6060` | 无 | [调试](../11-troubleshooting/debugging.md) |

网关业务端口上另有 `/healthz` 与 `/readyz` 健康检查端点，供负载均衡和 Kubernetes 探针使用。

## 安全建议

- Dashboard 默认监听所有网卡，务必设置强密码与 `token`，并用防火墙或前置网关限制来源。
- 指标与 pprof 端口没有鉴权，只开放给采集机或运维网络。
- 自动化调用优先使用 `X-API-Key`，不要在脚本中保存登录密码。
