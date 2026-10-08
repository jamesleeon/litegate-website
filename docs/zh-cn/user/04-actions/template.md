# Template Action (服务端模板与站点渲染)


`template` Action 支持使用 Go 的 `html/template` 在网关层（服务端）直接渲染高颜值、动态的 HTML 页面。它默认启用 HTML 转义以防止跨站脚本攻击（XSS），支持请求上下文数据的动态注入，并支持多文件**片段复用**。

同时，LiteGate 提供了针对**自定义错误页（Error Pages）**、**SSO 自定义登录页**、**免登录公开系统状态页（Status Page）**以及 **Markdown 模板化渲染** 的完整高级集成方案。

---

## 1. 最小配置（内联模板）

```yaml
domain: status.example.com
routes:
  - name: hello
    match:
      path_prefix: /
    action:
      type: template
      body: "<h1>Hello {{ .Host }}</h1><p>你的 IP：{{ .ClientIP }}</p>"
```

访问后将返回网关渲染好的 HTML。`body` 属性适合短小的内联模板。

---

## 2. 文件模板与片段复用

通过指定 `template` 文件路径，可以从本地磁盘或挂载目录中读取页面进行渲染。

```yaml
action:
  type: template
  template: "./site/pages/index.html"   # 主模板文件路径
  template_root: "./site"               # 片段扫描根目录，用于扫描其它 HTML 片段
```

在主模板 `index.html` 中，可以通过 `{{ template "相对路径" . }}` 引用 `template_root` 下的其它公共组件（例如 Header / Footer）：

```html
<!-- ./site/pages/index.html -->
{{ template "partials/header.html" . }}
<main>欢迎访问 {{ .Host }}，当前系统时间：{{ .Time }}</main>
{{ template "partials/footer.html" . }}
```

---

### 📦 分布式加载：从 litemesh / Consul KV 拉取模板（`template_kv_mode`）

除了从本地磁盘读取，模板还可以**直接存放在 litemesh / Consul 的 KV 里**，由网关在内存中编译。这样多节点集群无需把模板文件分发到每台机器，改一次 KV 全网生效——对标已有的 [Serve KV 模式](../../serve_kv_mode.md)。

```yaml
action:
  type: template
  template_kv_mode: true
  template_kv_provider: "litemesh"            # litemesh 或 consul
  template_kv_prefix: "litegate/tmpl/site-a/" # 模板片段在 KV 中的前缀
  template_kv_namespace: "tenant-a"           # 可选，多租户隔离；留空用客户端默认 namespace
  template: "pages/index.html"                # 主模板：相对 prefix 的 key 后缀
```

工作方式：

- 网关用 `ListKV(prefix)` 拉取该前缀下的所有片段（每个 KV key 去掉 prefix 后即模板名，可被 `{{ template "..." }}` 引用），主模板由 `template` 字段指定。
- **纯内存编译，零本地文件**；不涉及文件系统，因此没有符号链接 / 目录穿越风险。
- **热更新**：网关后台监听该前缀的变更（litemesh SSE / KV `ModifyIndex`），KV 一变即在后台重新编译并原子切换，已连请求无感。
- **失效降级**：若某次拉取 KV 失败，自动回退到上一份已编译好的模板继续服务，不会把页面打挂。

#### ⚖️ 资源与安全边界

| 边界 | 限制 | 说明 |
| :--- | :--- | :--- |
| 片段数量 | ≤ 100 | 超出报错，防内存滥用 |
| 单个片段大小 | ≤ 1 MB | 超出报错 |
| 全部片段总大小 | ≤ 10 MB | 超出报错 |

> ⚠️ **安全提示**：能写入该 KV 前缀 = 能向网关注入任意模板代码（模板可调用 `safeHTML` 等绕过转义）。请把 KV 模板写入权限视同**代码部署权限**，锁好对应的 namespace 与访问 token。

> ℹ️ **限制**：KV 模式下没有本地根目录，`{{ markdown "x.md" }}` 的**文件加载形式不可用**（只支持内联字符串 `{{ markdown "# 标题" }}`）。其余上下文变量与内置函数（见下一节）均正常可用。

