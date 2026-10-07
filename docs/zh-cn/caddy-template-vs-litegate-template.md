# Caddy `templates` 与 LiteGate `template` 功能对比

> 对比时间：2026-09-05  
> Caddy 部分以当前官方文档和 `caddyserver/caddy` 主线源码为准；LiteGate 部分以本仓库当前实现为准。

## 1. 结论先行

Caddy 和 LiteGate 都使用 Go 模板语法，但它们解决的并不是同一个问题：

```text
Caddy templates
    = 响应体模板中间件
    = 将文件、静态响应甚至上游响应再次解释为模板

LiteGate template
    = 页面渲染终端 Action
    = 主动获取 API 数据后生成完整页面或 HTMX 片段
```

Caddy 更像一个功能丰富的“可编程静态站/响应加工器”，LiteGate 更像一个面向 API、服务发现和 HTMX 的轻量 UI Gateway。

- 如果重点是文件包含、Markdown、Sprig 函数、占位符以及加工任意可信响应体，Caddy 更成熟、更灵活。
- 如果重点是纯 JSON API、结构化并发取数、服务发现、缓存失效、KV 模板和 HTMX 局部渲染闭环，LiteGate 的模型更直接。
- LiteGate 不应简单复制 Caddy 的所有文件和网络函数。两者最有价值的差异，是 LiteGate 把模板能力约束在“安全取数、轻量组合和页面呈现”范围内。

## 2. 总览对比

图例：✅ 原生支持；🟡 能实现但模型不同或需要额外配置；🔌 需要扩展；❌ 当前不支持。

| 维度 | Caddy `templates` | LiteGate `template` | 判断 |
| :--- | :--- | :--- | :--- |
| 核心形态 | HTTP 响应处理中间件 | 路由终端 Action | 定位不同 |
| Go 模板引擎 | `text/template` | `html/template` | LiteGate 默认 HTML 安全性更好 |
| 处理来源 | 文件、`respond`、代理上游等产生的响应体 | 内联 `body`、目录模板、KV 模板 | Caddy 的响应来源更自由 |
| HTML 上下文自动转义 | ❌ `text/template` 不提供 | ✅ `html/template` 默认提供 | LiteGate 占优 |
| 自定义分隔符 | ✅ `between` / `Delimiters` | ❌ 固定 `{{ }}` | Caddy 占优 |
| 按 MIME 类型启用 | ✅ | 不适用；Action 自己产生响应 | 模型不同 |
| 内置函数数量 | ✅ Go 标准函数 + Sprig + Caddy 函数 | 🟡 精简高频的实用工具函数集合 | Caddy 函数体量更大 |
| 模板函数插件 | ✅ `http.handlers.templates.functions.*` | ✅ 原生支持 `pkg/plugin.RegisterTemplateFunc(s)` 扩展点 | 两者均原生支持 |
| 文件包含/导入 | ✅ `include`、`import`、`readFile` | ✅ `template_root` + `{{ template }}` | 两者模型不同 |
| 文件查询 | ✅ `listFiles`、`fileStat`、`fileExists` | ❌ 模板内不开放通用文件查询 | Caddy 更强；LiteGate 暴露面更小 |
| Markdown | ✅ Goldmark + GFM、脚注、代码高亮 | ✅ 内置轻量 Markdown及独立 `markdown` Action | Caddy 模板函数更完整 |
| 请求上下文 | ✅ `.Req`、`.OriginalReq`、`.Host`、`.Cookie`、IP、placeholder | ✅ `.Req`、`.Host`、`.Path`、`.Method`、`.Header`、`.Query`、`.Cookie`、`.ClientIP` | 大体相当 |
| 修改响应头 | ✅ `.RespHeader.Set/Add/Del` | 🟡 通过 Action `headers` 配置，不在模板中动态修改 | Caddy 占优 |
| 模板内产生 HTTP 错误 | ✅ `httpError` | 🟡 `on_error`、状态配置和统一错误处理 | 模型不同 |
| 同站点内部子请求 | ✅ `httpInclude`，内存虚拟 GET | ✅ `httpInclude`，复用 `InternalRedirect` 内存虚拟 GET，最大递归 5 层、响应上限 1 MiB | 两者均原生支持，LiteGate 额外限制资源消耗 |
| 外部 JSON API 获取 | 🟡 可经内部路由 + `httpInclude` + `fromJson` 组合 | ✅ `fetch_json` 一等配置 | LiteGate 更直接 |
| 多数据源并发获取 | 需自行组织/扩展 | ✅ 原生并发 | LiteGate 占优 |
| 请求超时/响应体上限 | 依赖被调用路由或扩展 | ✅ 每个 `fetch_json` 独立配置 | LiteGate 占优 |
| SSRF 默认防护 | 模板能力可访问文件、环境和内部路由，依赖可信模板边界 | ✅ 外部 fetch 默认禁止私网/回环/保留地址 | LiteGate 更严格 |
| 服务发现取数 | 🔌 通过反代路由或插件间接实现 | ✅ `service://` | LiteGate 占优 |
| mTLS/灰度/IDS 选路取数 | 依赖路由组合/插件 | ✅ 复用 LiteGate 代理治理链 | LiteGate 占优 |
| 数据 TTL 缓存 | ❌ 模板模块无专用数据缓存 | ✅ `fetch_json.ttl` | LiteGate 占优 |
| 标签化缓存失效 | ❌ 模板模块无此闭环 | ✅ `cache_tags` + `proxy.on_success` | LiteGate 占优 |
| HTMX 脚本 | 用户自行部署 | ✅ 内嵌 HTMX 与 `htmx` helper | LiteGate 占优 |
| 同 URL 完整页/片段 | 用户自行按 Header 路由或写模板条件 | ✅ `template_fragment` 原生识别 `HX-Request` | LiteGate 更直接 |
| 写后 HTMX 事件 | 用户/后端自行设置 | ✅ `proxy.on_success.htmx_trigger` | LiteGate 占优 |
| 模板存入 KV | 🔌 标准指令无一等 KV 模板模型 | ✅ litemesh/Consul KV | LiteGate 占优 |
| KV 监听和原子热更新 | 🔌 | ✅ | LiteGate 占优 |
| 本地开发热更新 | 每次处理响应时解释模板内容 | ✅ Mtime 依赖检查和重新编译 | 都可快速看到变化 |
| 生产预编译缓存 | 没有与 LiteGate 同名的模式开关 | ✅ `template_production` | LiteGate 配置更明确 |
| 可视化模板错误 | 标准错误链和日志 | ✅ `template_debug` 页面 | LiteGate 开发体验更直接 |

