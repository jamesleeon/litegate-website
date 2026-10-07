# 两层路由：先切上游，再改路径（疑难杂症速查）

如果你之前只用过 `path:` 模式做转发，那你只用到了 LiteGate 路由能力的一小半。把 **`rule:` 匹配** 和 **`rewrite` 改写** 组合起来，绝大多数"网关层疑难杂症"都能用同一套思路解决。这篇文档先讲清心智模型，再给一串可直接复制的配方。

---

## 1. 心智模型：两件正交的事

网关处理一个请求，本质上就问两个问题：

```
                进来一个请求
                     │
        ┌────────────┴────────────┐
        │  第 1 层：切上游（分发）  │   ← match / rule 决定
        │  “这个请求该给哪个后端？” │      按 host/path/query/header/IP/method
        └────────────┬────────────┘         的任意布尔组合命中某条 route
                     │
        ┌────────────┴────────────┐
        │  第 2 层：改路径（适配）  │   ← rewrite 决定
        │  “后端认识这个 URL 吗？”  │      命中之后把 path/query 改成后端要的样子
        └────────────┬────────────┘
                     │
                转发给上游
```

| 层 | 配置项 | 职责 | 决定什么 |
| --- | --- | --- | --- |
| 第 1 层 | `match`（`path` 或 `rule`） | **分发** | 命中哪条 route → 哪个 `upstream` |
| 第 2 层 | `rewrite` / `strip_prefix` | **适配** | 命中之后把 path/query 改成后端期望的形式 |

**两条铁律**：

1. **切上游永远是第 1 层（match）的事**，不是 rewrite 的事。
2. **`rewrite` 只在命中的这条 route 内改路径，不会重新回到路由表匹配**（区别于 Nginx `rewrite ... last`）。

一旦按这两层去想，你会发现很多以前要靠 Nginx `if` + `rewrite ... last` 硬凑的场景，在这里都是"写一条带条件的 route + 可选的一段 rewrite"。

---

## 2. 为什么 `path:` 不够，`rule:` 解锁了什么

`path:` / `path_prefix:` 只能按 URL 路径分发。而 `rule:` 是一套布尔表达式 DSL，能按**任意维度组合**分发：

- **Host**：`Host`、`HostRegexp`
- **Path**：`Path`、`PathPrefix`、`PathSuffix`、`PathRegex`
- **Query**：`Query`、`QueryPrefix` / `QueryIPrefix`、`QuerySuffix` / `QueryISuffix`、`QueryRegex`
- **Header**：`Header`、`HeaderRegexp`、`HeaderPrefix` / `HeaderIPrefix`、`HeaderSuffix` / `HeaderISuffix`
- **Cookie**：`Cookie`、`CookieRegex`、`CookiePrefix` / `CookieIPrefix`、`CookieSuffix` / `CookieISuffix`
- **来源 / 方法**：`ClientIP`（支持 CIDR）、`Method`

> `Header`、`Query`、`Cookie` 都支持只传 1 个参数做**存在性判断**（如 `Cookie("session")` 表示带了该 cookie 即命中）。参与**值**匹配的 query / cookie 必须是单值，重复出现（同名多次）不会命中，避免网关与后端取到不同值。
- **逻辑组合**：`&&`、`||`、`!`、括号分组

