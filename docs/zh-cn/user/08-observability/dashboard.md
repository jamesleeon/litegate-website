# Web Dashboard (可视控制面板)

LiteGate 内置了一个直观、实时的 **Web Dashboard**，允许运维人员在浏览器中直接监控网关运行状态、管理站点配置以及分析流量日志。

---

## 1. 启用配置

在 `config.yaml` 中配置 Dashboard 的访问权限：

```yaml
dashboard:
  enabled: true
  port: 9999           # 面板访问端口
  username: "admin"
  password: "$2a$..."  # 必须使用 Bcrypt 哈希加密后的密码
```

---

## 2. 核心功能板块

### 实时指标 (Status)
- **系统状态**: CPU、内存、Goroutines 活跃数。
- **流量概况**: RPS (每秒请求数)、累计请求总量、在线连接数。
- **证书监控**: 所有域名的证书过期倒计时。

### 站点管理 (Sites)
- **在线编辑**: 直接在浏览器中修改站点的 `.yaml` 配置并即时生效。
- **状态监控**: 每一个 Site 的实时报错率和响应延迟 (Latency)。

### 服务发现 (Discovery)
- 查看 Litemesh、LiteDeploy、Docker、Consul、Kubernetes、Discovery Agent 以及外部 Discovery Provider 插件中的在线服务。
- 确认具体路由后端绑定的真实 IP 列表。
- “Control Plane Providers” 会为每个成功加载的 Discovery Provider 插件实例动态生成卡片，展示注册类型、实例名和 Watch/Namespace/Tags/Metadata 能力；插件配置和密钥不会进入状态接口。

### 编译插件 (Compiled Plugins)
- 独立列出当前二进制中实际注册的 Action、Middleware、LoadBalancer、KV、DNS、IDS 和 Discovery 插件。
- 展示插件注册名、类型、版本、公共 API 版本和能力；没有 Manifest 的旧插件会标记为兼容性未知。
- 插件 Manifest 提供 `ConfigExample` 时，卡片会显示说明，并提供“如何启用”折叠区与一键复制 YAML；NATS、OpenAPI MD5 和 forward proxy 等官方插件提供配置参考。
- 此区域表示“已经编入二进制”，Discovery Provider 的连接健康仍以 Control Plane Providers 和 Discovery Mesh 为准。

### Connect Network
- 查看每个 Peer 的在线 Session、注册 generation、活动连接数和已发布 hostname。
- CLI HTTP hostname 会分别显示 **Registration** 和 **Cloud TLS**，避免把“注册成功”误认为“公网 HTTPS 已可用”。
- Cloud TLS 会报告 `ready`、`eligible`、`issuing`、`failed` 或 `missing`，并尽可能展示精确/泛域名覆盖、证书来源、ACME 验证方式、过期时间和失败原因。
- 完整 Connect Site 的 TLS 在 Home 终止；Cloud TLS 状态只适用于 `litegate connect http` 发布的 hostname。

### 日志分析 (Logs)
- 实时访问日志流 (Access Log Tails)。
- 关键错误日志定位与搜索。

---

## 3. 安全建议

> [!WARNING]
> **生产环境安全建议**:
> 1.  务必修改默认用户名 `admin`。
> 2.  务必设置复杂的 Bcrypt 强密码。
> 3.  建议限制 Dashboard 端口的访问 IP（可以在外层再套一个 `ip_restriction` 中间件）。
> 4.  Connect Cloud TLS 的 `failed` 详情包含 ACME 原始错误，可能带有内部域名、Provider 或网络信息；不要向非受信用户开放 Dashboard 或对应状态接口。

---

## 延伸阅读
- [如何生成密码哈希](../../user/01-getting-started/installation.md#命令行参数)
- [Prometheus 指标集成](./metrics.md)
- [使用 CLI 发布内网 HTTP 服务](../09-advanced/connect-cli-http.md)
