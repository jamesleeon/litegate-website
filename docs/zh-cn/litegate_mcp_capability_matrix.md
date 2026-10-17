# LiteGate MCP 能力表

LiteGate 内置 MCP（Model Context Protocol）服务端，让 AI 助手直接读取配置、生成并校验站点、保存重载、发布回滚以及排障。本文列出当前暴露的全部工具。

## 接入方式

LiteGate 提供两种接入方式，工具列表相同，区别在于 AI 连接的是哪个进程：

| | stdio | SSE |
|---|---|---|
| 启动方式 | AI 客户端执行 `litegate mcp -config <路径>` 拉起一个独立进程 | 运行中的网关在 `mcp.port` 上提供 `/sse` 端点 |
| 适合 | 本机编写、校验、保存配置 | 管理一台正在运行的网关、远程排障 |
| 配置读写、校验、建站、发布回滚 | 可用 | 可用 |
| 运行时诊断（`get_recent_requests`、`get_recent_errors`、`get_gateway_status`、`list_active_tunnels`、`get_connect_status` 等） | 只反映 MCP 进程自身，看不到网关流量 | 反映正在运行的网关 |
| 保存后生效 | 写入文件，由正在运行的网关热加载 | 写入文件并重载当前网关 |

### stdio：本机 AI 客户端

日志全部写到 stderr，stdout 只承载 JSON-RPC。`config.yaml` 不存在时会生成默认配置和目录。

`sites_dir`、`streams_dir`、`certs_dir` 等相对路径按**进程工作目录**解析，而 AI 客户端拉起进程时的工作目录通常不是 `config.yaml` 所在目录。请在 `config.yaml` 中把这些目录写成绝对路径，或让客户端在配置目录中启动 LiteGate。

Claude Code：

```bash
claude mcp add litegate -- litegate mcp -config /etc/litegate/config.yaml
```

Cursor（`.cursor/mcp.json`）、Claude Desktop 等使用 JSON 配置的客户端：

```json
{
  "mcpServers": {
    "litegate": {
      "command": "litegate",
      "args": ["mcp", "-config", "/etc/litegate/config.yaml"]
    }
  }
}
```

### SSE：连接正在运行的网关

在 `config.yaml` 中开启，网关启动或热加载后监听 `mcp.port`，端点为 `/sse`（消息端点 `/message` 由服务端在握手时告知客户端）：

```yaml
mcp:
  enabled: true
  port: 9900                            # 默认 8080，不能与 http.port、Dashboard 和入口端口冲突
  token: "REPLACE_WITH_STRONG_TOKEN"    # 客户端以 Authorization: Bearer <token> 访问
  public_url: ""                        # 经反向代理暴露时填写公开地址，例如 https://ops.example.com/mcp
```

`token` 为空时不做鉴权，请始终设置。生成随机值可用 `litegate -secret`。

Claude Code：

```bash
claude mcp add --transport sse litegate http://127.0.0.1:9900/sse --header "Authorization: Bearer <token>"
```

JSON 配置的客户端：

```json
{
  "mcpServers": {
    "litegate": {
      "url": "http://127.0.0.1:9900/sse",
      "headers": { "Authorization": "Bearer <token>" }
    }
  }
}
```

### 安全

MCP 工具可以修改、删除配置和写入令牌文件。SSE 端口只在本机或内网监听，不要直接暴露到公网；需要远程使用时放在带认证的入口之后，并开启[配置发布控制面](release_control_guide.md)，让 AI 的修改先进入草稿、确认后再发布。

### 让 AI 开始工作

连接成功后可以直接用自然语言描述需求，例如：

- 「把 app.example.com 的 /api 转发到 127.0.0.1:8080，其余用 ./dist 做单页应用，开启 HTTPS。」
- 「列出 30 天内到期的证书。」
- 「为什么请求 https://api.example.com/v1/orders 返回 404？」

AI 会按下文「典型闭环」调用工具：先读配置说明，生成配置后用 `validate_*` 校验、`preview_config_change` 预览差异，再保存并用 `verify_site` 验证。

### Litemesh MCP 代理

启用 Litemesh 后，LiteGate 会发现 Litemesh 中注册的 MCP 服务，把它们的工具和资源一并代理出来，AI 客户端只需连接 LiteGate 一个入口。

## 能力矩阵

