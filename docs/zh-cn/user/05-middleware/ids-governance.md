# IDS 请求治理

IDS 在路由匹配后、代理下游前调用用户注册的 Provider。Provider 可以检查完整 HTTP 请求、查询租户系统或缓存，并返回继续转发、直接响应或系统错误。

```yaml
action:
  type: proxy
  service_name: shared-app
  ids:
    provider: saas-session
    fail_policy: deny
    selector_merge_policy: intersect
    options:
      token_header: Authorization
    header_projection:
      allowed_headers: [X-Tenant-Ref, X-Database-Ref]
```

Forward 可不返回 Route，此时使用默认下游；也可返回 Selector 硬隔离候选池，并以 Meta 指定同一池中的灰度偏好。默认 `selector_merge_policy: intersect`，动态 Selector 与路由已有同名维度冲突时拒绝；显式配置 `override` 才允许覆盖。Respond 终止代理并直接响应客户端。只有 error 受 `fail_policy` 控制，默认拒绝。

路由 options 每次请求动态传入，配置热更新无需重启。数据库、Redis、HTTP 客户端和缓存由 Provider 单例管理；秘密应通过引用从插件自己的安全配置源解析。

完整说明见 [IDS Provider 架构](../../ids-architecture-v2.md) 和 [插件开发与配置](../../ids-provider-plugin-guide.md)。
