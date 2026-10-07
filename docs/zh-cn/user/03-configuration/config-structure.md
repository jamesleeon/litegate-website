# 配置结构总览与最佳实践

本文把 LiteGate 的配置从整体讲清楚：有哪些配置文件、每个文件的层级结构、每一层负责什么，以及怎样组织配置更合理。

逐个字段的说明请查参考手册：[全局配置](global-config.md)、[站点配置](site-config.md)、[命名 Service](services.md)、[服务标签](tag-reference.md)。

---

## 1. 配置从哪里来

LiteGate 的配置分三类来源，各管一件事：

| 来源 | 位置 | 负责什么 | 谁来写 |
|---|---|---|---|
| **全局配置** | `config.yaml` | 网关进程本身：监听哪些端口、证书、从哪里发现服务、日志与监控、安全信任边界 | 网关运维 |
| **站点配置** | `sites/*.yaml` | 每个域名的路由：请求去哪里、经过哪些处理、由谁响应 | 网关运维 / 业务团队 |
| **服务标签** | 注册到 Consul / LiteMesh / Docker / K8s 的服务上 | 服务自己声明“我要暴露在哪个域名、哪个路径” | 业务服务自己 |

另外还有 `streams/*.yaml`，用于 TCP/UDP 四层转发，见 [Stream 配置](stream-config.md)。

典型目录布局：

```text
litegate/
├── config.yaml              # 全局配置（一个）
├── sites/                   # 站点配置（每个站点一个文件）
│   ├── www.example.com.yaml
│   ├── api.example.com.yaml
│   └── blog.example.com.yaml
├── streams/                 # 四层转发（可选）
└── certs/                   # 证书目录（自动证书或自定义证书）
```

**怎么选：**

*   固定不变的入口、证书、安全设置 → `config.yaml`。
*   由网关统一管理的域名和路由 → `sites/*.yaml`。
*   服务数量多、上下线频繁、希望服务自己声明路由 → 服务标签。
*   站点配置与服务标签可以作用于同一个域名：例如 `sites/` 里用 `serve` 托管前端，后端服务用标签声明 `/api`。二者会合并为一个站点。

---

## 2. 全局配置 `config.yaml`

### 2.1 结构

```text
config.yaml
├── mode                  运行模式：observability（默认）/ performance
├── entrypoints           监听入口：名字 → 地址、是否 TLS
├── http                  兼容旧写法的端口与超时（有 entrypoints 时以 entrypoints 为准）
├── tls / auto_cert       静态证书 / 自动申请证书
├── sites_dir             站点配置目录
├── streams_dir           四层转发配置目录
├── consul / litemesh     配置中心或注册中心的连接（可选）
├── service_discovery     服务发现来源 catalogs、标签可开的端口
├── real_ip               可信代理：决定客户端真实 IP 从哪里取
├── ip_restriction        全局 IP 白名单 / 黑名单
├── scan_protection       扫描防护
├── auth_providers        OIDC / OAuth2 身份提供方（供路由引用）
├── dashboard / metrics / pprof / mcp    管理与监控端口
├── log / tracing         日志、访问日志、链路追踪
└── passive_health / cache / redis / ... 其他运行参数
```

按职责可以分成五组：

| 组 | 字段 | 说明 |
|---|---|---|
| 入口 | `entrypoints`、`http` | 网关监听哪些端口。站点和路由通过入口名引用它们 |
| 证书 | `tls`、`auto_cert` | HTTPS 证书从哪里来 |
| 配置来源 | `sites_dir`、`streams_dir`、`consul`、`litemesh`、`service_discovery` | 站点配置和服务从哪里读取 |
| 安全边界 | `real_ip`、`ip_restriction`、`scan_protection`、`auth_providers` | 信任谁、拒绝谁 |
| 运维 | `dashboard`、`metrics`、`mcp`、`log`、`tracing` | 管理与观测 |

### 2.2 推荐的生产配置

```yaml
mode: observability

# 入口：名字供站点和标签引用；默认使用 web / websecure
entrypoints:
  web:
    address: ":80"
  websecure:
    address: ":443"
    tls: true

sites_dir: "./sites"
streams_dir: "./streams"

# 自动证书：确认域名解析和 80 端口可达后再开启
auto_cert:
  enabled: true
  email: "ops@example.com"
  certs_dir: "./certs"
  default_challenge: "http"

# 网关前面还有负载均衡时必须配置，否则客户端 IP 取到的是负载均衡的地址
real_ip:
  trusted_proxies:
    - "10.0.0.0/8"

# 服务发现：只打开实际使用的来源
service_discovery:
  catalogs:
    - enabled: true
      provider: "consul"
      url: "127.0.0.1:8500"
  tag_entrypoints:
    allowed_ports: []        # 默认不允许服务标签新开端口

dashboard:
  enabled: true
  port: 9999
  username: "admin"
  password: "$2a$10$..."     # 用 `litegate -hash <密码>` 生成，不要写明文

log:
  level: "info"
  format: "json"             # 生产环境便于日志系统解析
  access_log:
    enabled: true
    stdout: true
```