> 完整语义见 [规则表达式 Rule DSL 参考](../03-configuration/site-config.md#9-规则表达式-rule-dsl-参考)。

**性能提示**：只有一条路由、路径不重叠时，继续用 `path:` 最快（走 O(1) 精确匹配）。只有当**多条路由落在同一路径、靠附加条件区分**时，才需要 `rule:`——而且这种情况下**这些路由要全部用 `rule:`**（原因见 [第 4 节陷阱](#4-边界与陷阱)）。

---

## 3. 疑难杂症速查（Cookbook）

每个配方的套路都一样：**第 1 层用 match 选后端，第 2 层按需 rewrite 改路径**。

### 3.1 一个 OAuth 回调地址，分给多个后端

平台只让填一个回调 URL，但要按 `state` 前缀分给主/子账号。→ 见独立文档：[单回调地址分流](./oauth-single-callback.md)。

### 3.2 灰度 / 金丝雀发布（按 header 选上游）

带特定 header 的流量进新版本，其余走稳定版：

```yaml
- name: api-canary
  priority: 200
  match:
    rule: 'PathPrefix("/api/") && Header("X-Release", "canary")'
  action:
    type: proxy
    upstream: ["10.0.0.9:8080"]   # 新版本
- name: api-stable
  priority: 100
  match:
    rule: 'PathPrefix("/api/")'
  action:
    type: proxy
    upstream: ["10.0.0.1:8080"]   # 稳定版
```

按比例灰度可交给 Header 由上游染色，或结合 `ClientIP` 先放内网。

### 3.3 API 多版本路由 + 老版本兼容

新老版本各自独立部署，同时让老客户端的 `/api/v1/*` 平滑映射到 v2 后端的新路径：

```yaml
# v2 / v3 各走各的后端
- name: api-v3
  match: { path_prefix: "/api/v3/" }
  action: { type: proxy, upstream: ["10.0.0.3:8080"] }
- name: api-v2
  match: { path_prefix: "/api/v2/" }
  action: { type: proxy, upstream: ["10.0.0.2:8080"] }

# v1 老客户端 → 转到 v2 后端，并把路径改写成 v2 形式（第 2 层适配）
- name: api-v1-compat
  match: { path_prefix: "/api/v1/" }
  action:
    type: proxy
    upstream: ["10.0.0.2:8080"]
    rewrite:
      path:
        pattern: "^/api/v1/(.*)$"
        target: "/api/v2/$1"
```

也可以让版本走 header：`rule: 'PathPrefix("/api/") && Header("X-Api-Version", "v3")'`，URL 保持干净。

### 3.4 A/B 测试（按 cookie 分流）

用原生 `Cookie` 匹配器直接按 cookie 值分流：

```yaml
- name: bucket-b
  priority: 200
  match:
    rule: 'PathPrefix("/") && Cookie("ab", "B")'
  action:
    type: proxy
    upstream: ["10.0.0.12:8080"]   # B 版
- name: bucket-a
  priority: 100
  match: { path_prefix: "/" }
  action:
    type: proxy
    upstream: ["10.0.0.11:8080"]   # A 版（默认）
```

值有前缀/正则规律时可用 `CookiePrefix("ab", "B")` 或 `CookieRegex("ab", "^B[0-9]+$")`。

### 3.5 多租户：同一域名，按 header 分到各自后端

```yaml
- name: tenant-blue
  priority: 200
  match: { rule: 'Header("X-Tenant", "blue")' }
  action: { type: proxy, upstream: ["10.1.0.1:8080"] }
- name: tenant-green
  priority: 200
  match: { rule: 'Header("X-Tenant", "green")' }
  action: { type: proxy, upstream: ["10.2.0.1:8080"] }
```

如果租户体现在子域名上，直接用不同 `domain:` 的站点更简单；体现在同域名的 header/路径上时才用 rule。

### 3.6 老 URL 迁移到新后端的新路径

老系统的 `/old/report/2024` 要接到新服务的 `/v2/analytics/report/2024`：

```yaml
- name: legacy-report
  match: { path_prefix: "/old/report/" }
  action:
    type: proxy
    upstream: ["10.0.5.1:8080"]      # 第 1 层：换到新后端
    rewrite:
      path:
        pattern: "^/old/report/(.*)$"
        target: "/v2/analytics/report/$1"   # 第 2 层：改成新路径
```

纯粹只想剥掉一层前缀时，用更轻的 [`strip_prefix`](../04-actions/proxy.md#3-高级转发参数) 即可，不必动 rewrite。

### 3.7 端类型分流（Web / 移动端不同后端）

```yaml
- name: mobile-api
  priority: 200
  match:
    rule: 'PathPrefix("/api/") && HeaderRegexp("User-Agent", "(?i)(iphone|android)")'
  action: { type: proxy, upstream: ["10.0.7.1:8080"] }
- name: web-api
  priority: 100
  match: { path_prefix: "/api/" }
  action: { type: proxy, upstream: ["10.0.7.2:8080"] }
```

### 3.8 内网 IP 才开放的功能门禁

```yaml
- name: admin-internal
  priority: 200
  match:
    rule: 'PathPrefix("/admin/") && ClientIP("10.0.0.0/8")'
  action: { type: proxy, upstream: ["10.0.9.1:8080"] }
- name: admin-blocked
  priority: 100
  match: { path_prefix: "/admin/" }
  action:
    type: respond
    status: 403
    body: "forbidden"
```

（注意 `ClientIP` 取的是直连 IP；如果 LiteGate 前面还有一层代理，请正确配置 `trusted_proxies` 让它解析 `X-Forwarded-For`。）

### 3.9 按请求属性动态筛选实例子集（服务发现 subset routing）

前面几个配方都是"一个条件 → 一条 route → 一个 upstream"。当后端是**服务发现动态注册**的一批实例、且实例带了 Endpoint Metadata（如 `sid`、`version`）时，还能通过 Service `discovery.selector.*` 或 IDS 返回的 selector **筛出实例子集**，不必为每个租户/版本各写一条 route。

`route_selector` 和 `route_meta` 的值支持 `{cookie.x}` / `{header.x}` / `{query.x}` 模板变量（和 `rewrite`、`service_tag` 同一套词汇表）。例如按 cookie 的租户值,把流量只投给带对应元数据的实例:

```yaml
- name: api-by-tenant
  match: { path_prefix: "/api/" }
  action:
    type: proxy
    service_name: api                 # 服务发现动态实例池
    route_meta:
      tenant: "{cookie.tenant}"       # 按 cookie 值软偏好对应实例子集
      version: "{header.X-Api-Version}"
```

- **选池**：`service_name: api` 由服务发现动态解析出一批实例;
- **筛子集**：`route_meta` / `route_selector` 用**同一批请求属性**在池内筛出匹配元数据的实例。

也就是说，除了"匹配 → 改写"这两层，服务发现场景下还多了一层**池内按实例元数据的动态过滤**。一条 route 就能覆盖任意多租户/版本，实例增减由服务发现自动跟随。

两个字段的区别很关键：

| 字段 | 语义 | 适合 |
| --- | --- | --- |
| `route_meta` | **软偏好**：优先命中匹配实例，匹配不到可回退池内其它实例 | 灰度、版本偏好、就近 |
| `route_selector` | **硬隔离**：只能落到匹配实例，匹配不到就没有后端 | 强隔离边界 |

> **模板值缺失即忽略该键**：`{cookie.tenant}` 不存在时展开为空串，该键会被**跳过**（不会去筛"空租户"）。所以 cookie 缺失的请求会退回到"不按 tenant 筛"的默认行为。
>
> **安全红线（务必读）**：cookie/header/query 是**客户端可伪造**的。模板 key 由你（运维）在配置里写死，客户端只能控制**值**——所以能不能被滥用，取决于你把哪个 key 交给了哪个请求属性:
> - ✅ 可以：`tenant` / `version` / `region` / `ab` 这类**非特权维度**，尤其配合 `route_meta`（软偏好）。
> - ❌ 不要：把**物理隔离 / 权限边界**的 key（如 `sid`）用裸 `{cookie.x}` 模板到 `route_selector`——那等于让客户端自己选落到哪个隔离池。这类权威选路应交给 [IDS / 身份服务](../05-middleware/ids-governance.md) 在鉴权后注入，或用受信内网头 `X-Selector-Sid`（需可信客户端 IP）。
> - ⚠️ 模板值要用**低基数**属性（租户/版本/地域），别用 per-user id，否则会击穿服务发现缓存。

---

## 4. 边界与陷阱

### `rewrite` 不能切上游、不会重新匹配

它只改**当前命中路由内**的 path/query，改完直接转发给这条路由的 upstream，不会回到路由表。任何"按 X 选后端"都要写成"一条带 X 条件的 route 指向目标 upstream"，别指望 rewrite。需要"干净 URL 全部回退到入口脚本"（WordPress/Laravel/SPA）用 [`try_files`](../04-actions/serve.md)。

### 多条路由匹配同一 path 时，全部用 `rule:`

`path:` 走 O(1) 精确匹配，会在按 `priority` 排序的常规匹配**之前**命中。若一条用 `path:`、一条用 `rule:`，`path:` 那条会**无条件抢先**，让带条件的规则永远轮不到。解决办法：**同一路径上互相竞争的路由，统一用 `rule:` 表达**，让它们一起走 priority 排序。参见 [路由优先级解析](../02-concepts/routing-priority.md)。

### 参与匹配的 query / header 值要单一且可信

- 参与值匹配的 query 参数必须**只有一个值**，多值（如 `?v=a&v=b`）不会命中，避免网关与后端取到不同值。
- 用 `header` / `cookie` 做**安全**判断时要小心：这些是客户端可伪造的。灰度、A/B 无所谓，但涉及权限（如 3.8 的内网门禁）应以 `ClientIP` 或后端鉴权为准，header 只作辅助。

### 模板化的 `route_selector` / `route_meta` 只用于非特权维度

用 `{cookie.x}` / `{header.x}` / `{query.x}` 模板实例过滤（见 [3.9](#39-按请求属性动态筛选实例子集服务发现-subset-routing)）时，客户端能控制这些值。**非特权维度**（租户/版本/AB/地域）随便用，优先落到 `route_meta`（软偏好）；**权限 / 物理隔离边界**（如 `sid`）绝不能用裸请求属性模板到 `route_selector`，应交给 IDS 鉴权后注入或受信内网头。另外模板值要低基数，避免击穿服务发现缓存。

### 改写 query 可能影响验签

`rewrite.query` 会按标准编码重排查询串，若第三方按原始 query 字节验签会失败。这种情况只改 path，或让后端读 `{original_uri}` / `{original_path}`。详见 [Proxy `rewrite` 说明](../04-actions/proxy.md#8-url-rewrite-rewrite)。

---

## 5. 一句话总结

> **match 负责"给谁"，rewrite 负责"长什么样"。** 把任何疑难杂症拆成这两个问题，先用 `rule` 的布尔组合选对后端，再用 `rewrite` 把 URL 适配好——网关层的分流、灰度、多版本、迁移、多租户，基本都在这套组合的射程之内。

---

## 相关文档

- [单回调地址分流（OAuth 一个回调地址，多个后端）](./oauth-single-callback.md)
- [Proxy 转发与 `rewrite` 参数详解](../04-actions/proxy.md#8-url-rewrite-rewrite)
- [规则表达式 Rule DSL 参考](../03-configuration/site-config.md#9-规则表达式-rule-dsl-参考)
- [路由优先级解析](../02-concepts/routing-priority.md)
