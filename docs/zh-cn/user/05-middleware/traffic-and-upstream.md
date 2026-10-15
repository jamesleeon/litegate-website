# 流量控制与上游治理

并发限制与速率限制保护入口；重试、熔断和健康检查保护访问后端的尝试。命名 limit_conn 的 limit 为正整数，key 为 global（默认）或 ip；超限返回 503 和 Retry-After。速率限额的语义见专门指南。

新配置在 Service 中写 retry、circuitbreaker、healthcheck。旧命名 retry/circuit_breaker 编译进 proxy Action，已弃用；不能应用于 serve/respond，也不能叠加相同内联策略。重试需要满足请求可重放和幂等约束；本地熔断拒绝保证尚未发送请求，可以无退避改选节点，不计上游被动健康失败。

mirror 在 PostAuth 运行，仅镜像已经通过认证的请求。镜像目标需自行保护，不应将私密业务流量复制到不可信地址。

## 相关文档与代码

- [Rate limits](rate-limit.md)
- [Services](../03-configuration/services.md)
- [Circuit breakers](../09-advanced/circuit-breaker.md)
