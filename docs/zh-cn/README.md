# LiteGate 文档中心

公开文档描述当前代码的使用方式。历史提案、审计和修复过程已移至本地忽略目录，不作为功能承诺。

[中文](../zh-cn/README.md) · [English](../en/README.md)

## 用户手册

- [User guide](user/README.md)
- [Quick start](user/01-getting-started/quick-start.md)
- [构建环境安装](user/01-getting-started/build-environment.md)
- [Cookbook](user/cookbook/README.md)
- [Plugins](user/12-plugins/README.md)

## 使用专题

- [数据库 TCP 资产访问](database-proxy-solution.md)
- [Discovery Provider 开发](discovery-provider-plugin-guide.md)
- [DNS Provider 插件开发指南（证书 DNS-01、DDNS 与 ECH HTTPS 记录）](dns-provider-plugin-guide.md)
- [LiteGate 与 Traefik：Docker、Swarm、Kubernetes 源码能力对比](litegate_traefik_container_capability_matrix.md)
- [Docker Provider 测试指南](docker_provider_testing_guide.md)
- [内网 DNS 自动发布 - 多节点网关支持](dynamic-dns-multi-node.md)
- [LiteGate FastCGI 配置指南](fastcgi_config.md)
- [Forward 隧道与 HTTP 正向代理](forward-vs-forward-proxy.md)
- [IDS：Go 与 WASM 选型](ids-go-vs-wasm.md)
- [IDS 概览](ids-overview.md)
- [IDS 插件约束与排错](ids-plugin-caveats.md)
- [IDS Provider 开发与上线](ids-provider-plugin-guide.md)
- [IDS 业务决策配方](ids-recipes.md)
- [实验性 IDS WASM](ids-wasm-plugin-guide.md)
- [IDS Provider 验收指南](ids_testing_guide.md)
- [Ingress 入口插件](ingress-plugin-guide.md)
- [LiteGate Docker Provider 部署与配置官方指南](litegate_docker_provider_deployment_guide.md)
- [Kubernetes 部署与使用](litegate_k8s_usage_guide.md)
- [Kubernetes 当前能力与边界](litegate_kubernetes_capabilities.md)
- [Kubernetes 能力对标与提升规划（Traefik 开源版）](litegate_k8s_traefik_capability_matrix.md)
- [LiteGate v2 快速上线指南](litegate_lite_quickstart.md)
- [LiteGate MCP 能力表](litegate_mcp_capability_matrix.md)
- [LiteGate 集成 Litemesh MCP 指南 (新架构)](litegate_mcp_integration.md)
- [LiteGate + Litemesh 集成指南](litemesh_integration.md)
- [NATS 能力与责任边界](nats_capability_matrix.md)
- [NATS 联动部署](nats_deployment_guide.md)
- [On-Demand TLS (SaaS 按需证书申请)](on_demand_tls.md)
- [OpenAPI MD5 兼容 Provider](openapi-md5-ids-plugin.md)
- [配置发布控制面](release_control_guide.md)
- [LiteGate 前端 ZIP 托管与 Serve KV 自动化同步模式](serve_kv_mode.md)
- [服务注册与 LiteGate 标签](service_registration_guide.md)
- [服务注册即上线：完整自动化流程验证](service_registration_instant_online.md)
- [LiteGate 服务标签](tag_system_v6_guide.md)

- [Prometheus dashboard](prometheus/LiteGate_Overview.json)

维护规则见 [文档发布说明](../README.md)。
