# NATS 联动部署

部署顺序为外部 NATS Server → LiteGate NATS 插件配置 → 业务消费者。在线发布/订阅用 Core NATS；可靠离线事件启用 JetStream 并配置存储与业务 ACK。NATS、网关和消费者分别负责传输、HTTP 入口与业务处理。

plugin_config 指定 plugin.yaml，在 plugins.nats.connections 中配置连接。站点 publish/subscribe 或显式 NATS action 使用该连接；主题与租户模板需鉴权。request_reply 没有消费者时可能返回 no_responders；unavailable 表示连接不可用，排错方向不同。

生产固定实际部署版本和制品，不使用未核验的 latest 版本号示例。NATS 凭据和监控端口限制访问；先验证连接，再请求应答，再 SSE 与 ACK 重连。完整协议、缓冲/慢消费者与离线保证见专题指南。

```yaml
plugin_config:
  path: plugin.yaml
  watch: true
```

```yaml
plugins:
  nats:
    connections:
      default:
        servers: nats://127.0.0.1:4222
```

```yaml
site: events.example.com
/events:
  subscribe: notify.orders
```

## 相关文档与代码

- [Events contract](user/04-actions/nats-events.md)
- [SSE](user/04-actions/nats-sse.md)
- [Examples](../../examples/nats-events/demo/README.md)
