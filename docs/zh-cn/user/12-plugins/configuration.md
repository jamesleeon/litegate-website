# 插件使用与配置参考

编译入 LiteGate 二进制的插件，在使用体验上与官方内置功能**完全一致**。
你可以直接在 `config.yaml` 全局配置或 `sites/*.yaml` 站点配置中声明插件名称，网关的配置加载器会自动识别、解析并执行纯配置校验。

---

## 插件配置分类速查

| 插件扩展点 | 配置位置 | 关键声明字段 |
| :--- | :--- | :--- |
| **Action** | `sites/*.yaml` 路由定义 | `action.type: "<plugin_name>"`，其余私有参数内联声明 |
| **Middleware** | `sites/*.yaml` 站点或路由 | `middlewares: { <instance>: { type: "<plugin_name>", config: {...} } }`，路由通过 `middlewares: [<instance>]` 引用 |
| **LoadBalancer** | `sites/*.yaml` 路由定义 | `action.lb_policy: "<plugin_name>"` |
| **KV Provider** | `sites/*.yaml` 路由定义 | `action.kv_provider: "<plugin_name>"`, `action.kv_key: "..."` |
| **Ingress** | `config.yaml` 全局配置 | `ingress_plugins: [{ name: "...", type: "<plugin_name>", ... }]` |
| **Discovery** | `config.yaml` 全局配置 | `service_discovery.catalogs: [{ provider: "<plugin_name>", ... }]` |
| **DNS Provider** | `config.yaml` 全局配置 | `auto_cert.dns.provider: "<name>"`, `ddns.provider: "<name>"` |
| **IDS Provider** | `sites/*.yaml` 路由定义 | `action.ids.provider: "<plugin_name>"` |
| **Template Func** | HTML 模板源码文件 | 模板中直接调用注册的函数名，如 `{{ maskPhone .User.Phone }}` |

---

## 1. Action 插件配置

Action 插件用于终结请求并产出响应。在路由项中通过 `action.type` 引用插件名，其余非核心字段会自动作为该插件的私有参数传递给插件的 `ActionConfig`：

```yaml
# sites/api-site.yaml
domain: api.example.com
port: 443

routes:
  # 场景 A: 使用标准内置的 NATS Action 插件
  - name: publish-order-event
    match:
      path: /v1/events/order
      method: [POST]
    action:
      type: nats                     # 插件注册的名称
      url: "nats://127.0.0.1:4222"   # 插件私有参数
      subject: "orders.created"
      mode: "request_reply"          # 支持 publish 或 request_reply
      timeout_ms: 3000
      jetstream: true

  # 场景 B: 使用自定义的 AI 网关代理插件
  - name: llm-chat-proxy
    match:
      path_prefix: /v1/chat/completions
    action:
      type: llm_proxy                # 自定义 Action 插件名
      model: "gpt-4o"
      token_budget_per_min: 100000
      upstream_endpoint: "https://api.openai.com"
```

> [!TIP]
> Action 插件推荐提供 `Validate` 函数。若你在 YAML 中少填了必填项或类型写错，在启动执行 `litegate -t` 或热加载时就会被直接拦截并报错，绝不会拖延到请求到达时才报错。

---

## 2. Middleware 插件配置

Middleware 插件穿透加工 HTTP 请求链。在 Site 级别定义具名中间件，再通过各条 Route 的 `middlewares` 列表引用；定义本身不会自动应用到所有路由：

```yaml
# sites/app.yaml
domain: app.example.com
port: 443

# 1. 站点级中间件定义（供路由引用）
middlewares:
  enterprise_trace:
    type: custom_trace_id
    config:
      header_name: "X-Enterprise-Trace-ID"
      generate_uuid: true
  finance_auth:
    type: custom_jwt_validator
    config:
      issuer: "https://auth.company.internal"
      audience: "finance-api"

routes:
  - name: sensitive-data
    match:
      path_prefix: /api/finance/
    # 2. 路由级中间件（仅对当前路由生效）
    middlewares: [enterprise_trace, finance_auth]
    action:
      type: proxy
      upstream: ["10.0.10.50:8080"]
```