---

## 3. 模板可用上下文变量与函数

在 `template` 渲染上下文中，你可以直接使用以下变量与内置方法：

| 字段 / 方法 | 说明 | 示例 |
| :--- | :--- | :--- |
| `{{ .Host }}` | 请求的 Host 头部 | `example.com` |
| `{{ .Path }}` | 请求的 URL 路径 | `/docs/intro` |
| `{{ .Method }}` | 请求的 HTTP 方法 | `GET` |
| `{{ .ClientIP }}` | 客户端的真实物理 IP | `192.168.1.100` |
| `{{ .Time }}` | 当前网关时间 (RFC3339 格式) | `2026-06-17T09:00:00Z` |
| `{{ header "Key" }}` | 获取指定的 HTTP 请求头值 | `{{ header "User-Agent" }}` |
| `{{ query "key" }}` | 获取指定的 URL Query 参数值 | `{{ query "page" }}` |
| `{{ cookie "name" }}` | 获取指定的 Cookie 值 | `{{ cookie "session_id" }}` |

> 模板只能调用注册函数，不能调用对象方法（如 `{{ .Req.FormValue "x" }}`）：按名字反射调用方法会让二进制把所有依赖库的方法都编译进来（约 4MB）。`header` / `query` / `cookie` 也是函数；旧写法 `{{ .Header "X" }}` 会在加载模板时报错，并给出替换写法。

### 🛠️ 内置模板辅助函数

除了标准的 Go 内置函数外，LiteGate 在渲染上下文中注册了以下增强辅助函数以简化模板开发：

| 函数名 | 说明 | 示例 |
| :--- | :--- | :--- |
| `formatTime` / `formatDateTime` | 格式化时间对象（`time.Time`）或符合常见格式的时间字符串（如 RFC3339、`2006-01-02 15:04:05`） | `{{ formatTime .Time "2006-01-02" }}` <br> `{{ formatDateTime "2026-06-18T10:00:00Z" "2006/01/02" }}` |
| `markdown` | 将 Markdown 格式的字符串动态渲染为安全的 HTML 网页结构 (网关自动防二次转义) | `{{ markdown "# 这是一个标题\n- 列表项 1" }}` |
| `htmx` | 自动注入内建的 HTMX 4.0.0 脚本标签，避免手动部署 CDN | `{{ htmx }}` |
| `safeHTML` | 声明信任的 HTML 字符串片段，免受 HTML 转义防御的拦截 | `{{ safeHTML "<div>" }}` |
| `lower` / `upper` | 将输入字符串快速转换为全部小写或全部大写 | `{{ lower "ABC" }}` / `{{ upper "xyz" }}` |
| `contains` / `replace` / `substr` | 提供字符串匹配包含、全部替换、以及 Rune 字符安全的切片截取操作 | `{{ replace "hello" "l" "x" }}` <br> `{{ substr "abcdef" 1 4 }}` (输出 `bcd`) |
| `env` | 安全地读取系统指定的环境变量（仅限配置允许的环境变量白名单） | `{{ env "APP_ENV" }}` |
| `default` | 提供空值兜底默认值（支持空串、零值、nil、空数组切片兜底） | `{{ default "游客" .Data.user.name }}` <br> `{{ query "role" \| default "user" }}` |
| `toJson` | 将变量或数据结构序列化为经过 HTML 字符转义的 JSON，并作为 JavaScript 表达式输出 | `<script>const cfg = {{ toJson .Data.stats }};</script>` |
| `fromJson` | 将 JSON 格式字符串动态反序列化为可遍历的数据结构 | `{{ $obj := fromJson .Data.rawString }}` |
| `split` / `join` | 字符串切片拆分与元素合并拼接 | `{{ $tags := split "a,b,c" "," }}` <br> `{{ join $tags " · " }}` |
| `dict` / `slice` | 在模板内部动态创建复合字典（KV对）或切片列表（子模板传参神器） | `{{ $ctx := dict "title" "详情" "id" 42 }}` <br> `{{ template "card" $ctx }}` |
| `b64enc` / `b64dec` | 标准 Base64 编码与解码操作 | `{{ b64enc "token-123" }}` <br> `{{ b64dec .Token }}` |
| `urlquery` | 对 URL 查询参数进行安全转义 | `{{ urlquery "a b&c" }}` |
| `httpInclude` | 发起同站点内存级虚拟 GET 子请求并内嵌可信 HTML 片段（最大递归 5 层、响应上限 1 MiB） | `{{ httpInclude "/components/header?theme=dark" }}` |

