# LiteGate MCP 能力表

本文用于说明 LiteGate 当前 MCP 暴露给 AI 的管理能力，以及这些能力是否足以支撑“用户只配置好 MCP，不额外提供文档，AI 就能协助完成网站配置和基础管理”。

## 结论

当前 MCP 已经覆盖了常见网站配置和大部分日常管理动作。对以下场景，AI 可以直接通过 MCP 自行获取信息、生成配置、校验、保存、重载和验证：

- 反向代理网站
- 静态网站
- 将域名绑定到服务发现中的 service
- 常见 TCP/UDP stream
- 基础排障和运行态检查

这意味着：用户只要完成 MCP 接入，并给出业务意图，例如域名、上游地址、站点类型，通常不需要再额外提供 LiteGate 配置文档。

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
| 文档/schema | `get_config_guide` | 获取站点配置说明 | 是 | 是 | AI 可不依赖外部文档 |
| 文档/schema | `get_gateway_config_schema` | 获取全局配置说明 | 是 | 是 | AI 可直接读取主配置 schema |
| 文档/schema | `get_stream_config_schema` | 获取 stream 配置说明 | 是 | 是 | 覆盖 L4 配置说明 |
| 配置校验 | `validate_site_config` | 严格校验站点配置 | 是 | 是 | 已复用 loader 严格校验 |
| 配置校验 | `validate_stream_config` | 严格校验 stream 配置 | 是 | 是 | 已复用 stream 校验 |
| 配置校验 | `validate_gateway_config` | 校验全局配置 | 是 | 部分 | 可拦截大部分格式和语义错误 |
| 生成与规划 | `plan_site_from_intent` | 根据自然语言给出配置建议 | 是 | 部分 | 适合复杂需求前置规划 |
| 快捷创建 | `create_proxy_site` | 创建反向代理站点 | 是 | 是 | 常见场景可直接落配置 |
| 快捷创建 | `create_static_site` | 创建静态站点 | 是 | 是 | 适合目录托管和 SPA |
| 快捷创建 | `bind_domain_to_service` | 将域名绑定到 service | 是 | 是 | 适合 mesh/discovery 场景 |
| 快捷创建 | `create_stream_proxy` | 创建 TCP/UDP stream | 是 | 是 | 覆盖常见 L4 转发 |
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

## 当前覆盖度判断

如果不把认证/OIDC 作为前提，当前 MCP 已经足够让 AI 完成“大多数常见网站配置”和“大部分日常管理”。

可以认为当前能力已经达到：

- 常见网站配置：已覆盖
- 常见 stream 配置：已覆盖
- 配置前校验：已覆盖
- 保存后自动应用：已覆盖
- 基础结果验证：已覆盖
- 常规排障：已覆盖
- 生产级精细变更分析：部分覆盖
- 生产级稳健回滚：部分覆盖

## 仍然建议继续增强的点

虽然当前已经能让 AI 在没有外部文档的情况下协助用户建站，但下面这些点仍然值得继续加强：

- `preview_config_change` 的影响分析可以更细，例如明确受影响的站点、端口、监听器
- `verify_site` 可以进一步返回命中的 route、最终 upstream 等更强断言信息
- `verify_stream` 可以进一步确认监听者是否为 LiteGate 本进程
- 回滚链路可以进一步强化备份失败时的错误处理和状态说明

## 对“不给任何文档”的判断

如果用户已经把 MCP 配好，AI 不依赖额外人工提供的 LiteGate 文档，也能完成常见配置。原因是：

- MCP 本身已经暴露了 schema 和配置说明
- MCP 本身已经暴露了当前运行状态和现有配置
- MCP 本身已经提供了校验、保存、回滚、验证和排障能力

因此，外部文档不再是常见建站流程的必需输入，而更像是补充材料。
