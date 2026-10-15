# CSRF 中间件

默认不自动挂载，也不会因启用 SSO 自动开启。只有显式通过站点或路由的 `use` 引用才生效。

```yaml
site: app.example.com
middlewares:
  browser_csrf:
    type: csrf
    config:
      allowed_origins: "https://frontend.example.com"
      allow_missing_origin: false
/api:
  use: browser_csrf
  proxy: http://127.0.0.1:8080
/webhook:
  proxy: http://127.0.0.1:8080
```

上例只保护 `/api`，定义中间件但不引用不会保护请求。

| 配置 | 默认值 | 说明 |
| --- | --- | --- |
| `enabled` | `true` | 已挂载中间件的开关；false 禁用 |
| `allowed_origins` | 空 | 额外可信来源，逗号分隔的完整 HTTP(S) 来源；拒绝通配符、路径、查询参数和 null |
| `allow_missing_origin` | `false` | 放行同时缺少 Origin 和 Referer 的请求；不放行已有但不可信的来源 |

除 GET、HEAD、OPTIONS 外的所有方法都受检查，包括 PATCH 和 WebDAV 写方法。优先使用 Origin，仅在缺失时回退到 Referer。校验协议、主机和端口，HTTP 80 / HTTPS 443 的显式和隐式端口视为等价。当前请求的同源始终允许，allowed_origins 添加其他可信来源。失败返回 403，不执行后续业务处理。

不会根据 Cookie、Authorization 或 API Key 自动豁免。Webhook 和服务间调用可使用不挂载中间件的独立路由；allow_missing_origin: true 会减弱防护。

同源依据实际 TLS 连接和请求 Host，不信任转发头。前置代理终止 TLS 时，应显式配置浏览器访问的外部可信来源，并限制后端入口访问。

CSRF 与 CORS 独立配置，CORS 不能替代来源校验。此中间件不修改 Dashboard 或 OIDC 登录防护，不提供 CSRF Token。GET 等安全方法应避免修改业务状态，此机制也不能防止 XSS。