## 3. 核心架构差异

### 3.1 Caddy：加工已经产生的响应体

Caddy 官方将 `templates` 定义为执行响应体模板的中间件。响应体可以来自静态文件、`respond`，也可以来自反向代理上游。官方同时明确警告：不能对不可信、用户可编辑的内容启用模板执行，因为模板能访问环境、文件和网络能力。

典型配置：

```caddyfile
example.com {
    root * /srv
    templates
    file_server
}
```

链路是：

```text
file_server 读取 index.html
    → templates 缓冲响应体
    → 将响应体当作 text/template 执行
    → 返回结果
```

这种中间件模型的优势是来源自由：只要下游 Handler 能产生符合 MIME 条件的文本响应，`templates` 就能继续加工。但它也意味着必须格外小心，不能让用户输入变成可执行模板。

参考：[Caddy templates 指令](https://caddyserver.com/docs/caddyfile/directives/templates)、[Caddy 模板模块源码](https://github.com/caddyserver/caddy/blob/master/modules/caddyhttp/templates/templates.go)。

### 3.2 LiteGate：由路由主动构造页面

LiteGate 的 `template` 是终端 Action：模板就是该路由的响应生产者，而不是包裹任意下游响应的中间件。

```yaml
routes:
  - name: dashboard
    match:
      path: /dashboard
    action:
      type: template
      template: pages/dashboard.html
      template_root: ./site
      fetch_json:
        - key: stats
          url: service://metrics-api/v1/stats
```

链路是：

```text
匹配 template Action
    → fetch_json 获取并解析 API JSON
    → 数据写入 .Data.stats
    → html/template 渲染页面
    → 返回 HTML
```

它不能像 Caddy 一样直接把任意代理响应再次解释为模板，但边界更容易理解：只有明确配置为 `template` 的可信模板会被执行。

## 4. 模板语言与安全模型

### 4.1 Caddy 使用 `text/template`

Caddy 模板模块源码使用 Go `text/template`，并设置 `missingkey=zero`。它不会像 `html/template` 那样根据 HTML 标签、属性、URL或 JavaScript 上下文自动转义数据。

Caddy 的安全前提是“模板及被模板读取/包含的内容必须可信”。例如官方文档特别说明：

- `include` 和 `readFile` 的内容不会自动转义。
- 代理响应只要通过 MIME 匹配，也可能被解释为模板。
- 模板可以读取环境、文件，并通过内部路由发起子请求。

这不代表 Caddy 不安全，而是它给模板作者更多能力，同时要求使用者严格控制模板内容来源。

### 4.2 LiteGate 使用 `html/template`

LiteGate 默认使用 Go `html/template`，动态变量会根据所在 HTML 上下文进行转义：

```gotemplate
<p>{{ .Query "message" }}</p>
```

如果 `message` 含 HTML 标签，默认不会作为标签执行。只有显式调用以下能力才会绕过：

```gotemplate
{{ safeHTML .Data.content }}
```

因此 `safeHTML` 只能用于可信内容。KV 模板写权限也应视同代码部署权限。

LiteGate 还收紧了几个边界：

- `env` 默认只能读取白名单环境变量，可通过 `LITEGATE_ALLOWED_ENVS` 扩充。
- 本地模板路径必须位于 `template_root` 内，并校验符号链接解析后的真实路径。
- `fetch_json` 在实际拨号时执行 SSRF 地址校验。
- 每个数据源都有超时和响应体大小上限。

安全结论：Caddy 倾向“强能力 + 可信内容约束”，LiteGate 倾向“默认收敛 + 显式放开”。

## 5. 模板来源与组合

### 5.1 Caddy

Caddy 标准 `templates` 可以处理：

- `file_server` 读取的磁盘或文件系统内容。
- `respond` 产生的内联文本。
- `reverse_proxy` 等 Handler 返回的文本响应。
- `include`：读取并立即执行另一个模板文件，可传 `.Args`。
- `import`：解析模板定义，再通过 `template` / `block` 调用。
- `readFile`：原样读取文件。

Caddy 的 `root` 为这些文件函数设定根文件系统。标准 `templates` 指令没有与 LiteGate `template_kv_prefix` 等价的一等 KV 前缀、监听和原子切换配置；可以通过模块、虚拟文件系统或外部同步方案扩展。

### 5.2 LiteGate

LiteGate 提供三种模板来源，由用户自行选择。

内联模板：

```yaml
action:
  type: template
  body: '<h1>Hello {{ .Host }}</h1>'
```

目录模板：

```yaml
action:
  type: template
  template: pages/index.html
  template_root: ./site
```

LiteGate 扫描 `template_root` 下的 `.html` 和 `.tmpl`，可以使用标准命名模板：

```gotemplate
{{ template "partials/header.html" . }}
```

KV 模板：

```yaml
action:
  type: template
  template: pages/index.html
  template_kv_mode: true
  template_kv_provider: litemesh
  template_kv_prefix: litegate/templates/site-a/
  template_kv_namespace: tenant-a
```

KV 前缀下每个 Key 是一个模板文件。LiteGate 在内存中编译模板组，监听变更后重新编译并原子切换；拉取失败时可以继续使用上一份已编译模板。

KV 模式的资源边界：最多 100 个模板、单个不超过 1 MiB、总计不超过 10 MiB。

## 6. 动态数据和子请求

### 6.1 Caddy 的 `httpInclude`

Caddy 的 `httpInclude` 发起同一虚拟服务器内的轻量 GET 请求，不经过真实网络 Socket。它会复制原请求 Header，并设置递归深度限制来防止虚拟请求循环。返回状态大于等于 400 时，模板执行会收到错误。

配合 Sprig 的 JSON 函数，可以组成类似逻辑：

```gotemplate
{{ $raw := httpInclude "/internal/stats" }}
{{ $stats := fromJson $raw }}
<strong>{{ get $stats "total" }}</strong>
```

其中 `/internal/stats` 可以再由 Caddy 路由到反向代理。这个模型很灵活，适合在同一个 Caddy Handler 图中复用已有路由。

限制也很明确：

- `httpInclude` 是模板函数，结果首先是字符串。
- 请求语义固定为同站点内部虚拟 GET。
- 多数据源并发、独立 TTL、失败策略和标签失效不是模板模块的一等概念。

参考：[Caddy `TemplateContext` 与内置函数](https://pkg.go.dev/github.com/caddyserver/caddy/v2/modules/caddyhttp/templates)、[`httpInclude` 源码](https://github.com/caddyserver/caddy/blob/master/modules/caddyhttp/templates/tplcontext.go)。

### 6.2 LiteGate 的 `fetch_json`

LiteGate 将 API 取数从模板语言移到路由配置：

```yaml
fetch_json:
  - key: profile
    url: service://user-api/v1/profile
    timeout: 3
    ttl: 10
    fail_policy: error
    forward_headers: [Authorization]

  - key: notices
    url: service://notice-api/v1/notices
    timeout: 2
    ttl: 5
    fail_policy: ignore
```

两个数据源会并发执行，并分别出现在：

```gotemplate
{{ .Data.profile }}
{{ .Data.notices }}
{{ .Errors.notices }}
```

`service://` 会复用服务发现、IDS Selector/Meta、健康实例过滤、灰度、负载均衡和 mTLS transport。普通 `http(s)://` 则经过 SSRF 防护。

这种配置式模型没有 Caddy 模板函数那么自由，但更适合网关治理：运维人员不用审查模板里的任意网络调用，就能从 YAML 看出页面依赖了哪些服务、超时多久、失败后是否降级。

### 6.3 LiteGate 的 `httpInclude`

LiteGate 同样原生支持 `httpInclude` 模板内置函数：

```gotemplate
<!-- 内存级虚拟调用同站点子路由，原样内嵌子页面/组件 -->
<header>{{ httpInclude "/components/navbar?theme=dark" }}</header>
```

- **零网络 Socket 开销**：直接复用网关核心的 `Context.InternalRedirect`（即 `router.ServeHTTP`），在进程内存内派发子请求，性能极高。
- **上下文透明继承**：子请求透明继承父请求的 Header、Cookie、客户端真实 IP（`X-Forwarded-For`），并自动透传 Query 参数。
- **递归死循环防护**：利用 `context.Context` 记录调用深度，上限强制为 5 层。一旦出现循环包含，即刻熔断并抛出友好错误。
- **明确资源边界**：只接受以单个 `/` 开头的站内路径；响应体上限 1 MiB，拒绝非 2xx、SSE、流式和协议升级响应，并剥离 hop-by-hop 请求头。
- **可信 HTML 边界**：返回值类型为 `template.HTML`，确保子路由组件不会被多余转义；相应地，目标路由必须输出可信 HTML，不能直接拼入未经转义的用户输入。
- **分工策略**：LiteGate 建议“数据拉取首选并发的 `fetch_json`，页面公共部件/子路由拼装选用 `httpInclude`”，两者形成互补。

## 7. 缓存与写后闭环

Caddy 的模板模块本身没有 `fetch_json.ttl`、缓存标签和写后失效协议。可以借助其他缓存 Handler、插件或应用自身实现，但不属于 `templates` 的内置数据模型。

LiteGate 的读取配置可以给数据缓存打标签：

```yaml
action:
  type: template
  template: pages/todos.html
  template_root: ./site
  fetch_json:
    - key: todos
      url: service://todo-api/todos
      ttl: 30
      cache_tags: [todos]
```

写操作只需要配置普通代理和成功后的网关动作：

```yaml
- name: create-todo
  match:
    path: /api/todos
    method: [POST]
  action:
    type: proxy
    service_name: todo-api
    on_success:
      invalidate_cache: [todos]
      htmx_trigger: [todos-changed]
      discard_body: true
```

上游纯 JSON API 返回 `2xx` 后，LiteGate 会：

1. 清除带 `todos` 标签的 `fetch_json` 缓存。
2. 生成 `HX-Trigger: todos-changed`。
3. 根据配置读取但不向浏览器发送成功 JSON 响应体。
4. 对 `3xx/4xx/5xx` 保留原响应，不执行成功动作。

这使业务 API 不需要生成 HTML，也不需要理解 LiteGate 或 HTMX Header。

## 8. HTMX 支持

### Caddy

Caddy 可以很好地托管 HTMX 应用，但 `templates` 本身不提供 HTMX 专用语义：

- HTMX 脚本由用户自行部署或引用 CDN。
- 完整页和片段的选择由路由、Header matcher 或模板条件实现。
- 写后事件 Header 由应用、Caddy Header 配置或扩展产生。

这给使用者最大的自由度，但需要自行拼装约定。

### LiteGate

LiteGate 把常用约定做成一等能力：

```yaml
action:
  type: template
  template: pages/dashboard.html
  template_root: ./site
  template_fragment: stats-cards
```

模板同时包含完整页面和命名片段：

```gotemplate
{{ define "stats-cards" }}
<div id="stats-data">...</div>
{{ end }}

<!doctype html>
<html>
  <body>{{ template "stats-cards" . }}</body>
</html>
```

- 普通请求执行完整主模板。
- `HX-Request: true` 只执行 `stats-cards`。
- 响应自动加入 `Vary: HX-Request`。
- `{{ htmx }}` 可以加载 LiteGate 内嵌脚本。
- `.Nonce` 或 `nonce` helper 支持严格 CSP。
- `proxy.on_success.htmx_trigger` 可以由网关发出写后事件。

这一组合是 LiteGate 相对 Caddy 最明确的产品差异，而不是单个模板函数数量。

## 9. 函数和上下文能力

### Caddy 更丰富的部分

Caddy 除了 Go 标准模板函数，还集成 Sprig，并提供：

- `include`、`import`、`readFile`
- `httpInclude`
- `listFiles`、`fileStat`、`fileExists`
- `markdown`、`splitFrontMatter`
- `placeholder` / `ph`
- `httpError`
- `humanize`、`stripHTML`、`pathEscape`
- `.RespHeader.Set/Add/Del`
- 模板函数扩展模块和可选函数 `maybe`

所以在“模板本身就是小型程序”的场景中，Caddy 明显更强。

### LiteGate 更场景化的部分

LiteGate 当前内置了高频实用的核心函数库：

- `markdown`
- `htmx`
- `safeHTML`
- `httpInclude`
- `default`
- `toJson` / `fromJson`
- `split` / `join`
- `slice` / `dict`
- `b64enc` / `b64dec`
- `urlquery`
- `lower`、`upper`、`contains`、`replace`、`substr`
- `formatTime` / `formatDateTime`
- 白名单 `env`
- `nonce`

请求上下文包括：

- `.Req`
- `.Host`、`.Path`、`.Method`、`.Time`、`.ClientIP`
- `.Header`、`.Query`、`.Cookie`
- `.Data`、`.Errors`
- `.Nonce`

LiteGate 不全盘无脑照搬 Sprig 的上百个函数以维持核心轻量与安全边界，但在 `pkg/plugin` 中正式提供了 `RegisterTemplateFunc(s)` 插件扩展点，允许第三方模块根据需要注入企业专有或特定业务函数。注册过程会校验函数名与签名，拒绝重复名称和内置保留名称；注册表版本也会进入模板缓存键，避免热注册后继续使用旧的已编译模板。

## 10. 性能和更新模型

两者在输出模板响应时都需要缓冲，因此都不适合把模板执行放在 SSE、超大文件或持续流式响应链路上。

Caddy 的中间件需要取得下游响应体后再执行模板。它的优势是 Handler 组合统一；代价是模板能力是否生效还受到 Handler 顺序、MIME 和响应来源影响。

LiteGate 提供两个明确模式：

| 模式 | 行为 |
| :--- | :--- |
| 开发模式 | 检查 `template_root` 中模板依赖的 Mtime，变更后重新编译 |
| `template_production: true` | 使用内存中的已编译模板，避免请求期文件检查 |
| `template_debug: true` | 绕过生产缓存，并显示带源码上下文的模板错误页 |
| KV 模式 | 监听 KV 变更、重新编译、原子替换，失败时保留上一版本 |

`fetch_json` 数据缓存与模板编译缓存互相独立：修改模板不等于清空 API 数据缓存，业务写入则通过标签精确清除数据缓存。

本文不对两者做 QPS 高低结论。没有同一机器、同一模板和同一请求链的基准测试，单从架构无法得出可靠性能排名。

## 11. 错误处理

Caddy 模板可以调用实验性的 `httpError` 返回结构化 Handler 错误，也可以通过 `.RespHeader` 修改响应头，并与 `handle_errors` 等路由组合。

LiteGate 更偏配置化：

```yaml
action:
  type: template
  template: pages/dashboard.html
  template_debug: false
  on_error:
    status: 502
    content_type: text/html
    template: pages/fallback.html
```

`fetch_json.fail_policy` 决定单个数据源错误是：

- `ignore`：记录到 `.Errors.<key>`，页面继续渲染。
- `error`：终止渲染并进入 `on_error`。

Caddy 更适合在模板/Handler 图中编程式组合错误；LiteGate 更适合统一声明页面降级策略。

## 12. 选型建议

选择 Caddy `templates`，当你需要：

- 给静态文件、内联响应或可信代理响应统一套模板。
- 大量使用 Sprig、Front Matter、文件查询和模板内工具函数。
- 通过 `httpInclude` 复用同一 Caddy 站点的内部路由。
- 使用插件扩展模板函数。
- 自定义模板分隔符或按 MIME 启用模板处理。

选择 LiteGate `template`，当你需要：

- 业务后端保持为纯 JSON API，不负责页面或 HTML 片段。
- 一个页面并发聚合多个 API。
- 直接通过服务发现名称取数，并继承 IDS、灰度、负载均衡和 mTLS。
- 对数据做短 TTL 缓存，并在写成功后精确失效。
- 同一个 URL 同时生成完整 SSR 页面和 HTMX 局部片段。
- 将模板放在本地目录或 litemesh/Consul KV，并热更新多节点模板。
- 默认使用 HTML 上下文转义和受限环境变量访问。

两者也可以共存：Caddy 负责公网自动 HTTPS 和通用 Web 服务，LiteGate 负责内部 API 聚合页面；不过如果 LiteGate 已经承担入口、服务发现和身份治理，通常没有必要仅为模板再增加一层 Caddy。

## 13. LiteGate 值得继续补强的能力

对照 Caddy 后，LiteGate 最值得吸收的是：

1. **模板函数扩展点**：允许可信插件注册函数，而不是无限扩张核心函数表。
2. **更完整的 Markdown**：GFM、Footnote、代码高亮和 Front Matter。
3. **可选的 `include` 参数模型**：让组件模板接收明确参数，而不仅是整个页面上下文。
4. **文件元数据函数的受限版本**：只允许在 `template_root` jail 内执行，并默认关闭。
5. **可配置分隔符**：适配同时大量使用 `{{ }}` 的前端框架或配置文件。

不建议直接照搬：

- 不受限的环境变量读取。
- 将任意代理响应自动解释为模板。
- 模板内任意访问外部 URL。
- 让页面模板承担复杂业务事务。

LiteGate 的竞争力不在于“函数数量超过 Caddy”，而在于形成以下闭环：

```text
目录/KV 模板
    + 安全、结构化 API 取数
    + 服务发现和身份选路
    + 数据缓存
    + 写后精确失效
    + HTMX 完整页/片段切换
```

## 14. 参考资料

### Caddy 官方资料

- [Caddy `templates` 指令](https://caddyserver.com/docs/caddyfile/directives/templates)
- [Caddy templates 模块 Go 文档](https://pkg.go.dev/github.com/caddyserver/caddy/v2/modules/caddyhttp/templates)
- [Caddy templates 模块源码](https://github.com/caddyserver/caddy/blob/master/modules/caddyhttp/templates/templates.go)
- [Caddy TemplateContext 与内置函数源码](https://github.com/caddyserver/caddy/blob/master/modules/caddyhttp/templates/tplcontext.go)
- [Caddy `file_server` 指令](https://caddyserver.com/docs/caddyfile/directives/file_server)
- [Caddy Handler 顺序说明](https://caddyserver.com/docs/caddyfile/directives)

### LiteGate 仓库资料

- [Template Action 用户文档](./user/04-actions/template.md)
- [站点配置与 `proxy.on_success`](./user/03-configuration/site-config.md)
- [`template` Action 实现](https://github.com/jamesleeon/LiteGate/blob/master/internal/action/template.go)
- [`proxy.on_success` 实现](https://github.com/jamesleeon/LiteGate/blob/master/internal/action/proxy.go)
- [模板配置结构](https://github.com/jamesleeon/LiteGate/blob/master/internal/loader/types.go)
