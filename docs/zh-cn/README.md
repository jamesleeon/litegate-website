# LiteGate 文档中心

LiteGate 是单一二进制的 HTTP / TCP 网关：放在网站、API 和内网服务前面，负责接收流量、自动配置 HTTPS、按规则转发。本文档描述当前代码的使用方式。

[中文](../zh-cn/README.md) · [English](../en/README.md)

不需要从头读到尾。建议按下面四步走：**先跑通 → 找到自己的场景 → 需要时查参考 → 上线前看部署**。

---

## 第一步：跑起来（约 5 分钟）

1. [安装](user/01-getting-started/installation.md)：下载二进制、Docker 或源码构建
2. [快速开始](user/01-getting-started/quick-start.md)：零配置启动，写第一个站点
3. [入门案例：一个站点跑起来](user/cookbook/01-basics.md)：反向代理、静态站、HTTPS、负载均衡，每段配置都由自动化测试验证，复制即可用

---

## 第二步：按场景配置

找到和你需求最接近的场景，先照着「入门」改成自己的域名和后端，用到时再读「进阶」。

### 发布网站或前端应用

- 入门：[路径分流、改写与跳转](user/cookbook/02-paths.md)
- 进阶：[Serve：静态文件与 SPA](user/04-actions/serve.md) · [Markdown 文档站](user/04-actions/markdown.md) · [目录浏览](user/04-actions/list.md) · [WebDAV](user/04-actions/webdav.md) · [服务端模板](user/04-actions/template.md) · [PHP / FastCGI](fastcgi_config.md) · [前端包 KV 发布](serve_kv_mode.md)

### 给多个后端做 API 网关

- 入门：[跨域、请求头、限流案例](user/cookbook/03-governance.md) · [Proxy 反向代理](user/04-actions/proxy.md)
- 进阶：[命名 Service 与配置分层](user/03-configuration/services.md) · [流量与上游治理](user/05-middleware/traffic-and-upstream.md) · [熔断](user/09-advanced/circuit-breaker.md) · [代理缓存](user/05-middleware/proxy-cache.md) · [WebSocket](user/09-advanced/websocket.md) · [按方法、请求头匹配](user/cookbook/06-matchers.md) · [两层路由](user/09-advanced/two-layer-routing.md)

### 服务上线自动挂路由（服务发现）

- 入门：[服务发现概览](user/07-discovery/overview.md) · [服务标签使用指南](user/03-configuration/tag-dsl.md) · [前端 + 自动发现后端案例](user/cookbook/05-discovery.md)
- 进阶：[服务注册与 LiteGate 标签](service_registration_guide.md) · [Magic Ingress](user/09-advanced/magic-ingress.md) · [Consul](user/07-discovery/consul.md) · [Litemesh](user/07-discovery/litemesh.md) · [Litemesh mTLS](user/07-discovery/litemesh-mtls.md) · [Nomad](user/07-discovery/nomad.md)
- Docker：[Docker Provider 部署与配置](litegate_docker_provider_deployment_guide.md) · [Docker catalog 身份与传输](docker_catalog_identity_and_transport.md) · [Docker Provider 测试指南](docker_provider_testing_guide.md)
- Kubernetes：[Kubernetes 部署手册](user/10-deployment/kubernetes.md) · [Kubernetes 部署与使用](litegate_k8s_usage_guide.md) · [Kubernetes 当前能力与边界](litegate_kubernetes_capabilities.md)

### 把内网服务发布到公网 / 远程访问内网资产

- 入门：[Connect 配置指南](user/09-advanced/connect.md) · [Connect 典型场景](user/09-advanced/connect-scenarios.md) · [数据库 TCP 资产访问](database-proxy-solution.md)
- 进阶：[Forward 与 Connect 怎么选](user/09-advanced/forward-and-connect.md) · [Forward 隧道与 HTTP 正向代理](forward-vs-forward-proxy.md) · [Connect 命令行与 HTTP 接口](user/09-advanced/connect-cli-http.md) · [Ingress 入口插件](ingress-plugin-guide.md)

### 证书与 HTTPS

- 入门：[自动证书](user/06-certificates/auto-cert.md) · [证书申请指南](user/06-certificates/certificate-application-guide.md)
- 进阶：[DNS 服务商](user/06-certificates/dns-providers.md) · [本地 CA](user/06-certificates/local-ca.md) · [按需证书](user/06-certificates/on-demand-cert.md) · [On-Demand TLS（SaaS）](on_demand_tls.md) · [动态 DNS](user/06-certificates/ddns.md) · [内网 DNS 多节点发布](dynamic-dns-multi-node.md) · [ECH](user/06-certificates/ech.md) · [局域网 CA 与 mTLS](user/06-certificates/lan-ca-and-mtls.md) · [Connect CSR 委托](user/06-certificates/connect-csr-delegation.md) · [credkeeper](user/06-certificates/credkeeper.md) · [Sealed Secrets](user/06-certificates/sealed-secrets.md)

### 登录与安全防护

