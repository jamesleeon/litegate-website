# NATS 实时事件订阅

`type: nats` 配合 `mode: subscribe` 将 Core NATS 消息推送为浏览器 SSE。业务服务发布消息，LiteGate 复用已有 NATS 连接，为每个 HTTP 连接建立普通订阅；多个网关连接同一个 NATS 集群时，每个节点上的订阅者都能收到对应主题的广播。这里不使用 queue group，消息不会被分摊给其中一个节点。

本功能用于在线通知、任务进度和实时状态。**没有持久化、历史重放或浏览器处理确认，不实现 Mercure 协议。** 不输出 SSE `id`，不使用 `Last-Event-ID` 补发消息；浏览器重连后应重新查询当前业务状态。仅在各节点启用 NATS 插件不会自动建立消息集群，节点必须配置相同或互通的 NATS 消息网络。

## 配置连接

在共享插件配置中设置连接，沿用现有 NATS 发布和请求 action 的连接配置：

```yaml
plugins:
  nats:
    connections:
      default:
        servers: "nats://127.0.0.1:4222"
        connect_timeout: "3s"
        reconnect_wait: "1s"
        max_reconnects: "-1"
```

生产部署使用 NATS 凭证及 TLS。部署细节见 [NATS 部署指南](../../nats_deployment_guide.md)。

## 单一主题

以下路由将 `events.demo` 提供给所有能访问它的用户，`tenant: demo` 是管理员指定的限额和监控分组，**不会自动为路由添加身份认证**。私有数据应配置网关认证中间件。

```yaml
site: events.example.com
routes:
  - match:
      path: /events
    action:
      type: nats
      mode: subscribe
      connection: default
      subject: events.demo
      sse:
        tenant: demo
        max_connections: 100
        buffer_messages: 64
        buffer_bytes: 262144
        max_event_bytes: 65536
        heartbeat: 15s
        write_timeout: 5s
        max_duration: 15m
```

发布 UTF-8 文本或 JSON，例如用 NATS CLI 执行 `nats pub events.demo '{"status":"ready"}'`。浏览器连接：

```javascript
const events = new EventSource('/events');
events.onmessage = event => console.log(event.data);
events.onerror = () => {
  // 重连期间可能丢失消息，通过普通业务 API 重新获取当前状态。
};
// 页面不再需要推送时：events.close();
```

只接受 GET，请求其他方法返回 405。响应为 `text/event-stream`，事件名固定为 `message`，消息正文按行转为 `data:`，客户端不能通过消息内容注入 SSE 控制字段。二进制或超过 `max_event_bytes` 的消息会被丢弃并计入指标，连接保留；二进制数据请由发布者先编码为文本。

## 按认证租户隔离

多租户路由使用 `tenants` 明确列出允许访问的租户，并将已验证身份放进主题：

```yaml
site: events.example.com
routes:
  - match:
      path: /events
    action:
      type: nats
      mode: subscribe
      subject_template: events.{auth.tenant}.orders
      sse:
        tenants: [team_a, team_b]
        max_connections: 100
```

该示例还需要在站点或路由上配置认证中间件，使网关提供已验证的租户身份。没有身份或不在列表中返回 403；浏览器传入 `?tenant=team_b` 不会改变订阅身份。主题只允许静态值，或只包含 `{auth.tenant}` 的模板，不允许 `subject_from`、客户端字段模板或订阅通配符。`tenant` 和 `tenants` 二选一。

原生 `EventSource` 不能设置任意 Authorization 请求头，浏览器认证通常使用已有的 Cookie 会话；跨域需要正确配置凭证和 CORS。客户端无需也不应自行设置内部的验证标记头。连接最长保留 `max_duration`，重连时重新认证；建立连接后的身份撤销不会自动即时生效。

## 限额和失败行为

| 字段 | 默认值 | 含义 |
|---|---|---|
| `max_connections` | 100 | 单节点、同一 NATS 连接名和租户的连接上限；同租户各路由应使用相同值 |
| `buffer_messages` | 64 | 每个客户端的待发送事件数上限，也限制 NATS 订阅的待处理消息数 |
| `buffer_bytes` | 262144 | 每个客户端 SSE 缓冲字节数上限，包含正在写入的事件；NATS 待处理消息另有同样字节上限 |
| `max_event_bytes` | 65536 | 单条 NATS 正文大小上限；SSE 行前缀会增加实际缓冲占用 |
| `heartbeat` | 15s | 注释心跳间隔，可配置 1s 至 1m |
| `write_timeout` | 5s | 每次 HTTP 写入及刷新超时，最大 1m |
| `max_duration` | 15m | 单连接最长时间，最大 24h |

同一 action 实例最多接纳 10000 个连接，`tenants` 最多列出 256 个租户。配额是单节点的，不是全集群统一配额。缓冲满时关闭慢连接，不阻塞其他客户端或无限堆积内存；写超时也会结束连接。NATS 掉线、检测到重新连接或订阅丢消息时，流在心跳检查时关闭，让客户端重连并重新读取业务状态。服务器停机取消存量流，释放订阅及连接额度，并拒绝新订阅。

LiteGate 会禁用 SSE 响应压缩并发送 `X-Accel-Buffering: no`。前置代理仍需关闭响应缓冲，并使空闲超时大于心跳间隔。不要对事件路由应用响应缓存或整段响应变换。HTTP 流成功刷新只表示写到传输层，不表示浏览器业务已处理。

## 监控

Prometheus 指标按配置的 `connection`、`tenant` 分组，主题和客户端输入不会成为租户标签：

- `litegate_nats_sse_connections`：当前连接数。
- `litegate_nats_sse_messages_total`、`litegate_nats_sse_bytes_total`：成功刷新到 HTTP 的事件数和字节数。
- `litegate_nats_sse_disconnects_total`：断开或拒绝次数，`reason` 区分限额、慢消费者、写错误、NATS 不可用、最长时长和停机。

需要断线补发时，应另行设计 JetStream 消费和持久事件游标；单独设置 SSE 的 `id` 不会让 Core NATS 保存消息。

## 热重载与异常消息

任何配置热重载都会创建新 action 代数，旧代通常在 15 秒延迟清理后结束已有 SSE 流。重连期间消息可能丢失，应重新查询业务状态。每条连接随机发送 2000–8000 毫秒的 retry，以分散重连；尚未实现跨代保留订阅。配额跨同一进程的新旧代共享，不会因热重载增加一倍。

缓冲预算按编码后的 SSE 帧计算。单帧超过整个缓冲预算属于输入问题，会被丢弃；只有累计排队超限才断开慢消费者。`litegate_nats_sse_dropped_events_total` 按订阅者计数，reason 为 invalid_payload 或 frame_too_large。空正文保留 data 字段，浏览器可以收到空字符串事件。同租户不同路由的配额冲突目前在请求时返回 HTTP 500，尚未做跨路由加载校验。


需要离线补发、应用 ACK 或 IDS 缓存失效时，见 [可靠配置通知](nats-events.md)。
