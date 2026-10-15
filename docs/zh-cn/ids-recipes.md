# IDS 业务决策配方

先确认业务需要，不把登录、缓存或 Redis 固定成内核要求。验签成功可以 Forward 不带 Route，使用默认下游；业务拒绝 Respond 401/403。租户独立集群用 Selector；同一集群灰度用 Meta，缺少灰度实例时回到该隔离池默认实例。

共享应用配独立数据库时，Provider 查询可信租户状态、返回 Selector 并通过白名单投影数据库上下文头。登录/刷新/注销使用各自路由或不同 options，实际 token 生命周期由业务 Provider 实现。

动态限流通过 Forward 的 RateLimitDecision；缓存可以使用 idskit 的有界工具。通知是可选失效信号，断线后 Resync；离线事件使用 NATS 专门路径。每个方案都测试错租户、空候选池、密钥轮换、Body 重放与 Provider 超时。

## 相关文档与代码

- [Configuration](user/05-middleware/ids-governance.md)
- [Provider guide](ids-provider-plugin-guide.md)
- [Events](user/09-advanced/event-notification.md)
