# 可靠事件通知（持久化、离线续推与应用确认）

配置来源不受限制：数据库、Litemesh KV、NATS KV、Redis、HTTP 服务都可以。业务负责成功修改配置并可靠发布通知；LiteGate 负责 JetStream 持久化、每个接收者的离线进度、SSE 投递和确认。网关不读取或写入你的配置源。

```text
任意配置源更新 → HTTP POST /config/publish → JetStream 存储确认
                                           └→ 应用 SSE → 重新加载 → POST ACK
```

这是至少一次投递。发布去重在 JetStream 的 duplicates 窗口内有效，消费可能重复；开发者须实现幂等刷新。`event_id` 对同一次变更保持稳定，`version` 是不透明字符串，由开发者解释。配置事件示例：

```json
{"event_id":"tenant-a:routing:42","tenant_id":"tenant-a","type":"tenant.disabled","version":"42"}
```

## 连接和共享密钥

共享插件配置如下。ACK 密钥至少 32 字节，所有网关节点使用同一密钥，不能发给客户端。`LITEGATE_NODE_ID` 必须稳定且每个网关实例不同，不能每次重启随机生成。

```yaml
plugins:
  nats:
    connections:
      default:
        servers: nats://127.0.0.1:4222
shared:
  event_ack_secret: "${EVENT_ACK_SECRET}"
```