几点说明：

*   **入口名是站点与全局配置之间的契约。** 站点的 `entrypoints`、服务标签的 `entrypoints` 都引用这里的名字。新增内部管理端口时，新建一个入口（如 `internal: { address: ":8080" }`），不要改动 `web` / `websecure`。
*   **`real_ip.trusted_proxies` 只列前置代理的地址。** 列得过宽会让任何人都能伪造 `X-Forwarded-For`，从而绕过 IP 限制和限流。
*   **服务发现只开需要的来源。** 每个启用的来源都会定期扫描。
*   **`tag_entrypoints.allowed_ports` 默认留空。** 服务标签只能挂到已有入口上，不能自行打开新端口。

---

## 3. 站点配置 `sites/*.yaml`

### 3.1 写法

新站点统一使用顶层 `site:` 的 v2 写法。简单站点几行即可，需要更多功能时在同一个文件里继续加字段，不用换格式（完整说明见 [站点配置](site-config.md) 第 0 节）：

```yaml
site: blog.example.com
/api: 127.0.0.1:8080
spa: /var/www/blog
```

旧的 `domain:` 标准格式和 `.lite.yaml` 文件仍然可以正常加载，无需迁移。v2 会编译成与旧标准格式相同的内部模型，下文按这个内部模型讲解各层的职责；v2 中对应的字段名（如 `site`、`https`、`transports`、`use`）见 [站点配置](site-config.md) 第 0 节。

### 3.2 结构

一个站点文件分两部分：**上面是定义区，下面是使用区**。定义区给可复用的东西起名字，使用区的路由按名字引用它们。

```text
site.yaml
│
├── domain                 站点域名（必填）
├── entrypoints            挂在哪些入口上（缺省为全部入口）
├── force_https            HTTP 自动跳转 HTTPS
├── tls                    本站点自定义证书（可选）
├── ip_restriction         站点级 IP 规则（对所有路由生效）
├── max_request_body_size / error_pages / defaults   站点级默认值
│
│ ── 定义区：起名字，供路由引用 ──
├── serverstransports      上游传输方式（TLS / mTLS）
├── services               后端：怎么到达（发现、负载均衡、超时、重试、熔断）
├── middlewares            中间件：进出时做什么（CORS、鉴权、限流 ……）
│
│ ── 使用区 ──
└── routes[]               路由列表
    ├── name               路由名（出现在日志、Dashboard、执行链中）
    ├── priority           显式优先级（一般不需要）
    ├── match              去哪里：path / path_prefix / rule / method / header / query
    ├── ip_restriction     本路由的 IP 规则
    ├── middlewares        引用定义区的中间件名，按阶段执行
    └── action             谁来响应
        ├── type           proxy / serve / template / respond / redirect / webdav / list / markdown / status
        ├── service        (proxy) 引用定义区的 Service
        ├── 本类型字段      如 serve 的 root / spa，respond 的 status / body
        └── 通用字段        strip_prefix、headers、res_headers、log_level、on_error
```

**引用关系：**

```text
routes[].middlewares  ──按名字引用──▶  middlewares
routes[].action.service ──按名字引用──▶ services ──引用──▶ serverstransports
entrypoints            ──按名字引用──▶  config.yaml 的 entrypoints
```

所有引用都在加载时检查，引用了不存在的名字会直接加载失败，不会带病上线。

### 3.3 一个完整的站点

下面是一个常见形态：前端静态页面 + 多个 API 后端 + 旧接口跳转。

