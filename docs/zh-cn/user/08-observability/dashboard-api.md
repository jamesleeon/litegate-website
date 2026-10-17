# Dashboard API 参考

Dashboard 的页面与管理接口运行在同一个端口上。本文列出当前代码注册的全部接口，供脚本和自动化调用。

## 1. 基础信息

```yaml
dashboard:
  enabled: true
  port: 9999                  # 默认 9999，监听所有网卡
  username: admin
  password: REPLACE_WITH_STRONG_PASSWORD
  token: REPLACE_WITH_API_TOKEN   # 自动化调用使用
  allowed_origins: []         # 额外允许的 Origin；留空只允许同源
  require_secure_cookie: false    # 通过 HTTPS 访问时建议开启
```

Dashboard 监听所有网卡，生产环境请用防火墙或前置网关限制访问来源，不要直接暴露到公网。

### 鉴权

除 `/login`、`/api/login` 和静态资源外，所有接口都需要鉴权，按以下顺序判断：

1. **API Token**：请求头 `X-API-Key: <dashboard.token>`。值正确直接放行；值错误立即返回 401，不再尝试 Cookie。
2. **登录 Cookie**：`POST /api/login` 成功后下发签名 Cookie，有效期 24 小时。使用 Cookie 的 POST/PUT/DELETE 请求必须带同源的 `Origin` 或 `Referer`，或匹配 `allowed_origins`，否则返回 403。

未配置 `username` 时 Cookie 登录一律拒绝。未登录访问页面会跳转到 `/login`，访问 JSON 接口返回 401。

`/api/scan-protection/toggle` 与 `/api/scan-protection/unblock` 无论用哪种方式鉴权，都要求请求带合法的 `Origin` 或 `Referer`。

### 响应格式

大部分管理接口返回：

```json
{"success": true, "message": "Saved successfully"}
{"success": true, "data": {}}
```

失败时 `success` 为 `false`，`message` 为原因，HTTP 状态码同时反映错误类型。

### 示例

```bash
curl -H "X-API-Key: $TOKEN" http://127.0.0.1:9999/status/json
```

## 2. 登录

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/login` | 登录页面 |
| POST | `/api/login` | 请求体 `{"username": "...", "password": "..."}`，成功后下发 Cookie |
| POST | `/api/logout` | 清除 Cookie |

## 3. 状态与运行时

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/status` | Dashboard 主页面 |
| GET | `/status/json` | 网关状态 JSON；可加 `?service=<name>` 只看某个服务 |
| GET | `/overview/json` | 概览数据 |
| GET | `/api/runtime` | 运行时数据（内存、goroutine 等） |
| GET | `/api/upstreams` | 上游与健康状态 |
| GET | `/api/ddns` | DDNS 与内网 DNS 同步状态 |
| GET | `/api/stream/traffic` | 实时流量（SSE） |
| GET | `/metrics` | Prometheus 指标；仅在 `metrics.enabled: true` 时注册，需要登录 |

## 4. 路由诊断

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/status/routing` | 路由页面 |
| GET | `/api/routing` | 当前路由表 |
| GET | `/api/routing/explain` | 模拟一次请求的匹配，参数 `host`、`method`、`path`、`entrypoint`、`client_ip` |
| GET | `/api/routing/pipeline` | 查看某条路由的中间件管线，参数 `site`、`route` |
| GET | `/status/tags` | 服务标签页面 |
| GET | `/api/service-tags` | 服务标签解析结果 |

## 5. 配置管理

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/config/validate` | 只校验不保存。请求体 `{"kind": "site\|lite\|stream", "filename": "...", "content": "..."}`，`kind` 为空时按文件名推断 |
| POST | `/api/save` | 保存配置。请求体 `{"type": "site\|stream", "filename": "app.yaml", "content": "..."}`，`content` 可以是 YAML 字符串或 JSON 对象；文件名必须以 `.yaml` 结尾 |
| POST | `/api/delete` | 删除配置。请求体 `{"type": "site\|stream", "filename": "app.yaml"}` |

开启 `dashboard.release_control.enabled` 后，`/api/save` 与 `/api/delete` 只修改草稿，返回草稿信息，需要再通过发布接口生效；未开启时直接写入配置存储并触发重载。

## 6. 发布控制

以下接口需要开启 `dashboard.release_control.enabled`，否则返回 400。流程说明见[配置发布控制面](../../release_control_guide.md)。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/releases` | 列出所有版本（含草稿） |
| POST | `/api/releases` | 用一组配置创建草稿，请求体为配置制品数组；存在生效配置时拒绝空数组 |
| GET | `/api/releases/{id}` | 版本详情 |
| POST | `/api/releases/{id}/validate` | 预检 |
| POST | `/api/releases/{id}/publish` | 发布 |
| GET | `/api/releases/{id}/diff` | 该版本相对当前生效配置的差异 |
| POST | `/api/releases/{id}/rollback` | 回滚到该版本；`{id}` 写 `previous` 表示回滚到上一个生效版本 |
| GET | `/api/releases/history` | 变更历史 |
| GET | `/api/snapshot/export` | 导出快照文件 `litegate-snapshot.json` |
| POST | `/api/snapshot/import` | 导入快照为新草稿 |
| GET | `/api/snapshot/resolved-sites` | 导出解析后的站点 `resolved-sites.json`（不要求发布控制） |

## 7. 证书

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/cert/download?file=<name>` | 下载证书与私钥 ZIP |
| POST | `/api/cert/dry-run` | 检查 DNS Provider 能否为域名申请证书，请求体 `{"provider": "...", "domain": "..."}`；自动证书未启用时返回 503 |

## 8. 安全与缓存

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/scan-protection/toggle?enabled=true\|false` | 临时开关扫描防护，重启后恢复为配置值 |
| POST | `/api/scan-protection/unblock?ip=<ip>` | 解封一个 IP |
| POST | `/api/proxy-cache/purge` | 清理代理缓存。请求体 `{"scope": "all\|site\|route\|key", "site": "...", "route": "...", "base_key": "..."}` |

## 9. 日志与文档

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/status/logs` | 日志页面 |
| GET | `/api/logs/tail` | 最近日志，参数 `after`（游标）、`limit` |
| GET | `/status/docs` | 内置配置文档页面 |
| GET | `/api/docs` | 内置文档索引 |
| GET | `/api/docs/content?slug=<slug>&lang=<zh\|en>` | 内置文档正文 |

## 10. 自助发布

开启 `self_service` 后，`/publish`、`/publish/` 与 `/api/publish/` 由自助发布门户处理，使用独立的账号与 Cookie，不走本文的鉴权规则。

## 相关文档

- [Dashboard](dashboard.md)
- [Metrics](metrics.md)
- [配置发布控制面](../../release_control_guide.md)