- 入门：[认证方式总览](user/05-middleware/authentication.md) · [Basic Auth](user/05-middleware/basic-auth.md) · [IP 限制](user/05-middleware/ip-restriction.md) · [限流](user/05-middleware/rate-limit.md)
- 进阶：[OIDC / OAuth2](user/05-middleware/oidc.md) · [Authentik 样例](user/05-middleware/authentik.md) · [OAuth 单回调地址](user/09-advanced/oauth-single-callback.md) · [Forward Auth](user/05-middleware/forward-auth.md) · [Remote Auth](user/05-middleware/remote-auth.md) · [WAF](user/05-middleware/waf.md) · [扫描防护](user/05-middleware/scan-protection.md) · [CSRF](user/05-middleware/csrf.md) · [CORS](user/05-middleware/cors.md) · [带宽限制](user/05-middleware/bandwidth.md) · [压缩](user/05-middleware/compression.md)

### 实时消息推送

- 入门：[事件通知指南](user/09-advanced/event-notification.md) · [NATS 联动部署](nats_deployment_guide.md)
- 进阶：[JWT 鉴权与限制](user/09-advanced/notify-jwt-integration.md) · [可靠事件通知](user/04-actions/nats-events.md) · [NATS SSE](user/04-actions/nats-sse.md) · [NATS 能力与责任边界](nats_capability_matrix.md)

### TCP / UDP 与共用 443

- 入门：[L4 指南](user/03-configuration/l4-guide.md)
- 进阶：[共用 443 的 L4 Stream](user/09-advanced/shared-443-l4-stream.md) · [SNI 分流配方](user/09-advanced/sni-routing-recipes.md)

### 多租户 SaaS（IDS）

- 入门：[IDS 概览](ids-overview.md) · [IDS 业务决策配方](ids-recipes.md)
- 进阶：[IDS Provider 开发与上线](ids-provider-plugin-guide.md) · [IDS 插件约束与排错](ids-plugin-caveats.md) · [IDS Provider 验收指南](ids_testing_guide.md) · [Go 与 WASM 选型](ids-go-vs-wasm.md) · [实验性 IDS WASM](ids-wasm-plugin-guide.md) · [OpenAPI MD5 兼容 Provider](openapi-md5-ids-plugin.md) · [IDS 流量治理](user/05-middleware/ids-governance.md)

遇到问题先看 [常见坑](user/cookbook/04-pitfalls.md)，更多案例见 [Cookbook](user/cookbook/README.md)。

---

## 第三步：理解与查参考

- 概念：[站点与路由](user/02-concepts/sites-and-routes.md) · [Actions](user/02-concepts/actions.md) · [路由优先级](user/02-concepts/routing-priority.md) · [统一入口模型](user/02-concepts/unified-entry-model.md) · [服务标签架构](user/02-concepts/tag-architecture.md) · [服务发现原理](user/02-concepts/discovery.md)
- 配置参考：[站点 YAML 结构与字段](user/03-configuration/site-yaml-v2-concepts.md) · [站点配置参考](user/03-configuration/site-config.md) · [全局配置 `config.yaml`](user/03-configuration/global-config.md) · [配置结构与最佳实践](user/03-configuration/config-structure.md) · [Entrypoints](user/03-configuration/entrypoints.md) · [Stream 配置](user/03-configuration/stream-config.md) · [Rewrite](user/03-configuration/rewrite.md) · [上游 DNS](user/03-configuration/upstream-dns.md) · [服务标签参考](user/03-configuration/tag-reference.md) · [控制 API](user/03-configuration/api.md)
- 中间件：[执行顺序](user/05-middleware/pipeline.md) · [路径与跳转](user/05-middleware/path-and-redirect.md)
- 其他动作：[Respond](user/04-actions/respond.md) · [Redirect](user/04-actions/redirect.md) · [Status 看板](user/04-actions/status.md)
- 命令行：[CLI 参考](user/01-getting-started/cli-reference.md)
- 完整目录：[用户手册](user/README.md)

---

## 第四步：上生产与扩展

- 部署：[生产部署](user/10-deployment/production.md) · [systemd](user/10-deployment/systemd.md) · [高可用与状态](user/10-deployment/ha-state.md) · [压测](user/10-deployment/benchmarking.md) · [配置发布控制面](release_control_guide.md)
- 观测：[Dashboard](user/08-observability/dashboard.md) · [Dashboard API](user/08-observability/dashboard-api.md) · [指标](user/08-observability/metrics.md) · [访问日志](user/08-observability/access-log.md) · [Trace ID](user/08-observability/trace-id.md) · [官方 Grafana 面板](https://github.com/jamesleeon/LiteGate/tree/master/deploy/grafana) · [MCP 能力表](litegate_mcp_capability_matrix.md)
- 排错：[调试](user/11-troubleshooting/debugging.md) · [常见问题](user/11-troubleshooting/faq.md)
- 扩展：[插件](user/12-plugins/README.md) · [插件开发](user/12-plugins/authoring-guide.md) · [构建与命令行](user/12-plugins/build-and-cli.md) · [插件配置](user/12-plugins/configuration.md) · [Discovery 插件（Nomad 样例）](discovery-provider-plugin-guide.md) · [DNS Provider 插件](dns-provider-plugin-guide.md)
- 源码构建：[构建指南](user/01-getting-started/build.md) · [构建环境安装](user/01-getting-started/build-environment.md)

维护规则见 [文档发布说明](../README.md)。
