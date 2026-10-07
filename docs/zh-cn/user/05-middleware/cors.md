# CORS (跨域资源共享中间件)

在 LiteGate 中，CORS 中间件用于配置跨域请求策略，解决前端调用其他域名接口时的“跨域报错”问题。

---

## 0. 先确认是否需要 CORS

浏览器只在 **协议、域名、端口** 三者任一不同时才发起跨域检查。如果前端页面和 API 由同一个域名提供，就完全不需要 CORS：

```yaml
# app.example.com：前端静态文件由网关内置 serve 提供
domain: app.example.com
routes:
  - match: { path_prefix: / }
    action:
      type: serve
      root: /var/www/app
```

后端服务注册到 LiteGate 的服务发现（如 LiteMesh / Consul）时，通过标签声明同一个域名下的 `/api` 路径，
网关会把它与上面的静态站点合并为同一个站点，前端用相对路径 `/api/...` 调用即为同源请求。

以下情况仍然需要 CORS：

*   API 使用了不同的子域名（如 `api.example.com`）、端口或协议。
*   本地开发时前端运行在 `http://localhost:5173` 等开发服务器上，直接调用网关。
*   其他域名的前端（H5、管理后台、第三方页面）需要调用同一套 API。
*   字体等静态资源放在另一个域名 (CDN) 上。

---

## 1. 快速开始

最简单的写法是只打开开关：

```yaml
routes:
  - match: { path_prefix: / }
    action:
      type: proxy
      service_name: my-backend
      cors:
        enabled: true
```

`enabled: true` 且未填写其他字段时，默认值为：

| 字段 | 默认值 |
|---|---|
| `allowed_origins` | `*`（任意来源） |
| `allowed_methods` | `GET, POST, PUT, DELETE, PATCH, OPTIONS` |
| `allowed_headers` | `*`（预检时按请求回显，包括 `Authorization`） |
| `allow_credentials` | `false` |
| `max_age` | `3600` |

这是 **匿名跨域**：响应头为 `Access-Control-Allow-Origin: *`，浏览器不会携带 Cookie。
适合公开 API；需要登录态的接口请使用下文的凭证模式。

---

## 2. 精细化配置

### 方式 A：路由内联配置 (推荐)

```yaml
domain: api.example.com
routes:
  - match: { path_prefix: /api }
    action:
      type: proxy
      service_name: backend-svc
      cors:
        enabled: true
        # 允许的来源：必须列出具体来源才能开启凭证
        allowed_origins: ["https://web.example.com", "https://admin.example.com"]
        allowed_methods: ["GET", "POST", "PUT", "DELETE"]
        allowed_headers: ["Authorization", "Content-Type"]
        # 允许前端脚本读取的响应头
        exposed_headers: ["X-Request-ID"]
        # 是否允许携带凭证 (Cookie / HTTP 认证)
        allow_credentials: true
        max_age: 3600
```

### 方式 B：命名中间件 (可重用)

在站点的 `middlewares` 中定义，然后在多个路由中通过名字引用。

```yaml
domain: api.example.com
middlewares:
  web-cors:
    type: cors
    config:
      allowed_origins: "https://web.example.com, https://admin.example.com"
      allow_credentials: "true"

routes:
  - match: { path_prefix: /api }
    action:
      type: proxy
      service_name: backend-svc
    middlewares: ["web-cors"]
```

服务发现标签中的写法：

```properties
litegate.http.routers.api.middlewares=web-cors
litegate.http.middlewares.web-cors.cors.allowed_origins=https://web.example.com
litegate.http.middlewares.web-cors.cors.allow_credentials=true
```

### 开关说明
*   `enabled: true`：开启，并为未填写的字段使用上表中的默认值。**不会** 自动开启凭证。
*   `enabled: false`：**强行关闭**。即使配置了 `allowed_origins` 列表，该中间件也不会生效。
*   (不配置 `enabled`)：向前兼容模式。配置了 `allowed_origins` 列表则开启，否则关闭。

### 来源匹配
*   来源按精确值匹配，忽略大小写和末尾的 `/`。
*   `*` 代表任意来源。

---

## 3. 凭证 (Cookie) 与安全限制

`allow_credentials: true` **必须** 配合明确列出的 `allowed_origins` 使用。
以下配置会在加载时直接报错：

```yaml
cors:
  allowed_origins: ["*"]      # 或 enabled: true 且未填写 allowed_origins
  allow_credentials: true     # ❌ 加载失败
```

原因：“任意来源 + 凭证” 意味着任何网站都能以当前登录用户的身份调用接口并读取返回内容。
浏览器规范本身也不接受 `Access-Control-Allow-Origin: *` 与凭证同时出现。

来自 Kubernetes Ingress / Gateway API 等翻译来源的配置不会因此加载失败：
遇到 `*` 与凭证同时出现时，网关按匿名跨域处理（不发送 `Access-Control-Allow-Credentials`），并在日志中给出警告。

在凭证模式下，`allowed_methods` / `allowed_headers` 中的 `*` 会按请求回显具体的方法和请求头，
`exposed_headers: ["*"]` 会列出本次响应实际携带的响应头，以符合浏览器对凭证请求的要求。

---

## 4. 预检请求 (Pre-Flight) 处理

带有 `Origin` 和 `Access-Control-Request-Method` 的 `OPTIONS` 请求是预检请求，由网关直接返回 **204 No Content**，不会转发到后端：

*   来源被允许：返回完整的 `Access-Control-Allow-*` 响应头。
*   来源不被允许：返回不带 CORS 头的 204，浏览器会拒绝随后的实际请求。

不带 `Access-Control-Request-Method` 的普通 `OPTIONS` 请求（例如 WebDAV 的 `OPTIONS`）会照常交给路由的 action 处理。

预检在鉴权之前处理，因此不会被鉴权中间件拦截。

---

## 5. 与后端 CORS 头的关系

路由配置了 CORS 之后，**CORS 响应头由网关负责**：

*   后端返回的 `Access-Control-*` 响应头会被网关的策略替换，不会出现重复的 `Access-Control-Allow-Origin`，也不会被后端的宽松配置绕过。
*   网关在响应头最终发出时才写入 CORS 头，后端的同名响应头无法覆盖。
*   `Vary: Origin` 会与后端的 `Vary`（如 `Accept-Encoding`）合并，而不是被覆盖，避免 CDN 或浏览器缓存把一个来源的响应返回给另一个来源。

因此后端开着 CORS 也不会冲突；如果想让后端完全接管 CORS，就不要在网关上配置。

如需改写其他响应头，可以使用 `headers` 中间件的 `response.*`，同样会覆盖后端返回的同名头：

```properties
litegate.http.routers.api.middlewares=security-headers
litegate.http.middlewares.security-headers.headers.response.X-Frame-Options=DENY
```

---

## 6. 常见问题 (FAQ)

### 配置后依然报跨域错误？
1.  **检查来源是否完全一致**：包括协议和端口，例如 `http://localhost:5173` 与 `http://127.0.0.1:5173` 是不同来源。
2.  **需要 Cookie 却没有生效**：确认配置了 `allow_credentials: true` 且 `allowed_origins` 列出了具体来源，前端请求也需要设置 `credentials: "include"` / `withCredentials: true`。
3.  **自定义请求头被拒绝**：`allowed_headers` 写成具体列表时，需要包含前端实际发送的头（如 `Authorization`、`Content-Type`）；不确定时可以使用 `*`。

---

## 延伸阅读
- [配置反向代理 API](../04-actions/proxy.md)
- [配置身份认证保护接口](./authentication.md)