`httpInclude` 只接受以单个 `/` 开头的站内路径，不接受完整 URL、协议相对 URL 或片段标识。它会继承父请求的身份请求头（包括 Cookie 和 Authorization），并把响应作为可信 HTML 插入当前页面。因此目标路由必须与当前站点处于同一信任域，且不得直接返回未经转义的用户输入；流式、SSE、协议升级及非 2xx 响应不受支持。外部或 API 数据请求应使用 `fetch_json`。

### 🔌 模板函数插件扩展体系 (Plugin SPI)

LiteGate 提供了类似 Caddy 的全局模板函数插件扩展机制。任何第三方 Go 模块或企业内部私有包，只需调用 `pkg/plugin.RegisterTemplateFunc`，即可向所有模板注入专有函数：

```go
package myplugin

import (
    "log"

    "github.com/jamesleeon/LiteGate/pkg/plugin"
)

func init() {
    // 注册自定义脱敏函数
    if err := plugin.RegisterTemplateFunc("maskPhone", func(phone string) string {
        if len(phone) == 11 {
            return phone[:3] + "****" + phone[7:]
        }
        return phone
    }); err != nil {
        log.Printf("register template function failed: %v", err)
    }
}
```

编译时导入该插件包后，即可在任意模板中直接调用：
```gotemplate
<p>联系电话：{{ .Data.user.phone | maskPhone }}</p>
```

注册会校验函数名、函数签名、重复名称以及 LiteGate 内置保留名称，并在失败时返回 `error`。模板函数可能被多个请求并发调用，插件函数自身必须是线程安全、执行时间有界的可信代码。注册表发生变化后，LiteGate 会使用新的缓存版本重新编译模板。


---

## 4. 挂钩状态码渲染自定义错误页 (Nginx/Caddy 对标)

当代理的后端服务不可用（如发生 502 Bad Gateway、504 Gateway Timeout）或发生 404 Site Not Found 时，你可以通过配置 `error_pages` 拦截状态码，并渲染高颜值的 HTML 错误页。

### 🛡️ 流式响应与协议升级安全绕过说明
为了保证长连接与特殊传输协议的可用性，错误页拦截器自动遵循以下钢铁法则：
1. **Header 已发送直接透传**：如果在错误发生前，Header 已经写入并发送给客户端（如开始推送流数据），网关将直接透传，不再强行替换 Body，以防止破坏客户端已有状态。
2. **WebSocket & SSE 自动绕过**：网关检测到 WebSocket 协议升级（`Upgrade: websocket`）或 `Accept/Content-Type` 为 `text/event-stream` (SSE) 时，将强制关闭拦截器，确保双向通信与推送通道的语义完整。

### ⚙️ YAML 配置示例

主配置可以设置全局兜底错误页，用于 Host 没有匹配任何 site 的情况：

```yaml
# config.yaml
error_pages:
  - status: [404]
    template: "./templates/errors/site-not-found.html"
```

错误页按“站点级 → 全局级 → LiteGate 内置页面”的顺序选择。请求匹配到 site 且该 site 配置了对应状态码时，优先使用下面的站点级模板；否则继续使用全局模板。

```yaml
domain: myapp.example.com
# 站点级全局错误页面映射
error_pages:
  - status: [404]
    template: "./templates/errors/404.html"
  - status: [500, 502, 503, 504]
    template: "./templates/errors/5xx.html"
routes:
  - name: my-service
    match:
      path_prefix: /
    action:
      type: proxy
      service_name: backend-app
```