IDS 等插件的缓存失效不使用本文的持久投递，而是由插件自己声明 subject、通过通知总线接收，见 [插件订阅通知](../09-advanced/event-notification.md#9-插件订阅通知插件自己定义-subject)。

## HTTP 发布、订阅和确认

下面是 action 配置示例，**还需给发布和消费路由配置认证/授权**。示例静态 `tenant: config` 是监控与配额分组，不会自动检查业务租户。只应向有权接收整个 `config.changed` 的管理应用暴露这条路由；按租户隔离使用原 SSE 文档中的 `tenants` 和 `subject_template`，发布也要采用相同主题边界。

```yaml
site: events.example.com
routes:
  - match:
      path: /config/publish
      method: [POST]
    action:
      type: nats
      mode: jetstream_publish
      subject: config.changed
      stream:
        name: CONFIG_EVENTS
        create_if_absent:
          subjects: [config.changed]
          retention: limits
          storage: file
          max_age: 72h
          duplicates: 30m
          replicas: 1
  - match:
      path: /config/events
    action:
      type: nats
      mode: jetstream_subscribe
      subject: config.changed
      stream:
        name: CONFIG_EVENTS
      sse:
        tenant: config
        max_connections: 100
        heartbeat: 15s
        write_timeout: 5s
        max_duration: 15m
      reliable:
        subscription: config-updates
        consumer_from: auth.subscriber
        ack_secret_ref: shared.event_ack_secret
        ack_wait: 1m
  - match:
      path: /config/ack
    action:
      type: nats
      mode: jetstream_ack
      subject: config.changed
      stream:
        name: CONFIG_EVENTS
      sse:
        tenant: config
      reliable:
        subscription: config-updates
        consumer_from: auth.subscriber
        ack_secret_ref: shared.event_ack_secret
        ack_wait: 1m
```

生产集群建议文件存储及 3 副本；在客户端首次订阅前预建流，发布 action 的兜底创建只在实际发布时发生。可靠消费只接受 `LimitsPolicy` 文件流，不接受 workqueue/interest。管理员应设置存储容量和消费者数量限制。ACK 不删除事件，100 个不同订阅者有 100 份独立消费进度；第一个 ACK 不会影响其余 99 个。

发布请求使用 `Idempotency-Key: tenant-a:routing:42`，正文为上面的 JSON，网关收到 PubAck 后才返回成功。默认 `nats_headers` 模式保持正文原样，客户端收到的就是发布的正文。

`consumer_from: auth.subscriber` 从认证/IDS 注入的 `X-Lito-Subscriber` 读取稳定身份，并要求 `X-Lito-Verified: true`。入站身份头会被清理；IDS 的 `header_projection.allowed_headers` 需列出 `X-Lito-Subscriber`。客户端不能通过查询参数或自行设置这些内部头选择他人的消费进度。多个 Go 实例需要不同 ID；浏览器也要明确按用户、设备还是标签页划分身份。若多个标签页必须独立收到消息，就注入不同身份；同一身份的新连接会接管租约，旧连接在续租失败后关闭（正常约 5 秒）。

也可将 `consumer_from` 替换为固定 `consumer: agent-a`，用于已经由路由认证隔离的单一接收者。订阅与 ACK 路由的 subject、stream、tenant、reliable 配置必须一致。实际 durable 名称由订阅命名空间、租户、主题和身份哈希生成，修改这些值会产生新进度。切换到完全不同的 NATS 存储集群也会丢失旧进度。

## 客户端处理协议

连接开始会收到 `ready` 事件，要求先从配置源同步最新状态；每次重连都要执行这一步，覆盖缓存重建、消费者删除、历史过期和保留期不足。SSE 事件随后包含：

```json
{"sequence":123,"redelivered":false,"ack_token":"signed-proof","payload":{"event_id":"tenant-a:routing:42","tenant_id":"tenant-a","type":"tenant.disabled","version":"42"}}
```

客户端依次执行：

1. 完成初始同步，再处理变更事件。
2. 从自己的配置源刷新，或清理缓存并阻止旧回源结果写回；按版本避免旧配置覆盖新状态。
3. 成功后向 ACK 路由 POST `{"ack_token":"signed-proof"}`，Content-Type 为 application/json。
4. ACK 成功返回 204；失败不能当作处理确认，允许重投和幂等重做。

确认凭据绑定租户、订阅身份、流和主题，有效期为两倍 `ack_wait`；过期后等待重投得到新凭据。ACK 可以落在另一网关。每个 consumer 只允许一个未确认事件，失败会重投；处理时间应小于 `ack_wait`，过慢会产生重复。不要把网关写入成功或 `Last-Event-ID` 当业务 ACK：接收到了不等于处理完成了。

永久坏消息（超大、无效 UTF-8、编码后超出缓冲预算）会执行 TERM，只终止该 consumer 的重投，发送 delivery-warning 并继续连接。原始消息仍保留在 LimitsPolicy 流中供排查和其他消费者使用。litegate_nats_terminated_events_total 记录类型与原因；错误日志包含 stream、durable、stream sequence。没有自动死信转发，发布者仍需修复。

Go 客户端可用仓库的 `pkg/eventclient.Client`，提供 `Resync` 和 `Handle` 回调，包内负责重连和成功后的 ACK；认证头同时用于 GET 和 POST。HTTPClient 不应设置覆盖整个 SSE 请求的总超时。浏览器示例见 [browser-client.js](https://github.com/jamesleeon/LiteGate/blob/master/examples/nats-events/browser-client.js)，使用 Cookie、串行处理和显式 HTTP ACK。浏览器原生 EventSource 不支持自定义 Authorization 头；跨域需要正确设置 CORS/凭证。401/403 的页面跳转由应用处理。

## 运维边界

配额现在跨同一进程的 action 热重载代数共享，按 NATS 连接名和租户计数，仍不跨进程聚合。action 清理会断开 SSE，但 durable 进度不删除，随机 2–8 秒重连后可继续处理未确认事件。

`LITEGATE_EVENT_LEASES` 是单独的 JetStream KV 租约桶（不是你的配置源），TTL 为 15 秒，创建时沿用事件流副本数；网关每 5 秒续租。SSE 新连接可直接接管已验证身份的租约，旧连接停止时 NAK 尚未确认的消息；旧进程崩溃时，已取走的消息仍可能等待 ack_wait 才重投。租约丢失会结束当前消费连接。所有节点要访问同一个租约桶，权限需允许消费管理、租约 KV 和 ACK；已有桶的副本数由管理员维护。

事件保留时间、容量限制和 consumer 生命周期必须监控；无活动 consumer 按 offline_retention 自动回收。启动/重连完整同步与 TTL 是恢复兜底，不承诺无限期历史保存。


## 生命周期与容量

新 durable 使用 DeliverNew，只接收创建后的事件，不回放创建前的历史。首次连接和每次重连先完整同步当前配置；已有 consumer 保留原投递策略和确认进度。

reliable.offline_retention 默认 168h（7 天），范围 1m 到 720h（30 天）。这是无活动 consumer 的回收期限；流的 MaxAge 和容量另行限制可重放消息。超过期限重连会创建新 consumer 并完整同步。应同时设置流的 MaxConsumers，限制注册身份增长。修改 ack_wait、offline_retention 等可变设置会原地更新 consumer；FilterSubject、AckPolicy 等不兼容设置仍报错。

静态 tenant 配合静态 consumer 表示共享一个接收身份，新连接会抢占旧连接。仅用于已认证隔离的单一接收者；多用户路由使用验证后的 consumer_from，不能当作给每个浏览器广播。

MaxAckPending 为 1，每条事件单独 HTTP ACK。吞吐受往返延迟和处理时间限制，50ms 往返理论上约 20 条/秒。适合配置通知；高频业务需要另行设计更大的 pending 窗口或批量 ACK，当前不支持。
