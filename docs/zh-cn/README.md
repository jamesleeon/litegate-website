# LiteGate 文档中心

LiteGate 是一个动态网关：把静态站点、API 反代、自动证书、服务发现与身份治理统一在同一套路由模型里。

> 新用户**从用户手册开始**即可。需要深入原理或做二次开发时，再阅读「架构与设计」和「二次开发」。

---

## 📖 用户手册（从这里开始）

完整手册见 **[用户手册索引](user/README.md)**，按使用阶段编号组织（01 上手 → 11 排错）。

**最短路径：**
- **[LiteGate 深度介绍与全景对比](introduction.md)**：架构定位、核心代码亮点、对标主流网关及优缺点深度剖析
- [安装](user/01-getting-started/installation.md) → [快速开始](user/01-getting-started/quick-start.md) → [第一个站点](user/01-getting-started/first-site.md)
- [CLI 命令参考](user/01-getting-started/cli-reference.md)

**按目标查阅：**
- 托管静态站 + 反代 API：[站点配置](user/03-configuration/site-config.md) · [serve](user/04-actions/serve.md) · [proxy](user/04-actions/proxy.md) · [前端 ZIP 同步](serve_kv_mode.md)
- 网关模板与 API 页面聚合：[Template Action](user/04-actions/template.md) · [Caddy templates 对比](caddy-template-vs-litegate-template.md)
- 反代 PHP / PHP-FPM：[FastCGI 配置](fastcgi_config.md)
- 自动 HTTPS：[Auto-Cert](user/06-certificates/auto-cert.md) · [按需 TLS](user/06-certificates/on-demand-cert.md) · [DDNS](user/06-certificates/ddns.md)
- 共享 443 承载 HTTPS 与 L4 TCP：[SNI 端口共享与 Unix Socket](user/09-advanced/shared-443-l4-stream.md)
- 通过 443 安全访问 MySQL / PostgreSQL：[LiteGate Forward 数据库隧道](database-proxy-solution.md)
- 将云 RDS 代理到本地：[RDS Forward 完整部署指南](rds-forward-guide.md)
- 一个客户端通过 443 访问多个办公 TCP 服务：[Forward 多映射与热加载升级方案](https://github.com/jamesleeon/LiteGate/blob/master/docs/zh-cn/forward-multi-mapping-design.md)
- 内网穿透怎么选（Forward 与 Connect 的区别、组合与传输协议）：[Forward 与 Connect 总览](user/09-advanced/forward-and-connect.md)
- **概念辨析**：[Forward (资产映射隧道) 与 Forward Proxy (正向代理) 的本质区别](forward-vs-forward-proxy.md)
- 通过云 VPS 发布 Home LiteGate 服务：[LiteGate Connect 配置指南](user/09-advanced/connect.md) · [架构方案](https://github.com/jamesleeon/LiteGate/blob/master/docs/zh-cn/litegate-connect-design.md)
- 数据库安全代理：[数据库安全代理方案与实现指南](database-proxy-solution.md)
- 服务发现：[Litemesh](user/07-discovery/litemesh.md) · [Consul](user/07-discovery/consul.md) · [标签架构](user/02-concepts/tag-architecture.md) · [服务标签指南](user/03-configuration/tag-dsl.md) · [标签参考](user/03-configuration/tag-reference.md)
- SaaS 入口治理：[认证](user/05-middleware/authentication.md) · [IDS 治理](user/05-middleware/ids-governance.md) · [WAF](user/05-middleware/waf.md)
- 可观测性：[Dashboard](user/08-observability/dashboard.md) · [Metrics](user/08-observability/metrics.md) · [访问日志](user/08-observability/access-log.md)
- 配置发布与回滚：[配置发布控制面（Release Control）](release_control_guide.md)：草稿 → 校验 → 发布 → 回滚
- 生产部署：[最佳实践](user/10-deployment/production.md) · [systemd](user/10-deployment/systemd.md)

---

## 🧠 架构与设计

理解 LiteGate「标签驱动」的设计哲学与请求生命周期。

- [架构白皮书](ARCHITECTURE_WHITE_PAPER_ZH.md)
- [L7 执行流](l7_execution_flow.md)：请求在网关内部如何流转
- [Middleware 架构优化方案](https://github.com/jamesleeon/LiteGate/blob/master/docs/zh-cn/middleware-architecture-optimization-plan.md)：统一执行流水线、配置编译、插件契约、生命周期与兼容迁移设计
- [网关分层与职责边界设计](https://github.com/jamesleeon/LiteGate/blob/master/docs/zh-cn/gateway-layering-design.md)：EntryPoint / Router / Middleware / Service / Handler 的职责划分、能力归属表与迁移步骤
- [Tag 系统指南](tag_system_v6_guide.md)
- [IDS 概览：是什么，为什么需要它](ids-overview.md)：定位、心智模型、IDS vs middleware、对标友商（入口先读）
- [IDS 治理指南](user/05-middleware/ids-governance.md)：请求转发前的验证、直接响应、Header 注入和动态选路
- [IDS Provider 架构](ids-architecture-v2.md)：统一决策模型、动态配置以及 Selector/Meta 候选池语义
- [IDS 架构、场景与样例（HTML）](ids-architecture-guide.html)：面向架构师和插件开发者的可视化完整说明
- [Magic Ingress 设计](magic_ingress_architecture_zh.md)：打标即上线
- [LiteGate Connect 架构方案](https://github.com/jamesleeon/LiteGate/blob/master/docs/zh-cn/litegate-connect-design.md)：Cloud 只做 SNI/L4 分流，Home 负责 TLS/L7
- [LiteGate Connect 全双活高可用架构方案](https://github.com/jamesleeon/LiteGate/blob/master/docs/zh-cn/litegate-connect-ha-design.md)：N Cloud × M Private 网状双活、消除互相踢出、一致性仲裁与毫秒级漂移
- [TLS / mTLS 安全架构](tls_mtls_architecture.md)

---

## 🔌 生态集成

- [HTTP → NATS 旧业务资产整合方案](https://github.com/jamesleeon/LiteGate/blob/master/docs/zh-cn/nats_legacy_asset_integration_design.md)：以可选客户端 Action 接入 Delphi/FPC 等存量业务，不嵌入 NATS Server
- [Kubernetes 消费与声明式路由实战指南](litegate_kubernetes_user_guide.md) · [轻量级设计方案](litegate_lightweight_k8s_integration.md)
- [Docker Provider 部署指南](litegate_docker_provider_deployment_guide.md)
- [Litemesh 集成](litemesh_integration.md)
- [服务注册与即时上线](service_registration_instant_online.md) · [服务标签实战](service_registration_guide.md)
- [MCP Server 集成](litegate_mcp_integration.md) · [能力矩阵](litegate_mcp_capability_matrix.md)
- [按需 TLS / mTLS](on_demand_tls.md)
- [动态 DNS 多节点](dynamic-dns-multi-node.md)
- [Prometheus 监控面板](https://github.com/jamesleeon/LiteGate/blob/master/docs/zh-cn/prometheus)

---

## 🛠️ 二次开发

- **[插件体系用户手册与完整实战](user/12-plugins/README.md)**：[总览](user/12-plugins/README.md) · [定制编译与 CLI](user/12-plugins/build-and-cli.md) · [配置参考](user/12-plugins/configuration.md) · [9大扩展点开发指南](user/12-plugins/authoring-guide.md)
- [插件体系底层架构](plugin-architecture.md)：编译期注册表（Caddy 风格）的设计取舍与接缝
- [DNS Provider 插件指南](dns-provider-plugin-guide.md) · [Discovery 发现源插件指南](discovery-provider-plugin-guide.md) · [Ingress 插件指南](ingress-plugin-guide.md)
- [IDS Provider 选型：Go vs WASM](ids-go-vs-wasm.md)：两种实现层的能力边界与决策指引（WASM 当前为实验性、默认不编译）
- [IDS 配方](ids-recipes.md)：Session 查找、签名校验、切库/切集群、灰度、动态限流等端到端可抄场景
- [IDS Provider 插件开发与配置](ids-provider-plugin-guide.md)：实现统一 Provider，并管理动态配置、缓存和外部依赖
- [IDS 插件开发注意事项与避坑指南](ids-plugin-caveats.md)：单例并发、Context 传递、业务拒绝 vs 错误、Header 白名单与缓存穿透防护
- [OpenAPI MD5 IDS Provider](openapi-md5-ids-plugin.md)：兼容旧 MD5 Body 签名协议，验证成功后转发默认下游
- [IDS 测试规范](https://github.com/jamesleeon/LiteGate/blob/master/docs/zh-cn/ids_testing_guide.md)
