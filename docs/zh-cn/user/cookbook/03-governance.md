# 治理：入口限制与后端策略

认证、WAF、限流与并发限制保护路由；重试、熔断和健康检查属于上游 Service。不要在 Service 和旧命名 middleware 同时配置相同熔断/重试。

按实际访问场景选择本地 SSO、Basic、JWT、OIDC 或 Forward Auth。需要业务身份动态隔离时使用 IDS Selector。多副本配置不能默认共享内存限额或封禁。

## 相关文档与代码

- [Pipeline](../05-middleware/pipeline.md)
- [Services](../03-configuration/services.md)
- [HA state](../10-deployment/ha-state.md)