Middleware V2 会自动根据插件自身声明的 Stage（如 `Security`、`TrafficControl`、`RequestTransform` 等）以及 Priority 自动插入到最优执行流水线中，无需运维人员手动调谐物理先后顺序。

---

## 3. Ingress 入口拦截插件配置

Ingress 插件工作在 EntryPoint 共享端口入口层，能够在**站点域名路由与 URL 规范化之前**接管连接与请求。常用于 HTTP CONNECT 正向代理、特殊协议多路复用等场景。

在全局主配置文件 `config.yaml` 中声明：

```yaml
# config.yaml
entrypoints:
  web:
    address: ":80"
  websecure:
    address: ":443"

ingress_plugins:
  - name: enterprise-forward-proxy
    type: forward_proxy            # 插件类型名 (如 LiteGate 内置的正向代理)
    entrypoints: [websecure]       # 绑定到指定的入口点
    config:
      probe_resistance: true       # 防主动嗅探保护
      allowed_ports: [80, 443, 8443]
      allowed_destinations:
        - "*.internal.corp"
        - "api.github.com"
      username: ops_user
      password_env: LITEGATE_PROXY_PASSWORD  # 环境变量中存放代理密码
```

---

## 4. Discovery Provider 服务发现源配置

若你的服务注册在 Nacos、Eureka、Zookeeper 或企业自研 CMDB 中，编写 Discovery 插件后，在 `config.yaml` 的 `service_discovery.catalogs` 下挂载该源：

```yaml
# config.yaml
service_discovery:
  catalogs:
    - name: nacos-prod
      enabled: true
      provider: custom_nacos       # 插件注册的 Discovery 名称
      config:
        sync_interval: "15s"       # 自定义插件实现并解析的轮询间隔
        server_addr: "10.0.1.10:8848"
        namespace_id: "production"
        group: "DEFAULT_GROUP"
```

挂载完成后，LiteGate 的动态路由与上游健康池就可以像原生支持 Consul/Litemesh 一样直接消费发现出的服务列表和 Endpoint。

---

## 5. DNS Provider 插件配置 (证书 DNS-01 与 DDNS)

DNS Provider 插件能够接管 Let's Encrypt 证书申请时的 DNS-01 质询记录写入，以及公网动态 DDNS 同步：

```yaml
# config.yaml
auto_cert:
  enabled: true
  email: "admin@example.com"
  dns:
    provider: my_internal_dns      # 插件注册的 DNS Provider 名称
    propagation_timeout: 120s
    config:
      api_key: "secret-token-here"
      nameserver: "192.168.1.1"

# 若插件实现了 DDNSProvider 接口，还可直接用于 DDNS
ddns:
  enabled: true
  provider: my_internal_dns
  domain: "gateway.office.corp"
  interval: 5m
```

---

## 6. IDS Provider 安全治理插件配置

IDS 插件在路由匹配后、Action 执行前执行统一安全判定（如企业签名校验、风控评分、金丝雀分流标签下发等）：

```yaml
# sites/payment.yaml
domain: payment.example.com
port: 443

routes:
  - name: charge
    match:
      path: /v1/charge
    action:
      type: proxy
      upstream: ["payment-backend:8080"]
      ids:
        provider: openapi_md5      # 插件注册的 IDS 名称
        fail_policy: deny          # 判定失败策略: deny (直接阻断) 或 allow (降级放行)
        options:
          secret_key: "k9#zL@2!0xM"
          timestamp_tolerance_sec: 300
```

---

## 7. LoadBalancer 与 KV Provider 插件配置

### A. LoadBalancer 负载均衡算法
```yaml
routes:
  - name: dynamic-lb-route
    match:
      path_prefix: /api
    action:
      type: proxy
      service_name: order-service
      lb_policy: least_latency     # 注册的自定义 LoadBalancer 插件名
```

