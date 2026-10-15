# 插件配置位置与校验

先编译插件，再通过已注册名称引用。下表为实际配置入口，不把未来方案当作有效语法。

| 类型 | 配置入口 |
|---|---|
| Action | routes[].action.type，私有字段由插件 Decode |
| Middleware | middlewares.<instance>.type/config；V2 路由用 use 引用；兼容格式用 middlewares 列表 |
| LoadBalancer | action.lb_policy 或 Service 对应策略 |
| KV | action.kv_provider / kv_key |
| Ingress | 全局 ingress_plugins，绑定 entrypoints |
| Discovery | service_discovery.catalogs[].provider |
| DNS | auto_cert.dns_providers[].type/config |
| IDS | action.ids.provider/options |
| Template Func | 模板函数注册名 |

全局 plugin_config.path/watch 指定动态插件配置文件；路由 options 提供每请求策略，不应存储数据库口令。配置定义不代表自动作用于所有路由。Validate 应纯粹、并发安全且无副作用；启动/热更新预检失败时修复错误再发布。DNS 不能使用不存在的 auto_cert.dns.provider 旧写法。

## 相关文档与代码

- [IDS provider](../../ids-provider-plugin-guide.md)
- [DNS provider](../../dns-provider-plugin-guide.md)
- [Ingress](../../ingress-plugin-guide.md)
- [Discovery](../../discovery-provider-plugin-guide.md)
