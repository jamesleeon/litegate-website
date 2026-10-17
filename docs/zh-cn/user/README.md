# LiteGate 用户手册

从安装、快速开始和第一个站点开始；再按任务查阅参考。中英文目录采用同一主题和路径。

[中文](../../zh-cn/user/README.md) · [English](../../en/user/README.md)

## 上手

- [构建指南 (Build from Source)](01-getting-started/build.md)
- [构建环境安装](01-getting-started/build-environment.md)
- [CLI 命令行参考](01-getting-started/cli-reference.md)
- [第一个站点配置示例 (First Site)](01-getting-started/first-site.md)
- [安装指南](01-getting-started/installation.md)
- [快速开始](01-getting-started/quick-start.md)

## 核心概念

- [Actions 详解：请求处理模型](02-concepts/actions.md)
- [服务发现集成原理](02-concepts/discovery.md)
- [路由优先级解析 (Routing Priority)](02-concepts/routing-priority.md)
- [理解 Sites 与 Routes](02-concepts/sites-and-routes.md)
- [LiteGate 服务标签架构](02-concepts/tag-architecture.md)
- [Unified Entry Model](02-concepts/unified-entry-model.md)

## 配置

- [控制 API 参考 (Control API)](03-configuration/api.md)
- [配置结构总览与最佳实践](03-configuration/config-structure.md)
- [Entrypoints（监听入口）](03-configuration/entrypoints.md)
- [全局配置参考 (`config.yaml`)](03-configuration/global-config.md)
- [L4 Stream Guide](03-configuration/l4-guide.md)
- [Rewrite：路径与查询参数改写](03-configuration/rewrite.md)
- [命名 Service 与配置分层](03-configuration/services.md)
- [站点配置参考 (`sites/*.yaml`)](03-configuration/site-config.md)
- [站点 YAML V2：结构与基本概念](03-configuration/site-yaml-v2-concepts.md)
- [Stream 配置参考 (L4 代理)](03-configuration/stream-config.md)
- [LiteGate 服务标签使用指南](03-configuration/tag-dsl.md)
- [LiteGate 服务标签参考](03-configuration/tag-reference.md)
- [上游自定义 DNS](03-configuration/upstream-dns.md)

## Actions

- [List Action (目录浏览)](04-actions/list.md)
- [Markdown Action (文档渲染服务)](04-actions/markdown.md)
- [可靠事件通知（持久化、离线续推与应用确认）](04-actions/nats-events.md)
- [NATS 实时事件订阅](04-actions/nats-sse.md)
- [Proxy Action (反向代理)](04-actions/proxy.md)
- [Redirect Action (重定向处理)](04-actions/redirect.md)
- [Respond Action (直接响应)](04-actions/respond.md)
- [Serve Action (静态文件服务)](04-actions/serve.md)
- [Status Action (系统状态监控看板)](04-actions/status.md)
- [Template Action (服务端模板与站点渲染)](04-actions/template.md)
- [WebDAV Action (文件管理服务)](04-actions/webdav.md)

## 中间件与安全

- [Authentication (网关身份认证与治理概述)](05-middleware/authentication.md)
- [authentik OIDC 配置样例](05-middleware/authentik.md)
- [HTTP Basic Auth](05-middleware/basic-auth.md)
- [Compression (智能压缩)](05-middleware/compression.md)
- [CORS (跨域资源共享中间件)](05-middleware/cors.md)
- [Forward Auth 外部鉴权](05-middleware/forward-auth.md)
- [IDS 请求治理](05-middleware/ids-governance.md)
- [IP Restriction (IP 访问控制)](05-middleware/ip-restriction.md)
- [OIDC / OAuth2 认证配置指南](05-middleware/oidc.md)
- [路径改写与重定向](05-middleware/path-and-redirect.md)
- [Middleware Pipeline 与 Chain](05-middleware/pipeline.md)
- [Proxy Cache (反向代理内容缓存)](05-middleware/proxy-cache.md)
- [限流（V2 配置）](05-middleware/rate-limit.md)
- [扫描防护与治理规则](05-middleware/scan-protection.md)
- [流量控制与上游治理](05-middleware/traffic-and-upstream.md)
- [WAF (Web 应用防火墙)](05-middleware/waf.md)