### 📝 错误页模板编写规范
在错误页模板中，网关会额外注入以下上下文变量：
- `{{ .Status }}`：HTTP 状态码（如 502）
- `{{ .StatusText }}`：状态码描述（如 Bad Gateway）
- `{{ .Error }}`：后端服务或网关抛出的原始错误信息明文
- `{{ .RequestID }}`：当前请求的追踪链 ID (`X-Request-Id`)

```html
<!-- ./templates/errors/5xx.html -->
<div class="error-container">
    <h1>Error {{ .Status }} : {{ .StatusText }}</h1>
    <p>抱歉，服务器暂时无法处理您的请求。请稍后再试。</p>
    <pre>Trace Error: {{ .Error }}</pre>
    <small>RequestId: {{ .RequestID }}</small>
</div>
```

---

## 5. SSO 自定义登录页面渲染

如果你在路由上启用了 SSO 认证，可以挂载一个自定义的登录 HTML 页面，替代系统默认的登录框。

### ⚙️ YAML 配置示例
```yaml
routes:
  - name: secure-admin
    match:
      path_prefix: /admin
    action:
      type: proxy
      service_name: admin-service
      auth:
        type: sso
        secret: "your-super-long-sso-cookie-signing-secret"
        template: "./templates/auth/login.html" # 指定自定义登录模板路径
```

### 📝 SSO 登录模板编写规范
在自定义的登录 HTML 模板中，你可以通过以下占位符获取认证上下文，且必须在 `<form>` 中放置重定向隐藏域：

- `{{ERROR}}`：如果登录失败（如密码错误），网关会在此处替换为 `<div class="error-msg">错误信息</div>`，没有错误时则为空。
- `{{NEXT}}`：登录成功后需重定向的原始目标 URL。
- `{{CLIENT_IP}}`：当前发起登录的客户端 IP 地址。

```html
<!-- ./templates/auth/login.html -->
<div class="login-card">
    <h2>系统登录授权</h2>
    {{ERROR}}
    <form action="" method="POST">
        <!-- 核心：必须带上此隐藏域，以便网关登录成功后正确回跳 -->
        <input type="hidden" name="next" value="{{NEXT}}">
        
        <input type="text" name="username" placeholder="用户名" required>
        <input type="password" name="password" placeholder="密码" required>
        <button type="submit">立即登录</button>
    </form>
    <small>您的登录 IP: {{CLIENT_IP}}</small>
</div>
```

---

## 6. 免登录公开系统状态页 (AI 风格 Status Dashboard)

你无须向终端用户暴露敏感的管理后台，只需配置 `status` 类型的 Action，即可直接渲染一个支持暗黑模式、高颜值磨砂玻璃风（Glassmorphism）的公开可用性状态面板。

```yaml
routes:
  - name: site-status
    match:
      path: /status
    action:
      type: status
      title: "LiteGate Platform Availability" # 可自定义看板大标题
```

访问 `/status` 后，网关会自动获取当前所有站点的健康状态、QPS、平均响应时间及最近 30 天的可用性历史状态图，并提供每隔 5 秒自动更新指标数据的实时动态效果。同时它也支持 API 调用（请求中携带 `?format=json` 或 `Accept: application/json` 头可直接获取状态的 JSON 数据）。

---

## 7. Markdown 文档的模板化布局渲染

在传统的静态托管（`serve`）模式下，如果开启了 `render_markdown`，你可以使用自定义的 HTML 模板来定制文档的页面外观。

```yaml
action:
  type: serve
  root: "./docs"
  render_markdown: true
  markdown_template: "./templates/layouts/doc.html" # 自定义 Markdown 页面框架
```

在自定义布局 `doc.html` 中，可以使用以下 Go HTML 模板变量来接收文档信息与渲染内容：