```yaml
domain: shop.example.com
force_https: true

# ── 定义区 ─────────────────────────────────────────────

serverstransports:
  mesh:
    tls:
      enabled: true
      clientcertificate: litemesh     # 与后端双向 TLS

services:
  orders:                             # 通过服务发现找到实例
    discovery:
      name: orders
    timeout: 10s
    loadbalancer:
      strategy: least_conn
      serverstransport: mesh
    healthcheck: { path: /health, interval: 10s }
    retry: { attempts: 2 }
    circuitbreaker: { enabled: true, tripthreshold: 5 }

  payments:
    discovery:
      name: payments
      selector:
        match: { env: prod }          # 只选生产实例
    timeout: 30s                      # 支付回调慢，单独放宽
    loadbalancer: { strategy: round_robin }

  legacy-cms:                         # 没有接入服务发现的老系统
    servers: ["http://10.0.3.21:8080", "http://10.0.3.22:8080"]
    timeout: 5s

middlewares:
  api-limit:
    type: ratelimit
    config:
      qps: "200"
  api-auth:
    type: jwt_auth
    config:
      jwks_url: "https://auth.example.com/.well-known/jwks.json"
  api-common:                         # 把常用组合打包，路由只引用一个名字
    type: chain
    config:
      middlewares: "api-limit,api-auth"

# ── 使用区 ─────────────────────────────────────────────

routes:
  - name: orders-api
    match: { path_prefix: /api/orders }
    middlewares: [api-common]
    action:
      service: orders
      strip_prefix: /api

  - name: payments-callback           # 第三方回调：不走 JWT，只限流
    match: { path: /api/payments/callback, method: [POST] }
    middlewares: [api-limit]
    action:
      service: payments
      strip_prefix: /api

  - name: payments-api
    match: { path_prefix: /api/payments }
    middlewares: [api-common]
    action:
      service: payments
      strip_prefix: /api

  - name: cms
    match: { path_prefix: /cms }
    action:
      service: legacy-cms

  - name: old-help                    # 旧地址永久跳转
    match: { path_prefix: /help }
    action:
      type: redirect
      location: "https://help.example.com/"
      status: 301

  - name: frontend                    # 兜底：单页应用
    match: { path_prefix: / }
    action:
      type: serve
      root: /var/www/shop
      spa: true
      compress: true
```

这份配置的组织思路：

*   **后端只定义一次。** `payments` 被两条路由使用，超时、负载均衡只写在 Service 里，两条路由共享健康状态和熔断状态。
*   **中间件按用途命名，常用组合用 `chain` 打包。** 新增 API 路由只需要写 `middlewares: [api-common]`。
*   **前端和 API 同域。** 浏览器看到的是同一个来源，调用 `/api/...` 不需要 CORS。
*   **特殊路由写得更具体。** 支付回调用精确路径 `path`，自然优先于 `/api/payments` 前缀。
*   **兜底路由是 `/`。** 最长前缀匹配保证它只接住其他路由都不匹配的请求。

---

## 4. 路由匹配

### 4.1 `match` 字段

| 字段 | 含义 | 示例 |
|---|---|---|
| `path` | 精确路径 | `path: /login` |
| `path_prefix` | 路径前缀 | `path_prefix: /api` |
| `method` | 方法列表 | `method: [GET, POST]` |
| `header` | 请求头等值匹配 | `header: { X-Tenant: acme }` |
| `query` | 查询参数等值匹配 | `query: { version: "2" }` |
| `rule` | 规则表达式，与上面几项互斥 | `rule: 'PathPrefix("/api") && Method("GET")'` |

注意：YAML 中是单数的 **`method` / `header` / `query`**。Dashboard 和 JSON 接口显示为复数形式，写 YAML 时不要照抄。

### 4.2 优先级

多条路由都能匹配时，按以下顺序决定：

1.  `priority` 数值大的优先。
2.  精确路径 `path` 优先于前缀。
3.  前缀越长越优先（最长前缀匹配）。
4.  站点文件中的路由优先于服务标签产生的路由（仅在前三项都相同时）。
5.  仍然相同时，按文件中的书写顺序。

一般不需要写 `priority`，靠路径的具体程度就能得到正确结果。只有在路径相同、需要靠 `method` / `header` 区分，又想明确先后时才使用。

**注意：** 服务标签产生的路由如果使用了更高的 `priority` 或更具体的路径，可以覆盖同域名下站点文件中的路由（例如声明 `/login`）。因此，只有可信的服务才应该被允许注册到服务发现中。

---

## 5. 一个能力写在哪里

同一个需求可能有多种写法。下面是推荐的归属：

| 需求 | 推荐写在 | 不推荐 |
|---|---|---|
| 后端地址、负载均衡、超时 | `services` | 多条路由重复写 `service_name` / `timeout` |
| 重试、熔断、健康检查 | `services` | `retry` / `circuit_breaker` 中间件（已弃用） |
| 上游 TLS / mTLS | `serverstransports` | 每条路由写 `mtls` / `insecure_skip_verify` |
| CORS、鉴权、限流、IP 限制 | `middlewares`，路由引用 | 每条路由各写一份内联配置 |
| 只有一条路由用的简单设置 | action 内联字段（如 `compress: true`） | 为它单独定义一个中间件 |
| 路径改写 | `strip_prefix`（简单去前缀）或 `rewrite`（正则） | 后端再做一次路径兼容 |
| 站点级 IP 规则 | 站点 `ip_restriction` | 每条路由重复写 |
| 全局 IP 黑名单 | `config.yaml` 的 `ip_restriction` | 每个站点重复写 |