| 分类 | Tool | 作用 | AI 是否可直接使用 | 是否形成闭环 | 备注 |
| --- | --- | --- | --- | --- | --- |
| 环境发现 | `detect_environment` | 获取主机名、出口 IP、监听信息 | 是 | 部分 | 用于判断访问入口和部署环境 |
| 配置盘点 | `list_sites` | 列出现有站点 | 是 | 是 | 可作为变更前基线 |
| 配置盘点 | `get_site_config` | 读取站点 YAML | 是 | 是 | 支持直接审阅和修改 |
| 配置盘点 | `list_streams` | 列出现有 stream | 是 | 是 | L4 配置已纳入管理面 |
| 配置盘点 | `get_stream_config` | 读取 stream YAML | 是 | 是 | 支持直接审阅和修改 |
| 配置盘点 | `get_gateway_config` | 读取全局 `config.yaml` | 是 | 是 | 全局配置已可读 |
| KV 读写 | `get_kv` | 从 Litemesh/Consul KV 中读取特定键值 | 是 | 是 | AI 可直接审阅动态前端版本指针等 KV 状态 |
| KV 读写 | `set_kv` | 往 Litemesh/Consul KV 中写入特定键值 | 是 | 是 | AI 可直接写入最新前端 ZIP 发布版本与 URL 指针 |
| KV 读写 | `list_kv` | 模糊列出特定前缀下的所有 KV 项 | 是 | 是 | 适合大范围排查动态站点或前端指针的状态 |
| 服务发现 | `list_services` | 列出 mesh/service registry 中的服务 | 是 | 部分 | 适合给 AI 选 upstream |
| 服务发现 | `get_service_detail` | 获取服务实例与端点信息 | 是 | 部分 | 可配合绑定域名使用 |
| 文档/schema | `get_config_guide` | 获取站点、L4 Stream 或流量治理配置说明 | 是 | 是 | `topic=site` / `stream` / `traffic`；支持 `lang=zh` / `en`，包含负载均衡策略及作用范围 |
| 文档/schema | `get_gateway_config_schema` | 获取全局配置说明 | 是 | 是 | AI 可直接读取主配置 schema |
| 文档/schema | `get_stream_config_schema` | 获取 stream 配置说明 | 是 | 是 | 覆盖 L4 配置说明 |
| 配置校验 | `validate_site_config` | 严格校验站点配置 | 是 | 是 | 已复用 loader 严格校验 |
| 配置校验 | `validate_stream_config` | 严格校验 stream 配置 | 是 | 是 | 已复用 stream 校验 |
| 配置校验 | `validate_gateway_config` | 校验全局配置 | 是 | 部分 | 可拦截大部分格式和语义错误 |
| 快捷创建 | `create_proxy_site` | 创建反向代理站点 | 是 | 是 | 常见场景可直接落配置 |
| 快捷创建 | `create_static_site` | 创建静态站点 | 是 | 是 | 适合目录托管和 SPA |
| 快捷创建 | `bind_domain_to_service` | 将域名绑定到 service | 是 | 是 | 支持 `lb_policy` 指定 HTTP 实例负载均衡策略，默认轮询 |
| 快捷创建 | `create_stream_proxy` | 创建单静态后端 TCP/UDP Stream | 是 | 是 | 多后端、权重、服务发现及策略配置使用 `get_config_guide(topic=stream)` → `validate_stream_config` → `save_stream_config` |
| 变更预览 | `preview_config_change` | 预览 diff 和影响 | 是 | 部分 | 能看变更，但影响分析仍偏粗粒度 |
| 变更执行 | `save_site_config` | 保存站点配置 | 是 | 是 | 当前已包含校验和自动 reload |
| 变更执行 | `save_stream_config` | 保存 stream 配置 | 是 | 是 | 当前已包含校验和自动 reload |
| 变更执行 | `save_gateway_config` | 保存全局配置 | 是 | 是 | 当前已包含校验和自动 reload |
| 手动应用 | `reload_gateway` | 触发网关重载 | 是 | 是 | 可用于显式重载 |
| 回滚 | `rollback_last_change` | 回滚最近一次配置变更 | 是 | 部分 | 依赖 `.bak` 备份质量 |
| 联通性验证 | `test_upstream` | 检测 upstream TCP 可达性 | 是 | 部分 | 更偏基础探测 |
| 站点验证 | `verify_site` | 发起真实 HTTP/HTTPS 请求验证 | 是 | 大部分 | 可确认站点可达与基本响应 |
| Stream 验证 | `verify_stream` | 检查 stream 监听和上游可达 | 是 | 大部分 | 对 L4 已有基础验收能力 |
| 运行诊断 | `get_recent_errors` | 读取近期错误日志 | 是 | 是 | 适合 reload 后排障 |
| 运行诊断 | `get_gateway_status` | 查看运行状态、内存、goroutine | 是 | 是 | 适合健康检查 |
| 证书诊断 | `list_certificates_status` | 查看证书状态和过期时间 | 是 | 是 | 可辅助 HTTPS 配置 |
| 证书诊断 | `inspect_certificate` | 查看证书详情 | 是 | 部分 | 更适合诊断，不是建站主路径 |
| 补齐输入 | `explain_missing_inputs` | 帮 AI 向用户收敛缺失信息 | 是 | 是 | 减少 AI 乱猜 |

## 其他工具

以下工具覆盖认证、发布控制、服务标签、路由诊断、证书与 Connect 等场景。

