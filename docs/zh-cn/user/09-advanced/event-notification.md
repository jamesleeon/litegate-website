# 事件通知与离线投递

LiteGate NATS 插件连接外部 NATS，不内嵌 NATS Server。在线通知使用 Core NATS 与 SSE；断线后应重新同步业务状态。可靠离线通知使用 JetStream、稳定业务身份和显式 ACK；仅首次订阅之后的历史按消费者状态补发。

订阅离线身份使用 offline: auth.subscriber，必须由鉴权链生成可信身份。租户隔离主题使用 {auth.tenant}；发布还可使用 body/header/query 模板，发布者选择目标租户的权限需业务授权。多副本共享至少 32 字节 ACK 密钥，ACK 密钥不同于 JWT 签名密钥。

IDS 插件的 NotifySubscriber 是可选在线失效信号与 Resync，不是离线业务队列。消费者 ACK、重试和业务去重由应用按实际语义实现；不能将投递描述成业务操作 exactly-once。

## 相关文档与代码

- [SSE](../04-actions/nats-sse.md)
- [NATS events](../04-actions/nats-events.md)
- [JWT integration](notify-jwt-integration.md)