判断方法见 [命名 Service 与配置分层](services.md) 第 1 节：**需要知道后端的写在 Service，不需要知道后端的写成中间件。**

中间件无论以什么顺序写在 `middlewares` 列表里，都按固定阶段执行：预检（CORS）→ 请求改写 → 安全检查（IP、WAF）→ 流量控制（限流）→ 鉴权 → 鉴权后处理（镜像）→ 响应处理（压缩、缓存）。所以不用担心“限流写在鉴权前面还是后面”。同一阶段内先按中间件类型的固有顺序，类型顺序相同时再按书写顺序。

---

## 6. 推荐做法

**文件组织**

*   **一个站点一个文件，文件名用域名。** 排查问题时看文件名就能找到配置。一个文件里可以用 `---` 分隔写多个站点，但不利于维护。
*   **定义区在上，路由在下。** 读配置时先看到有哪些后端和中间件，再看路由怎么组合它们。
*   **每条路由都写 `name`。** 路由名会出现在访问日志、Dashboard 和执行链里，没有名字的路由很难排查。

**后端**

*   **同一个后端被多条路由使用时，一定用 Service。** 否则调整超时要改多处，漏改一处就会出现同一后端行为不一致。
*   **超时按后端设置，而不是按路由。** 慢接口单独定义一个 Service（像上面的 `payments`）。
*   **重试只对幂等请求开启。** 默认只重试幂等方法；不要把 POST 加进 `retry_methods`，除非后端保证幂等。

**中间件**

*   **按用途命名**，如 `api-limit`、`web-cors`、`admin-auth`，不要用 `mw1`。
*   **常用组合用 `chain`。** 统一调整一组路由的安全策略时只改一处。
*   **能同域就同域。** 前端和 API 放在同一个域名下，就不需要 CORS。确实需要跨域时，`allowed_origins` 写明确的来源，不要写 `*` 再开启凭证（会加载失败）。

**安全**

*   **网关在负载均衡后面时，必须配置 `real_ip.trusted_proxies`。**
*   **Dashboard 密码用 `litegate -hash` 生成的哈希**，Dashboard 端口不要暴露到公网。
*   **管理类路由加 `ip_restriction`**，只允许内网访问。
*   **`tag_entrypoints.allowed_ports` 按需逐个放开**，不要为了方便放开一整段端口。

**上线验证**

*   启动日志里没有 error，也没有弃用警告。
*   在 Dashboard 查看每条关键路由的执行链：`GET /api/routing/pipeline?site=<域名>&route=<路由名>`，确认中间件的顺序和来源符合预期。

---

## 7. 常见误区

| 误区 | 问题 | 正确做法 |
|---|---|---|
| 写 `methods: [GET]` | YAML 键是单数 `method`，会被拒绝 | `method: [GET]` |
| action 的 `timeout: 5s` | action 内联的 `timeout` 是整数秒 | 内联写 `timeout: 5`；Service 中写 `timeout: 5s` |
| Service 中写 `max_requests` | Service 键名沿用标签写法 | `maxrequests`、`tripthreshold` |
| 引用了 Service 又写 `timeout` / `retry` | 一条路由的后端只能有一个配置来源，加载失败 | 改在 Service 中配置 |
| `allowed_origins: "*"` 加 `allow_credentials: true` | 任何网站都能以用户身份读取接口，加载失败 | 列出可信来源 |
| 前端和 API 不同域，然后到处加 CORS | 配置复杂，容易出错 | 同域部署，用路径区分 |
| 在后端和网关都配 CORS | 两处策略可能不一致，排查时不清楚以谁为准 | 网关配置了 CORS 后由网关接管这些头；二选一即可 |
| 兜底路由 `/` 写了 `priority` | 会压过更具体的路由 | 兜底路由不写 `priority` |
| `retry` 中间件 | 已弃用 | `services.<name>.retry.attempts` |

---

## 延伸阅读

- [全局配置参考](global-config.md)
- [站点配置参考](site-config.md)
- [命名 Service 与配置分层](services.md)
- [服务标签使用指南](tag-dsl.md)
- [Middleware Pipeline、Chain 与命名能力](../05-middleware/pipeline.md)
- [路由优先级](../02-concepts/routing-priority.md)