| 分类 | Tool | 作用 |
|---|---|---|
| 建站 | `create_template_site` | 创建服务端模板渲染站点，支持模板 KV 模式 |
| 建站 | `create_status_site` | 创建状态看板站点 |
| 建站 | `create_forward_site` | 创建 Forward 站点，把公网 HTTPS 主机名绑定到内部 Stream 或 Connect Peer |
| 建站 | `export_lite_config` | 把 .lite.yaml 编译为标准 YAML，等同 `litegate -export-lite` |
| 认证 | `enable_oidc_for_site` | 为站点 proxy 路由启用 OIDC；v2 保留注释与简写 |
| 认证 | `enable_jwt_for_site` | 为站点 proxy 路由启用 JWT（JWKS 或 HS 密钥引用）；不保护 notify 路由 |
| 认证 | `enable_apikey_for_site` | 为站点 proxy 路由启用 API Key 校验与配额限流 |
| 删除 | `delete_site_config` | 删除站点配置文件 |
| 删除 | `delete_stream_config` | 删除 Stream 配置文件 |
| 发布控制 | `list_releases` | 列出草稿与已发布版本 |
| 发布控制 | `get_release_detail` | 查看某个版本的详情与配置内容 |
| 发布控制 | `get_release_diff` | 比较某个版本与当前生效文件 |
| 发布控制 | `validate_draft` | 预检当前草稿：结构、端口冲突、保留路径 |
| 发布控制 | `publish_release` | 发布草稿，发布前自动预检 |
| 发布控制 | `rollback_release` | 回滚到上一个或指定版本 |
| 服务标签 | `get_tag_dsl_guide` | 服务标签使用指南（四键快捷模式与命名资源） |
| 服务标签 | `get_tag_reference` | 服务标签权威参考，可按关键词检索 |
| 服务标签 | `get_service_tag_templates` | 可直接使用的标签模板 |
| 服务标签 | `preview_service_tags` | 用运行时解析器校验标签并预览生成的路由 |
| 服务标签 | `explain_tag` | 判定标签键属于新资源、快捷键还是已废弃键 |
| 路由诊断 | `lookup_route` | 模拟一次请求的路由匹配，返回命中路由、上游与改写后路径 |
| 路由诊断 | `get_recent_requests` | 最近处理的 HTTP 请求 |
| 路由诊断 | `list_active_tunnels` | 当前 WebSocket/Upgrade 隧道 |
| 运行诊断 | `get_goroutine_profile` | 完整 goroutine 栈，用于排查泄漏 |
| 运行诊断 | `list_plugins` | 列出编入二进制的插件，等同 `litegate plugins list` |
| 证书 | `request_certificate` | 立即为域名直接走 ACME 申请证书（手动管理用） |
| 证书 | `inspect_on_demand_tls` | 查看 On-Demand TLS 配置与已映射域名 |
| Connect/Forward | `get_connect_status` | Connect 隧道状态：Peer、在线、会话、域名归属与冲突 |
| Connect/Forward | `generate_connect_token` | 生成 Connect Peer 令牌并以 0600 权限落盘，不覆盖已有文件 |
| Connect/Forward | `generate_forward_token` | 生成 Forward 站点令牌并以 0600 权限落盘，不覆盖已有文件 |
| 部署 | `generate_systemd_unit` | 生成 systemd 单元，等同 `litegate systemd --print` |

## 典型闭环

### 1. 创建反向代理网站

常用链路：

1. `detect_environment`
2. `test_upstream`
3. `create_proxy_site`
4. `preview_config_change`
5. `save_site_config`
6. `verify_site`
7. `get_recent_errors`

### 2. 将域名绑定到服务发现中的服务

常用链路：

1. `list_services`
2. `get_service_detail`
3. `bind_domain_to_service`
4. `preview_config_change`
5. `save_site_config`
6. `verify_site`

### 3. 创建一个 TCP/UDP Stream

常用链路：

1. `test_upstream`
2. `create_stream_proxy`
3. `preview_config_change`
4. `save_stream_config`
5. `verify_stream`
6. `get_recent_errors`

### 4. 动态前端 ZIP 自动同步与升级 (Serve KV)

常用链路：

1. `detect_environment`
2. `get_gateway_config` (确认 Litemesh 或 Consul 启用状态与配置目录)
3. `set_kv` (写入最新前端 ZIP 发布版本号、URL 及 SHA256 校验和，如 `litegate/config/front/main`)
4. `verify_site` (发起真实请求验证新版静态前端是否热切部署成功)
5. `get_recent_errors` (辅助检测可能存在的同步与解压报错)

### 5. 配置发布控制面

开启 `dashboard.release_control` 后，变更先进入草稿：

1. `save_site_config` / `save_stream_config`（写入草稿）
2. `validate_draft`
3. `get_release_diff`
4. `publish_release`
5. `verify_site`；异常时 `rollback_release`

### 6. 路由排障

1. `lookup_route`（确认命中的路由、上游和改写结果）
2. `get_recent_requests`
3. `get_recent_errors`

## 相关文档

- [全局配置：MCP](user/03-configuration/global-config.md)
- [配置发布控制面](release_control_guide.md)
- [CLI 参考](user/01-getting-started/cli-reference.md)
