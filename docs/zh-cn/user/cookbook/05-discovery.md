# 发现：Service 与注册标签

服务发现提供地址与健康状态，配置监听提供站点配置，二者角色分开。Service 中 discovery 与 servers 二选一。Catalog 与注册标签可生成路由，仍需显式暴露标识和有效配置。

先检查发现源认证、namespace、服务名与端口，再检查标签 DSL、Selector、健康实例和实际 LB 选择。Consul/LiteMesh/Kubernetes 的资源模型不同，不能只替换 provider 名就保证行为相同。

## 相关文档与代码

- [Discovery](../07-discovery/overview.md)
- [Service configuration](../03-configuration/services.md)
- [Tags](../03-configuration/tag-dsl.md)
