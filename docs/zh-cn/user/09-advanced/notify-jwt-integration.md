# Notify 与业务 JWT 接入

网关验证业务 JWT，不替应用签发、刷新或存储业务状态。secret 与 jwks_url 必须二选一，拒绝 alg:none；按业务约定设置 issuer/audience。token_from 按顺序取第一个非空令牌，无效则直接拒绝，不再尝试后续来源；不支持 Query Token。浏览器 EventSource 可使用 HttpOnly Cookie。

subject_claim 生成可信订阅者，tenant_claim 生成可信租户且要求 subject_claim；映射 claim 缺失返回 401。通知身份只接受字母、数字、下划线和短横线，最多 128 字符。exp 到期断开连接。

offline: auth.subscriber 与 notify.{auth.tenant}.workorder 绑定租户和身份。ACK secret 通过插件 shared 配置引用，不沿用 JWT secret 的 env:// 规则；所有节点使用相同密钥。订阅模板只接受 auth.tenant/auth.subscriber；发布可选 body/header/query，必须防止跨租户越权。

默认简写连接配额按站点共享；租户配额使用完整 NATS action 的 sse.tenants。认证撤销、断线重连、ACK 失效与重复投递需要业务端处理；可选 IDS 通知不提供 JetStream 离线语义。

```yaml
site: app.example.com
notify:
  ack_secret_ref: shared.notify_ack_secret
  retention: 168h
  replicas: 1
/events/workorder:
  auth:
    type: jwt
    secret: env://APP_JWT_SECRET
    token_from: ['cookie:lg_token']
    subject_claim: user_id
    tenant_claim: tenant_id
  subscribe: notify.{auth.tenant}.workorder
  offline: auth.subscriber
```

```yaml
plugins:
  nats:
    connections:
      default:
        servers: nats://127.0.0.1:4222
shared:
  notify_ack_secret: REPLACE_WITH_AT_LEAST_32_RANDOM_BYTES
```

## 相关文档与代码

- [Authentication](../05-middleware/authentication.md)
- [SSE contract](../04-actions/nats-sse.md)
- [Event delivery](../04-actions/nats-events.md)
