# LiteGate 用户文档

这一部分面向使用者和运维人员，重点回答三个问题：

- 怎么把 LiteGate 跑起来
- 怎么把网站和服务接进来
- 怎么把它稳定地用在生产环境

## 建议阅读顺序

### 1. 上手

- [安装指南](01-getting-started/installation.md)
- [快速开始](01-getting-started/quick-start.md)
- [第一个站点](01-getting-started/first-site.md)
- [CLI 参考](01-getting-started/cli-reference.md)

### 常用场景案例（推荐从这里开始）

- [Cookbook：按「我要做什么」查找可直接复制的站点配置](cookbook/README.md)
- [常见错误与报错对照](cookbook/04-pitfalls.md)

### 2. 理解配置模型

- [Sites 和 Routes](02-concepts/sites-and-routes.md)
- [Actions 概念](02-concepts/actions.md)
- [路由优先级](02-concepts/routing-priority.md)
- [服务发现概念](02-concepts/discovery.md)
- [服务标签架构](02-concepts/tag-architecture.md)

### 3. 常用配置

- [站点 YAML V2：结构与基本概念](03-configuration/site-yaml-v2-concepts.md)：从简写开始理解地址、路由、动作、继承、配置复用，以及服务标签与站点的 Hybrid 合并
- [配置结构总览与最佳实践](03-configuration/config-structure.md)：先读这篇，了解配置文件的整体结构和推荐组织方式
- [全局配置](03-configuration/global-config.md)
- [站点配置](03-configuration/site-config.md)
- [L4 site 写法与场景指南](03-configuration/l4-guide.md)
- [Stream 配置](03-configuration/stream-config.md)
- [控制 API](03-configuration/api.md)
- [服务标签使用指南](03-configuration/tag-dsl.md)
- [服务标签参考](03-configuration/tag-reference.md)
- [命名 Service 与配置分层](03-configuration/services.md)：`services` 语法、能力该写在哪里、升级注意事项

### 4. Action

- [Proxy](04-actions/proxy.md)
- [Serve](04-actions/serve.md)
- [WebDAV](04-actions/webdav.md)
- [Markdown](04-actions/markdown.md)
- [Template](04-actions/template.md)
- [Status (系统状态)](04-actions/status.md)
- [Redirect](04-actions/redirect.md)
- [Respond](04-actions/respond.md)
- [List](04-actions/list.md)

### 5. 中间件与安全

- [Middleware Pipeline、Chain 与命名能力](05-middleware/pipeline.md)
- [认证](05-middleware/authentication.md)
- [Basic Auth 基本认证](05-middleware/basic-auth.md)
- [OIDC](05-middleware/oidc.md)
- [IDS 治理](05-middleware/ids-governance.md)
- [WAF](05-middleware/waf.md)
- [Rate Limit 与并发连接限制](05-middleware/rate-limit.md)
- [路径改写与重定向](05-middleware/path-and-redirect.md)
- [流量控制与上游治理](05-middleware/traffic-and-upstream.md)
- [Proxy Cache 内容缓存](05-middleware/proxy-cache.md)
- [IP Restriction](05-middleware/ip-restriction.md)
- [CORS](05-middleware/cors.md)
- [Compression](05-middleware/compression.md)

### 6. 证书与发现

- [证书申请配置指南](06-certificates/certificate-application-guide.md)
- [Auto-Cert](06-certificates/auto-cert.md)
- [ECH（Encrypted ClientHello）](06-certificates/ech.md)
- [Connect 证书委托与私钥安全（零信任 E2EE）](06-certificates/connect-csr-delegation.md)
- [On-Demand TLS](06-certificates/on-demand-cert.md)
- [本地 CA（自签自信任）](06-certificates/local-ca.md)
- [DDNS](06-certificates/ddns.md)
- [服务发现源总览](07-discovery/overview.md)
- [Consul](07-discovery/consul.md)
- [Litemesh](07-discovery/litemesh.md)
- [Litemesh mTLS 接入](07-discovery/litemesh-mtls.md)

### 7. 高级场景 (Recipes)

- [同一个 443 承载 HTTPS 与 L4 TCP](09-advanced/shared-443-l4-stream.md)
- [443 端口 L4 SNI 分流与 L7 组合实战（含 caddy-l4 迁移）](09-advanced/sni-routing-recipes.md)
- [通过 443 安全访问数据库](../database-proxy-solution.md)
- [将云 RDS 代理到本地](../rds-forward-guide.md)
- [两层路由：先切上游，再改路径（疑难杂症速查）](09-advanced/two-layer-routing.md)
- [单回调地址分流（OAuth 一个回调地址，多个后端）](09-advanced/oauth-single-callback.md)
- [Circuit Breaker 熔断器](09-advanced/circuit-breaker.md)
- [WebSocket](09-advanced/websocket.md)
- [Magic Ingress](09-advanced/magic-ingress.md)
- [Forward 与 Connect：内网穿透总览](09-advanced/forward-and-connect.md)
- [辨析：Forward (资产映射隧道) 与 Forward Proxy (正向代理) 的区别](../forward-vs-forward-proxy.md)
- [LiteGate Connect 配置与上线](09-advanced/connect.md)
- [使用 CLI 发布内网 HTTP 服务](09-advanced/connect-cli-http.md)
- [Connect 场景与架构指南（电商订单私有化落地）](09-advanced/connect-scenarios.md)

### 8. 观测与运维

- [Dashboard](08-observability/dashboard.md)
- [Metrics](08-observability/metrics.md)
- [Access Log](08-observability/access-log.md)
- [Trace ID](08-observability/trace-id.md)
- [生产部署](10-deployment/production.md)
- [FAQ](11-troubleshooting/faq.md)

### 9. 插件体系 (Plugins)

- [插件体系总览](12-plugins/README.md)：编译期注册表模型、9 大扩展点全景矩阵、内置插件清单与白盒感知
- [编译构建与 CLI 工具](12-plugins/build-and-cli.md)：`litegate build --with` 定制编译、`plugins list / inspect / doctor`、main.go 空导入与 Dockerfile
- [配置与使用指南](12-plugins/configuration.md)：Action、Middleware、Discovery、DNS、IDS、Ingress、KV 等各类插件在 YAML 中的完整实战配置
- [开发者说明与实战](12-plugins/authoring-guide.md)：从零编写 9 大扩展点插件、生命周期与 Dependencies、Manifest 元数据声明与高并发避坑

## 先看什么，后看什么

如果你的目标是：

- 托管一个静态站点和 API
  先看 `quick-start`、`site-config`、`serve`、`proxy`
- 做自动 HTTPS
  先看 `auto-cert`
- 在同一个 443 暴露 HTTPS 与 TLS TCP 服务
  先看 `shared-443-l4-stream`、`stream-config`、`entrypoints`
- 做动态服务接入
  先看 `discovery overview`、`tag-architecture`、`tag-dsl`、`consul`、`magic-ingress`
- 做 SaaS 入口控制
  先看 `authentication`、`remote-auth`、`waf`
- 编写企业自研插件或定制网关
  先看 `12-plugins/README.md`、`12-plugins/authoring-guide.md`、`12-plugins/build-and-cli.md`
