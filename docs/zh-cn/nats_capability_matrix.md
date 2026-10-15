# NATS 能力与责任边界

| 需求 | 机制与边界 |
|---|---|
| HTTP 发布 | publish / NATS Action；业务授权由路由配置 |
| HTTP 请求应答 | request_reply；需要业务消费者协议 |
| 在线 SSE | subscribe / Core NATS；断线后重新同步状态 |
| 离线事件 | JetStream、可信 subscriber、ACK；消费者状态绑定身份 |
| 多租户主题 | 订阅只允许可信 auth 模板，发布变量需授权 |
| 多副本 ACK | 共享至少 32 字节 ACK 密钥 |
| IDS 通知 | 可选在线信号 + Resync，不是离线队列 |

网关不内嵌 NATS Server，不实现应用事务或 exactly-once 业务操作。默认消费者单条在途 ACK、缓冲限制与慢消费者断开会影响吞吐。参数与错误码以当前 Action/SSE 文档为准，不能用旧侧车设计替代现有消费者契约。

## 相关文档与代码

- [Deployment](nats_deployment_guide.md)
- [NATS events](user/04-actions/nats-events.md)
- [SSE](user/04-actions/nats-sse.md)
- [JWT](user/09-advanced/notify-jwt-integration.md)
