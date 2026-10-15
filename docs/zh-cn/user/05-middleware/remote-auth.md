# Remote Auth（OIDC / OAuth2）

remote_auth 是浏览器 OIDC/OAuth2 登录联合的兼容入口。开放平台验签、租户会话和动态隔离已转到 IDS，不能再通过 remote_auth 配置这些业务能力。IDS 可保护所有 Action，并非只适用于 proxy。

在全局 auth_providers 中声明 oidc/oauth2 Provider，再在站点 Action 的 remote_auth 中设置 enabled、provider、enforce 和需要投影的 inject_claims。登录重定向与会话依赖 Redis，需同时配置 Redis；回调地址必须符合身份服务登记与网关回调路径。完整字段见 OIDC 指南。

enforce 控制无会话时是否要求登录。fail_policy 默认 deny；显式 allow 是故障时放行，需了解风险。无效 Provider 类型不能当作完成认证；检查加载告警与实际请求。IDS 的可信 Header 使用 ids.header_projection.allowed_headers 白名单，不使用旧 ids.allowed_headers 字段。

## 相关文档

- [OIDC](oidc.md)
- [认证](authentication.md)
- [IDS](../../ids-provider-plugin-guide.md)
- [OIDC 实现](../../../../internal/middleware/oidc.go)