- `{{ .Title }}`：当前 Markdown 文档的文件名或解析出的一级标题。
- `{{ .Content }}`：Markdown 服务端渲染好的 HTML 内容（类型为 `template.HTML`，直接输出不会被转义）。
- `{{ .Sidebar }}`：侧边栏的树形结构数据列表，可在模板中通过 `{{ range .Sidebar }}` 直接循环渲染侧边栏。
- `{{ .Host }}`、`{{ .Path }}` 等：标准的请求上下文变量，支持获取请求头和 Cookie。
- `{{ .Nonce }}`：生成当前页面唯一的随机安全 nonce，供 CSP 策略使用。

### 📝 Go Layout 模板编写示例
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{{ .Title }} | 文档中心</title>
    <style>
        body { display: flex; font-family: sans-serif; }
        .sidebar { width: 250px; background: #f8fafc; padding: 20px; border-right: 1px solid #e2e8f0; }
        .content { flex: 1; padding: 40px; }
        .nav-item { margin-bottom: 8px; }
    </style>
</head>
<body>
    <aside class="sidebar">
        <h3>目录</h3>
        {{ range .Sidebar }}
            <div class="nav-item">
                <a href="{{ .Href }}">{{ if .IsDir }}📁{{ else }}📄{{ end }} {{ .Name }}</a>
            </div>
        {{ end }}
    </aside>
    <main class="content">
        {{ .Content }}
    </main>
</body>
</html>
```

---

## 8. 高级配置：性能、调试与错误降级 (Production, Debug & OnError)

在生产和开发环境部署中，LiteGate 支持对模板和 Layout 进行高性能内存缓存、实时热重载以及弹性降级配置。

### ⚙️ YAML 配置高级参数

```yaml
action:
  type: template
  template: "./site/pages/index.html"
  template_root: "./site"
  
  # 1. 生产模式（建议线上开启）
  # 开启后，网关在启动时会对模板以及 markdown_template 布局自动进行预编译（Precompile），
  # 并常驻内存。运行时渲染直接读取缓存，完全关闭磁盘 I/O（不发生 os.Stat, os.ReadFile 等系统调用）。
  template_production: true

  # 2. 调试模式（建议本地开启）
  # 开启后，若模板编译或语法渲染错误，会在浏览器展示 Vite/Gin 风格的高颜值磨砂玻璃暗黑调试屏。
  # 调试屏会清晰标示出错误发生的文件名、所在行号、并在页面截取输出该行前后 5 行的上下文代码片段。
  # 当 template_debug 为 true 时，会强制旁路并忽略内存缓存以进行实时热重载。
  template_debug: true

  # 3. 错误降级策略
  # 当模板损坏、语法异常或执行报错导致无法正常向用户交付页面时，自动拦截并输出的安全降级响应。
  on_error:
    status: 502                           # 降级后的 HTTP 状态码，默认为 500
    content_type: "text/html; charset=utf-8"
    body: "<h1>服务正在维护中...</h1>"     # 降级展示的静态 HTML 字符串
    # template: "./site/fallback.html"    # 也可指定本地静态 html 降级文件
```

### 🧠 开发模式与生产模式对比

| 模式 | 推荐配置 | 特性与表现 |
| :--- | :--- | :--- |
| **开发环境 (Development)** | `template_debug: true`<br>`template_production: false` | 1. 自动追踪依赖树的 Mtime 变动：修改主模板或任意 `template_root` 下的 HTML 依赖片段，刷新即可即时热重载生效。<br>2. 编译或渲染语法错误在浏览器输出精美的报错代码上下文可视化屏。 |
| **生产环境 (Production)** | `template_debug: false`<br>`template_production: true` | 1. **零文件系统调用 (Zero-RTT I/O)** 内存缓存：消除运行时 os.Stat 等内核调用，并发 QPS 翻倍。<br>2. 预编译载入（Precompile）：网关冷启动时即完成解析缓存，消灭首个请求时的 cold start 响应延迟。<br>3. 弹性容灾：错误时静默执行 `on_error` 降级，防泄漏内部文件物理路径等敏感资产。 |

---

## 延伸阅读
- [Markdown 渲染服务](./markdown.md)
- [Serve 托管静态资源](./serve.md)
- [Respond 直接响应](./respond.md)

## 9. 结合 HTMX 与 Fetch JSON 的局部动态刷新（实战场景）🌟酷炫玩法🌟

通过联合使用 `fetch_json` 后端数据拉取和内置的 `{{ htmx }}` 渲染函数，你可以在网关层构建极具现代感、无刷新局部更新的动态交互页面。

下面的示例将演示：通过 `respond` Action 快速响应一个监控 JSON 数据（扮演我们的 API），通过 `/stats-partial` 提取 HTML 片段，最后在主页通过内建的 HTMX 实现按钮点击时的局部无刷新替换。

### ⚙️ YAML 配置示例 (`sites/demo.yaml`)
```yaml
domain: "cool-dashboard.local"
force_https: false

routes:
  # 1. 扮演后端 JSON API，返回实时系统监控 JSON 数据
  - name: mock-json-api
    match:
      path: "/api/stats"
    action:
      type: "respond"
      status: 200
      content_type: "application/json; charset=utf-8"
      body: '{"status":"healthy","qps":342,"cpu":14.8,"time":"{{.Time}}"}'

  # 2. 专门供 HTMX 调用，拉取 API 数据后返回用于替换的局部 HTML 片段
  - name: stats-fragment
    match:
      path: "/stats-partial"
    action:
      type: "template"
      body: '<div id="stats-data"><p>系统状态: <strong style="color: #22c55e;">{{.Data.monitor.status}}</strong></p><p>实时 QPS: <strong>{{.Data.monitor.qps}}</strong></p><p>CPU 占用: <strong>{{.Data.monitor.cpu}}%</strong></p><p style="color: #94a3b8;">更新时间: {{formatTime .Data.monitor.time "15:04:05"}}</p></div>'
      fetch_json:
        - key: "monitor"
          url: "http://127.0.0.1:8080/api/stats"
          allow_private: true

  # 3. 前端监控看板的主页面路由
  - name: main-dashboard
    match:
      path: "/"
    action:
      type: "template"
      template: "./templates/dashboard.html"
      fetch_json:
        - key: "monitor"
          url: "http://127.0.0.1:8080/api/stats"
          allow_private: true
```

### 📝 ./templates/dashboard.html 服务端主模板
```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>系统健康度 Dashboard</title>
    <!-- 自动加载内嵌的 HTMX 脚本，防止特殊字符转义 -->
    {{ htmx }}
    <style>
        body { font-family: sans-serif; background: #0f172a; color: #f8fafc; padding: 40px; }
        .card { background: #1e293b; border-radius: 8px; padding: 20px; border: 1px solid #334155; max-width: 400px; }
        .btn { background: #3b82f6; border: none; padding: 10px 20px; color: white; border-radius: 4px; cursor: pointer; }
        .btn:hover { background: #2563eb; }
    </style>
</head>
<body>
    <h1>监控看板 - {{ .Host }}</h1>
    
    <div class="card">
        <h3>实时系统指标</h3>
        
        <!-- 首屏通过 template 结合 fetch_json 直接渲染出状态数据，实现超快速首屏 -->
        <div id="stats-data">
            <p>系统状态: <strong style="color: #22c55e;">{{.Data.monitor.status}}</strong></p>
            <p>实时 QPS: <strong>{{.Data.monitor.qps}}</strong></p>
            <p>CPU 占用: <strong>{{.Data.monitor.cpu}}%</strong></p>
            <p style="color: #94a3b8;">更新时间: {{formatTime .Data.monitor.time "15:04:05"}}</p>
        </div>
        
        <div style="margin-top: 20px;">
            <!-- 点击按钮时，HTMX 请求 /stats-partial 并无刷新替换掉 #stats-data 的内容 -->
            <button class="btn" hx-get="/stats-partial" hx-target="#stats-data" hx-swap="outerHTML">
                局部无刷新更新
            </button>
        </div>
    </div>
</body>
</html>
```

### 📋 `fetch_json` 字段参考

| 字段 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `key` | string | — | 模板变量名,渲染上下文中通过 `{{ .Data.<key> }}` 访问解析后的 JSON |
| `url` | string | — | 拉取地址,支持 `{{ }}` 模板语法(基于请求上下文渲染,如 `.Query`/`.Header`) |
| `ttl` | int(秒) | `0` | 结果缓存时长,`0` 表示不缓存;非 2xx 与网络错误会做短时负缓存以防雪崩 |
| `timeout` | int(秒) | `5` | 单次请求超时 |
| `allow_private` | bool | `false` | 是否允许目标解析到私网/环回地址(拉取内网服务时需开启) |
| `max_body_size` | int(字节) | `2MB` | 响应体大小上限,超出即中止 |
| `fail_policy` | string | `ignore` | `ignore`:失败仅写入 `{{ .Errors.<key> }}` 并继续渲染;`error`:中止渲染并触发 `on_error` 降级 |
| `forward_headers` | []string | — | 透传到目标的请求头名;同时参与缓存键隔离,避免不同身份命中同一缓存 |
| `cache_tags` | []string | — | 给缓存结果附加标签；代理后端返回 `LiteGate-Invalidate: tag-a,tag-b` 时精确失效 |
| `lb_policy` | string | `round_robin` | `service://` 数据源使用的负载均衡策略 |

`url` 除了 `http://` 和 `https://`，还支持网关原生服务地址：

```yaml
template_fragment: "stats-cards" # HX-Request:true 时只执行该命名模板
fetch_json:
  - key: stats
    url: "service://orders/api/stats"
    ttl: 10
    cache_tags: ["orders:{{ header \"X-Tenant-Id\" }}"]
    forward_headers: ["X-Tenant-Id"]
```

`service://` 不直接解析 DNS 地址，而是复用 LiteGate 的服务发现、IDS Selector/Meta、健康实例过滤、负载均衡和 mTLS transport。缓存键自动包含服务发现查询维度；若数据依赖身份 Header，仍须将对应 Header 写入 `forward_headers`，用于传递身份并进一步隔离缓存。

设置 `template_fragment` 后，普通请求执行完整主模板，`HX-Request: true` 请求只执行指定的 `{{ define "..." }}` 命名模板，并自动返回 `Vary: HX-Request`。因此一个 URL 可以同时承担完整页面和 HTMX 局部刷新，无需额外建立 fragment 路由。

推荐让纯 JSON API 不感知网关协议，改由写操作的 `proxy` 路由声明：

```yaml
action:
  type: proxy
  upstream: ["127.0.0.1:9000"]
  on_success:
    invalidate_cache: ["orders:tenant-a"]
    htmx_trigger: ["orders-changed"]
    discard_body: true
```

上游返回 `2xx` 后，LiteGate 清理缓存、生成 `HX-Trigger`，并按需丢弃 JSON 响应体。模板无论来自 `template_root` 目录还是 `template_kv_mode` 的 KV，行为都一致。

为兼容已有系统，业务写接口也可以直接返回：

```http
LiteGate-Invalidate: orders:tenant-a
HX-Trigger: orders-changed
```

前一个 Header 只在网关内部消费并清理匹配的 `fetch_json` 缓存，后一个 Header 原样交给 HTMX 触发页面刷新；新系统优先使用 `on_success`，避免业务 API 耦合这些 Header。

- `{{ .Data.<key> }}`:该 key 拉取并解析后的 JSON 数据。
- `{{ .Errors.<key> }}`:该 key 拉取失败时的错误信息(`ignore` 策略下用于在页面上优雅展示)。

### 🔒 安全注意事项

- **SSRF 防护(默认开启)**:目标主机在**实际拨号时**解析并逐个校验 IP,私网 / 环回 / 链路本地 / 组播 / CGNAT(`100.64.0.0/10`)/ 保留段默认被拦截,除非显式 `allow_private: true`;重定向目标会经同一安全传输层二次校验;仅允许 `http` / `https` 协议;响应体大小与超时强制受限。
- **`forward_headers` 凭证外泄风险** ⚠️:`forward_headers` 会把指定请求头(如 `Authorization`、`Cookie`)原样转发给目标。当前目标 URL **不受白名单限制**,因此**只应向你完全可控的地址转发凭证类请求头**。被误配或被注入的 URL 模板可能把凭证泄露给外部主机——建议 `url` 的 host 部分写死为内网地址,不要用用户输入拼接 host。
- **HTMX 脚本与 CSP**:`{{ htmx }}` 输出的脚本标签**已自动带上本次请求的 nonce**(形如 `<script src="/_litegate/assets/htmx-4.0.0.min.js" nonce="…"></script>`),且始终指向当前内嵌版本——升级 htmx 时不会出现硬编码版本 URL 变 404 的问题。**优先用 `{{ htmx }}`,不要手写脚本标签。** 但 nonce 只有在响应同时带上匹配的 CSP 头时才真正生效:请在 action 上配置 **`template_csp`**(见下)。只有在无法使用该 helper 时才硬编码带版本的 URL,并记得每次升级 htmx 都同步修改。
- **内容安全策略(`template_csp`)**:`{{ .Nonce }}` / `{{ htmx }}` 产生的 nonce 只落在 HTML 正文里,除非 `Content-Security-Policy` 响应头携带**相同**的值,否则不产生任何强制力。`template_csp` 就是用来闭合这条链的:
  - `template_csp: "auto"` 会输出一条严格基线策略:`default-src 'self'; script-src 'self' 'nonce-<本次请求 nonce>'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'`。只有 `{{ htmx }}` 和带 `{{ .Nonce }}` 的内联脚本能执行,其余脚本一律被拦截。(内联 `<style>` 仍通过 `'unsafe-inline'` 放行,如需更严可自行收紧。)
  - 其他任意值被当作**字面策略**,其中的 `{nonce}` 占位符会被替换为本次请求的 nonce,例如 `template_csp: "default-src 'self'; script-src 'nonce-{nonce}'"`。
  - 若 `action.headers` 里已显式设置了 `Content-Security-Policy`,以该显式值为准,`template_csp` 会被跳过。
- **HTMX 4 迁移提醒**:LiteGate 内嵌版本已升级为 4.0.0。父元素上的 HTMX 属性默认不再隐式继承，依赖子元素继承时要为属性添加 `:inherited`；事件名改用新的阶段式命名，例如 `htmx:after:request` 取代 `htmx:afterRequest`，请求/响应事件数据改从 `event.detail.ctx` 读取；v4 默认会替换 4xx/5xx 响应体。旧的无版本资源 URL `/_litegate/assets/htmx.min.js` 返回 410 Gone，并在日志中提示迁移；新模板应使用 `{{ htmx }}` 或带版本 URL。

### 🔌 网关对 HTMX 请求的原生感知(代理后端场景)

当你用 **HTMX + 后端(`type: proxy`)** 的架构时(网关做边缘,后端用 `html/template` 渲染片段),LiteGate 会识别 `HX-Request: true` 请求头并自动做两件事,避免破坏 HTMX 的局部替换语义:

- **错误页不拦截 HTMX 请求**:`error_pages` 在普通整页请求上会把 404/5xx 替换为完整错误页;但对 HTMX 请求(含发送 `Accept: text/html` 的 `hx-boost` 请求)会**自动放行**,让后端返回的 HTML 片段与状态码原样透传——否则整页错误页会被 swap 进某个 `<div>`。
- **SSO 未登录改用 `HX-Redirect`**:受 `auth.type: sso` 保护的路由,未登录时普通请求返回 `302` 跳登录页;而对 HTMX 请求会返回 `401 + HX-Redirect: /_auth/login?next=...`,使 htmx 执行**整页跳转**到登录页,而不是把登录页 swap 进片段容器。

> 此外,所有 `HX-*` 请求/响应头(`HX-Trigger`、`HX-Redirect`、`HX-Push-Url`、`HX-Retarget`、`HX-Reswap` 等)在反向代理时均原样透传(仅按 RFC 7230 剥离 hop-by-hop 头),并支持 HTMX 的 SSE / WebSocket 扩展。OIDC 中间件的鉴权重定向暂未做 HTMX 感知。
