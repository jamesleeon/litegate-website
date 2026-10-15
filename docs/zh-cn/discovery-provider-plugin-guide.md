# Discovery Provider 开发

Discovery Provider 向宿主提供服务快照与 Endpoint，适合第三方注册中心。实现 ListServices(ctx) 与 Resolve(ctx, query)，通过 RegisterDiscoveryProvider 注册 Validate、Factory 和 Info。可选 Watch 与生命周期负责变化通知和资源释放。

DiscoveryQuery.Namespace 需映射到实际注册中心；Catalog 先用服务自身 Namespace，否则回退到 Catalog 配置或 default。Resolve/ListServices 可以并发调用，返回切片、Tags、Metadata 都是不可继续修改的快照。

宿主负责 Endpoint 校验、数量限制、深拷贝、筛选、健康、缓存、多源融合与 LB。插件不直接访问 Router 或连接池；Kubernetes 路由控制器不是这个服务/Endpoint 接口。遵守 context、鉴权和秘密管理，验证空结果、断流、重连和关闭。

## 相关文档与代码

- [Public contract](../../pkg/plugin/discovery.go)
- [Discovery overview](user/07-discovery/overview.md)
- [Plugin build](user/12-plugins/build-and-cli.md)
