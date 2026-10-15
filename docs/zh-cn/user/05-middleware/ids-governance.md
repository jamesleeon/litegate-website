# IDS 请求治理

IDS 在路由匹配后、Action 执行前调用注册的 Provider，适用于 proxy、静态内容、直接响应和第三方 Action。Provider 可读取 HTTP 请求和业务系统，返回 Forward、Respond 或 error；业务拒绝应返回 Respond，只有系统 error 受 fail_policy 控制，默认 deny。

Forward 不带 Route 时使用原有下游。Selector 是硬隔离边界；Meta 是边界内偏好，缺少目标版本时只回到同一 Selector 的默认池。默认 selector_merge_policy 为 intersect，与静态 Selector 同名但值冲突会拒绝；override 需明确授权覆盖。

只投影 header_projection.allowed_headers 中的响应头。路由 options 每请求传入，热更新无需重启；连接池和缓存由并发安全的 Provider 单例管理。读取 Body 后需恢复，不跨请求保存请求对象。

```yaml
site: api.example.com
routes:
  - match: {path_prefix: /api}
    ids:
      provider: saas-session
      fail_policy: deny
      selector_merge_policy: intersect
      options: {token_header: Authorization}
      header_projection:
        allowed_headers: [X-Tenant-Ref, X-Database-Ref]
    proxy: ['127.0.0.1:8080']
```

## 相关文档与代码

- [Authoring](../../ids-provider-plugin-guide.md)