- [Remote Auth](05-middleware/remote-auth.md)

## 证书

- [Auto-Cert (自动化证书管理)](06-certificates/auto-cert.md)
- [证书申请方式与配置](06-certificates/certificate-application-guide.md)
- [Connect CSR 证书委托](06-certificates/connect-csr-delegation.md)
- [CredKeeper 集中凭据托管](06-certificates/credkeeper.md)
- [DDNS 动态域名解析](06-certificates/ddns.md)
- [添加 DNS 服务商](06-certificates/dns-providers.md)
- [ECH：隐藏网站的 TLS ClientHello](06-certificates/ech.md)
- [本地 CA (Local CA / 自签自信任)](06-certificates/local-ca.md)
- [局域网 CA 与服务间 mTLS 实战](06-certificates/lan-ca-and-mtls.md)
- [On-Demand TLS (按需签发证书)](06-certificates/on-demand-cert.md)
- [密文配置（Sealed Secrets）](06-certificates/sealed-secrets.md)

## 服务发现

- [Consul 服务发现](07-discovery/consul.md)
- [Nomad 服务发现与插件配置](07-discovery/nomad.md)
- [Litemesh mTLS 接入指南](07-discovery/litemesh-mtls.md)
- [Litemesh 服务发现](07-discovery/litemesh.md)
- [服务发现源总览](07-discovery/overview.md)

## 可观测性

- [Access Log (访问日志)](08-observability/access-log.md)
- [Dashboard API 参考](08-observability/dashboard-api.md)
- [Web Dashboard (可视控制面板)](08-observability/dashboard.md)
- [Metrics (监控指标)](08-observability/metrics.md)
- [Trace ID (分布式追踪)](08-observability/trace-id.md)

## 高级场景

- [熔断（V2 配置）](09-advanced/circuit-breaker.md)
- [使用 CLI 发布内网 HTTP 服务](09-advanced/connect-cli-http.md)
- [Connect 场景与部署职责](09-advanced/connect-scenarios.md)
- [LiteGate Connect 配置与上线指南](09-advanced/connect.md)
- [事件通知与离线投递](09-advanced/event-notification.md)
- [Forward 与 Connect](09-advanced/forward-and-connect.md)
- [Magic Ingress (零配置服务接入)](09-advanced/magic-ingress.md)
- [Notify 与业务 JWT 接入](09-advanced/notify-jwt-integration.md)
- [单一 OAuth 回调地址选路](09-advanced/oauth-single-callback.md)
- [共享 443：HTTPS 与 L4 Stream](09-advanced/shared-443-l4-stream.md)
- [SNI 分流实战](09-advanced/sni-routing-recipes.md)
- [选上游与改路径](09-advanced/two-layer-routing.md)
- [WebSocket 代理](09-advanced/websocket.md)

## 部署

- [压测与性能归因](10-deployment/benchmarking.md)
- [多副本状态与故障隔离](10-deployment/ha-state.md)
- [Kubernetes 部署手册](10-deployment/kubernetes.md)
- [生产环境部署建议 (Production Best Practices)](10-deployment/production.md)
- [Systemd 部署指南 (Linux)](10-deployment/systemd.md)

## 排错

- [故障排查与调试 (Debugging Guide)](11-troubleshooting/debugging.md)
- [常见问题 (FAQ)](11-troubleshooting/faq.md)

## 插件

- [插件开发契约](12-plugins/authoring-guide.md)
- [插件构建与 CLI](12-plugins/build-and-cli.md)
- [插件配置位置与校验](12-plugins/configuration.md)
- [插件体系总览](12-plugins/README.md)

## 配置实例

- [基础：静态站点与 API](cookbook/01-basics.md)
- [路径：匹配与改写](cookbook/02-paths.md)
- [治理：入口限制与后端策略](cookbook/03-governance.md)
- [常见配置问题](cookbook/04-pitfalls.md)
- [发现：Service 与注册标签](cookbook/05-discovery.md)
- [命名请求条件](cookbook/06-matchers.md)
- [配置 Cookbook](cookbook/README.md)


- [????????????????](05-middleware/bandwidth.md)
