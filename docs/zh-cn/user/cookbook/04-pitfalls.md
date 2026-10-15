# 常见配置问题

排错先检查解析与真实运行版本，再检查 Host、入口、路由和后端。@matcher 引用必须用引号；V2 不支持 anchors/aliases、重复键或 null。未知插件需先编译；只有配置定义不会自动绑定路由。

rewrite 不重新选路；DNS 插件用 auto_cert.dns_providers；Service 熔断用 circuitbreaker/maxrequests/tripthreshold，而兼容 Action 用 circuit_breaker/max_requests/trip_threshold。不要混用层级和字段拼写。

401/403 先查认证与策略；429 查限流；503 区分并发、熔断、无后端与依赖不可用；502/504 查上游错误和超时。修复配置后预检，再发布并实际请求验证。

## 相关文档与代码

- [Debugging](../11-troubleshooting/debugging.md)
- [Configuration](../03-configuration/site-yaml-v2-concepts.md)