### B. KV Provider 动态热内容
```yaml
routes:
  - name: dynamic-template-page
    match:
      path: /dashboard
    action:
      type: template
      kv_provider: redis_kv        # 注册的 KV Provider 插件名
      kv_key: "cms:pages:dashboard.html"
```

---

## 8. 全局扩展插件绑定配置 (extension_plugins)

LiteGate 支持通过统一的 `extension_plugins` 数组在全局 `config.yaml` 中绑定实例。支持 8 种企业级扩展能力：

```yaml
# config.yaml
extension_plugins:
  # 1. L4 TCP/UDP 传输层插件
  - kind: stream
    name: redis_guard
    type: redis_readonly          # 插件注册名 (RegisterStream)
    config:
      allowed_commands: [GET, MGET, PING]

  # 2. 响应流 / Body 变换插件 (脱敏、注入)
  - kind: response_filter
    name: pii_masker
    type: pii_filter              # 插件注册名 (RegisterResponseFilter)
    config:
      mask_idcard: true

  # 3. 异步日志/链路导出 (推送到 Kafka/Loki/OTLP)
  - kind: access_log_exporter
    name: kafka_audit
    type: kafka_producer          # 插件注册名 (RegisterAccessLogExporter)
    config:
      brokers: ["10.0.0.1:9092"]
      topic: "gateway-access-log"

  # 4. 企业私有 CA 证书签发 (对接 Vault / 私有 PKI)
  - kind: cert_issuer
    name: internal_vault
    type: vault_ca                # 插件注册名 (RegisterCertIssuer)
    config:
      vault_addr: "https://vault.internal:8200"

  # 5. 上游传输定制 (自定义双向 mTLS / 连接池)
  - kind: upstream_transport
    name: enterprise_mtls
    type: mtls_transport          # 插件注册名 (RegisterUpstreamTransport)
    config:
      client_cert: "/certs/client.pem"
      client_key: "/certs/client.key"
```

### 如何在路由和 Stream 中引用这些扩展：

```yaml
# sites/secure-api.yaml
# 1. 站点路由引用 Response Filter 和 Upstream Transport:
domain: api.example.com
routes:
  - name: secure-api
    match: { path_prefix: /api/ }
    action:
      type: proxy
      upstream: ["internal-service:8080"]
      upstream_transport: enterprise_mtls  # 引用 extension_plugins 中的 name
      response_filters: [pii_masker]       # 引用 extension_plugins 中的 name
```

**L4 Stream 配置**：

```yaml
# streams/redis-proxy.yaml
# 2. L4 Stream 引用 Stream 插件:
name: redis-proxy
port: 6379
protocol: tcp
plugin_handler: redis_guard                # 引用 extension_plugins 中的 name
```

**全局证书配置**：

```yaml
# config.yaml
# 3. 自动证书申请引用私有 CA:
auto_cert:
  issuer: internal_vault                   # 引用 extension_plugins 中的 name
```

---

## 常见配置报错与排查

1. **`action type "xxx" is not compiled into this binary`**
   - **原因**：YAML 中引用的插件名称未成功编入当前二进制，或者拼写大小写不一致。
   - **排查**：运行 `litegate plugins list` 查看当前二进制支持的插件名称；检查 `cmd/litegate/plugins.go` 或 `litegate build` 参数。
2. **`unsupported plugin manifest kind "xxx"`**
   - **原因**：插件注册 Manifest 时填写的 Kind 类型不合法。合法的 Kind 包括：`action`、`middleware`、`load_balancer`、`kv`、`dns`、`ids`、`discovery`、`ingress`、`template_func`、`stream`、`response_filter`、`access_log_exporter`、`trace_exporter`、`metrics_exporter`、`cert_issuer`、`upstream_transport`、`config_source`。
3. **加载期校验错误：`config validation failed`**
   - **原因**：插件的 `Validate` 函数检测到了必填项缺失、数值越界或不合法配置。请检查终端打印的具体报错定位修正 YAML。
