# Status Action (系统状态监控看板)

`status` Action 可以在网关层直接向终端用户或管理员交付一个高颜值、响应式的系统状态监控仪表盘（Dashboard）。它会自动收集网关内所有的 site 和代理路由的流量、QPS、延迟等 live 指标及历史健康状况，无需挂载任何繁重的第三方监控组件（如 Prometheus / Grafana）。

此外，它还支持多租户安全隔离，且支持提供结构化 JSON 数据供第三方抓取。

---

## 1. 最小配置

你只需要在路由的 `action` 中将类型指定为 `status`，即可在对应路径上启用状态面板：

```yaml
routes:
  - name: "system-status"
    match:
      path: "/status"
    action:
      type: "status" # Set type to status
```

访问该路由路径（如 `http://example.com/status`）即可看到系统状态仪表盘。

---

## 2. 配置字段说明

`status` Action 提供了丰富的自定义参数，允许你定制看板的标题、可见范围、模板以及是否展示后端实例等：

```yaml
action:
  type: "status"
  title: "LiteGate Platform Status" # Custom dashboard title
  host: "self"                     # "self" to filter by current host, or "*" for all sites
  show_instances: false            # Whether to render detailed backend physical instances
  template: "./site/status.html"   # Optional path to a custom template
  template_root: "./site"          # Optional path to template partials root
  template_debug: false            # Enable debug mode (reload template every request)
  template_production: true        # Enable production mode (cache compiled template)
```

| 字段 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `title` | string | `"LiteGate System Status"` | 自定义状态页面顶部展示的系统大标题。 |
| `host` | string | `"self"` | 配置要监控展示的站点域名。设为 `"self"` 或留空时仅展示当前被访问域名（站点）的健康指标，常用于多租户网关的安全隔离；也可设为特定的域名（如 `"api.example.com"`）；设为 `"all"` 或 `"*"` 则展示网关内所有静态与动态发现站点的全局监控。 |
| `show_instances` | bool | `false` | 是否在代理路由监控下，进一步渲染并展示底层的物理服务发现实例节点列表及健康状况（支持 Litemesh/Consul 实例发现）。 |
| `template` | string | `""` | 可选。自定义状态页面的 HTML 模板文件路径。若留空，则展示网关内置的高性能、美观的 AI/Glassmorphism 风格监控仪表盘。 |
| `template_root` | string | `""` | 可选。用于模板组合复用时的片段扫描根目录（类似于 `template` action 的用法）。 |
| `template_debug` | bool | `false` | 是否开启模板调试模式（开启后不缓存模板，每次请求重新从磁盘读取，适合开发期调试）。 |
| `template_production`| bool | `true` | 是否开启模板缓存生产模式（开启后预编译模板，避免重复磁盘 I/O，极大地提升渲染并发性能）。 |
| `template_kv_mode` | bool | `false` | 是否从 litemesh / Consul KV 分布式加载自定义模板（而非本地磁盘），详见下方「分布式自定义模板」。 |
| `template_kv_provider` | string | `""` | KV 提供方：`litemesh` 或 `consul`。 |
| `template_kv_prefix` | string | `""` | 模板片段在 KV 中的前缀；此时 `template` 字段填相对该前缀的主模板 key 后缀。 |
| `template_kv_namespace` | string | `""` | 可选，多租户 KV namespace 隔离；留空用客户端默认 namespace。 |

### 📦 分布式自定义模板（`template_kv_mode`）

状态页的自定义模板与 [`template` action](./template.md) 共用同一套加载引擎，因此**同样支持从 litemesh / Consul KV 分布式加载**：模板内容存在 KV 里，多节点无需本地分发文件，纯内存编译、KV 变更热更新、拉取失败自动回退上一份缓存。

```yaml
action:
  type: "status"
  title: "LiteGate Platform Status"
  host: "self"
  template_kv_mode: true
  template_kv_provider: "litemesh"
  template_kv_prefix: "litegate/tmpl/status-a/"
  template: "status.html"   # 相对 prefix 的主模板 key 后缀
```

资源边界（≤100 片段 / 单片段 ≤1MB / 总量 ≤10MB）与安全提示（KV 写入权限视同代码部署权限）同 `template` action；KV 模式下 `{{ markdown "x.md" }}` 的文件加载形式不可用（仅支持内联）。

---

## 3. 多租户安全隔离 (`host: "self"`)

在多租户网关的部署场景中，你可能不希望 A 域名的访问者通过 `/status` 查看到 B 域名的后端和流量数据。
通过将 `host` 配置为 `"self"`：
- 网关会在请求到达时，动态解析 HTTP 请求的 `Host` 字段。
- 面板上将**仅展示当前域名**所关联的流量曲线、延迟分布、路由健康度。
- 其他站点的监控数据将被静默隐藏，实现零信任安全隔离。

---

## 4. 后端实例可见性 (`show_instances: true`)

当你的路由动作类型为 `proxy`，并且使用了动态服务发现（如 Consul 或 Litemesh）时，每个路由下面会有多个底层的物理容器或虚拟机实例（IP+Port）。
- 默认情况下，公开状态页仅展示路由（Route）级别的平均指标，以保护后端物理拓扑不被泄露。
- 如果将 `show_instances` 显式设为 `true`，状态页的路由监控面板下将会展开展示出**每个活跃的后端物理节点**，并呈现其健康检查状态、独立的实时延迟、以及最近的请求采样列表，非常适合用于集群内部的排障和诊断看板。

---

## 5. 自动 JSON 协商接口 (JSON API Mode)

`status` 页面本身支持高可用的内容协商。当网关检测到以下任意一种请求方式时，它不会渲染 HTML 网页，而是直接返回 **200 OK + `application/json`** 的结构化监控指标数据：
1. 请求 URL 带有 Query 参数 `?format=json`，例如：`/status?format=json`
2. 请求头中包含了 `Accept: application/json`

这非常方便第三方监控系统（例如 Zabbix, PromQL 抓取器）来拉取指标，或者用来开发自定义的监控大屏。

### 响应 JSON 示例结构：
```json
[
  {
    "domain": "api.example.com",
    "domain_id": "api_example_com",
    "title": "LiteGate API Gateway",
    "status": "Operational",
    "total_requests": 158249,
    "daily_requests": 1240,
    "error_requests": 2,
    "latency_avg": 12.5,
    "status_dist": {
      "200": 1238,
      "502": 2
    },
    "routes": [
      {
        "route_name": "get-users",
        "requests": 980,
        "errors": 0,
        "latency": 8.4
      }
    ]
  }
]
```

---

## 通过服务标签自动启用

除了手写 site 配置，也可在 Router 上设置 `litegate.http.routers.<name>.observability.status.enabled=true`，并可用 `.path` 和 `.showinstances` 调整状态页。详见 [服务标签参考](../03-configuration/tag-reference.md)。标签方式仅覆盖快速启用；自定义标题 / `host: self` / 自定义模板请仍用本文档的手写配置。

---

## 延伸阅读
- [Template 渲染 Action](./template.md)
- [服务注册指南（标签自动建路由）](../../service_registration_guide.md)
- [Metrics 指标监控](../08-observability/metrics.md)
- [Dashboard 观测面板](../08-observability/dashboard.md)
