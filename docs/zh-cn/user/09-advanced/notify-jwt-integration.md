# Notify 与业务 JWT 接入：配置、限制和排查

本文记录网关通知、第三方 JWT、离线消费和 IDS 通知之间的边界。业务状态可以来自数据库、KV 或其他系统；网关不限制状态存储，也不替业务系统签发或刷新 JWT。

## 1. 先选通知语义

| 需求 | 配置与责任 |
|---|---|
| 在线提醒，断线后重新查询当前状态即可 | 不写 `offline`，使用 Core NATS；每次连接成功从业务系统重新同步 |
| 首次订阅之后，离线期间的事件也要补发 | 发布 `offline: true`，订阅 `offline: auth.subscriber`；使用 JetStream 和业务 ACK |
| IDS Provider 的可选状态失效 | 实现 `plugin.NotifySubscriber`；当前插件通知总线是在线信号 + Resync，不是 JetStream 离线队列 |

IDS 不一定使用缓存，也不一定订阅通知。只做验签的 Provider 可以完全不接入 notify。需要通知的插件自行定义主题、消息格式及处理方式。

## 2. 同源浏览器、多租户可靠订阅

站点配置（v2）：

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
    token_from: [cookie:lg_token]
    subject_claim: user_id
    tenant_claim: tenant_id
  subscribe: notify.{auth.tenant}.workorder
  offline: auth.subscriber
```

插件配置：

```yaml
plugins:
  nats:
    connections:
      default:
        servers: nats://127.0.0.1:4222
shared:
  notify_ack_secret: "REPLACE_WITH_AT_LEAST_32_RANDOM_BYTES"
```

上面的 ACK 密钥值是占位符，部署时替换为至少 32 字节的随机密钥，通过受控插件配置分发。`ack_secret_ref` 是插件配置键名，不能把 JWT 的 `env://` 引用规则直接套到它上面。所有网关节点使用同一个 ACK 密钥；它和 JWT 密钥是两个用途不同的密钥。生产 NATS 集群可设 `replicas: 3`，前提是有足够节点。

发布路由单独配置鉴权：

```yaml
/internal/publish/workorder:
  auth:
    type: jwt
    secret: env://NOTIFY_PUBLISH_JWT_SECRET
    token_from: [header]
    issuer: trusted-notify-publisher
    audience: litegate-notify
  publish: notify.{body.tenant_id}.workorder
  offline: true
```

此发布密钥仅发给可信发布服务。`body.tenant_id` 表示发布方可以选择目标租户，网关不会自动检查它是否等于调用方身份。让租户用户自行发布时，应使用 `notify.{auth.tenant}.workorder` 和已验证的租户 claim，或增加业务授权。不要把拥有跨租户发布权限的凭证交给浏览器。

## 3. JWT 和 Cookie 的职责

发布也可以从自定义 Header 选题，正文无需包含租户字段：

```yaml
/internal/publish/workorder:
  publish: notify.{header.key}.workorder
  offline: true
```

请求携带 `key: tenant_a` 即发布到 `notify.tenant_a.workorder`。`key` 是用户自定义的请求头名称，没有固定名称要求。这个例子不配置鉴权；notify 不强制鉴权，访问策略由用户自行通过路由的 JWT、forward_auth 或其他认证插件配置。正文保持原样，不会因为使用 Header 模板而解析其中的租户字段。

- `secret` 接受 HS256/384/512；`jwks_url` 接受 RS/ES。两者必须且只能配置一个，拒绝 `alg: none`。同一密钥下仍应配置符合业务签发约定的 `issuer`、`audience`。
- `token_from` 按顺序选取第一个非空令牌，如 `[header, cookie:lg_token]`。选中的令牌无效就拒绝，不会继续尝试另一份。不支持 URL 查询参数令牌。
- `subject_claim` 输出可信订阅者身份；`tenant_claim` 输出可信租户身份，并要求配置 `subject_claim`。配置了映射却缺少相应 claim 时返回 401。18 位数字 ID 保留精度。
- 订阅身份及模板值使用字母、数字、下划线和短横线，最长 128 字符。用户名含点号、邮箱等不适合直接用作这些值，应映射稳定 ID。
- `exp` 到期会断流，即使没有配置身份映射。没有 `exp` 的 JWT 仍可验签通过，连接只受 `max_duration` 限制，签发方应始终提供过期时间。
- 共享密钥引用有约一分钟的缓存，并发请求共享解析；轮换密钥不保证立即生效。已经通过验证的连接也不会因密钥轮换自动重新验签。轮换方案应明确旧令牌的过渡期和最长连接时长。

业务后端在**登录和每次续签**时同步下发 `lg_token` Cookie，值为新 JWT；仅更新 localStorage 或 `New-Authorization` 响应头不会更新 Cookie。退出时用相同 Path、Domain 删除 Cookie。Cookie 应设置 HttpOnly、生产 HTTPS 下的 Secure，Expires 与 JWT 对齐；例如同源订阅使用 `Path=/events; SameSite=Lax`。

原生 EventSource 不读取 localStorage，也不能设置任意 Authorization 请求头。同源时自动携带匹配路径的 Cookie；页面与订阅服务不同源时需要 `withCredentials: true` 和明确允许来源、允许凭证的 CORS。只有跨站场景才需要评估 `SameSite=None; Secure`，不同源不一定是不同站。Cookie 必须实际属于订阅服务可接收的主机，浏览器策略也可能限制第三方 Cookie。

订阅 GET 和自动生成的同路径 POST ACK 都受路由鉴权保护。ACK 路径必须落在 Cookie 的 Path 内。Cookie Path 限制发送范围，不是权限边界；HttpOnly 限制脚本读取，但不能阻止 XSS 使用已有登录态发请求。

## 4. 租户隔离与消费身份

**鉴权通过不等于消息隔离。** `subscribe: notify.workorder` 是共享主题，所有通过路由鉴权的租户都能订阅。使用 `notify.{auth.tenant}.workorder` 才按租户选择主题；订阅模板只接受 `{auth.tenant}` 和 `{auth.subscriber}`，客户端不能通过 query/body 改变订阅范围。

离线进度、租约和 ACK 凭据绑定主题、订阅命名空间、配额分组、可信租户与订阅者。不同租户相同用户 ID 独立消费。**同一身份只有一个活动会话**：新连接抢占旧连接；按用户 ID 配置时，同用户多个标签页或设备会互相接管。如需每个设备独立接收，应由认证系统提供经过验证的稳定设备身份，不要直接相信客户端自报的 ID。

简写默认连接配额按站点统计，同站点订阅共享默认 100 个连接。`notify.sse.tenant` 可覆盖分组；简写不接受 `notify.sse.tenants`，按租户设置限额需完整 NATS action。配额分组不是消息权限边界。

## 5. 离线可靠投递的实际保证

1. 发布侧收到 JetStream PubAck 后才返回成功；进入网关之前的失败仍由发布方可靠重试。状态提交与通知发出应通过业务侧可靠机制衔接，数据库、KV 均适用。
2. 新 consumer 从创建之后开始接收，不补发首次订阅之前的历史。离线消息只能在流保留期、存储容量和 consumer 保留期限内补发。
3. 每次收到 `ready` 先从业务状态源同步，再串行处理 `{sequence, ack_token, payload}`。成功后 POST 同订阅路径 `{"ack_token":"..."}`，使用 `Content-Type: application/json`；204 才表示 ACK 请求成功。
4. 进度存在服务端 durable consumer，**不依赖 Last-Event-ID 实现离线恢复**。Last-Event-ID 也不是业务处理确认。
5. 投递可能重复，客户端需要业务幂等或版本检查。JetStream 发布去重仅覆盖去重窗口，不保证业务处理恰好一次。

发布重试时使用相同的 `Idempotency-Key`，例如 `tenant-a:workorder:42`。不提供稳定幂等键时，不应假设两次 HTTP 发布会被自动视为同一条业务事件。简写默认去重窗口为保留期与 10 分钟中的较小值；跨出窗口仍可能重复。

100 个不同身份有 100 份消费进度，一个人的 ACK 不释放其他人的消息。原生 EventSource 本身不做可靠 ACK，旧前端不能仅改 URL 就完整支持离线模式。可参考 `examples/nats-events/browser-client.js`；Go 使用 `pkg/eventclient`。两者遵守同一协议，但浏览器使用 Cookie，Go 可使用 Authorization 请求头。

默认保留期 7 天，可配置范围 1 分钟到 30 天。已有 stream 的保留策略不会随简写改动自动更新，应使用 NATS 管理工具调整。重建 consumer、更换消费身份或 NATS 存储集群会丢失原来的进度，需要全量同步兜底。

每个 consumer 只有一个未确认消息，单条 HTTP ACK 吞吐受延迟限制：50ms 往返理论约 20 条/秒，处理耗时还会降低它。适合配置通知，不适合作为当前实现下的高频消息通道。每个身份对应持久 consumer，管理员需限制容量及 consumer 数量。

坏消息会 TERM 当前 consumer 的该条投递并发出 `delivery-warning`，后续消息继续；原始事件仍在流中，没有自动死信转发。监控终止计数及日志中的 stream、durable、sequence。

## 6. 租户停用、退出与 IDS 的边界

本地 JWT 验签只能确认签名和声明，无法自动得知退出、令牌撤销或租户停用。清除 Cookie 也不会撤销已经建立的 SSE。已有连接会在 JWT 过期、最大时长或其他断开条件发生时结束。

使用缓存的 IDS Provider 收到通知后自行失效缓存，再由 `Evaluate` 读取新状态并明确返回 401/403。框架不假设缓存存在，不强制插件订阅，也不会把清缓存转换为撤销长连接。

因此“租户停用后新请求立即拒绝”和“已有 SSE 立即停止投递”是两个需求。后者需额外设计主动断流或持续授权机制，目前不能仅靠 JWT 和 IDS 缓存失效保证。浏览器还需处理登录失效；EventSource 的 error 回调没有 HTTP 状态码，应通过登录状态接口等方式判断是否重新登录，避免盲目重连。

## 7. 多节点、热重载和排查

共享 NATS/JetStream 支持多网关；各节点还必须使用相同 ACK 密钥。默认随机密钥仅适合单进程，跨节点 ACK 会返回 403；进程重启旧 token 失效，重连重投获取新 token。前置代理应关闭 SSE 缓冲，空闲超时大于心跳间隔。

站点热重载可能关闭旧实例的连接，客户端必须支持重连。在线模式可能丢信号，应全量同步；可靠模式恢复未确认投递，也应同步当前状态。不要把热重载描述为无缝不断流。

| 现象 | 优先检查 |
|---|---|
| 订阅 401 | Cookie 主机/Path、续签是否更新、JWT exp、密钥、issuer/audience、缺失 claim |
| 跨租户看到消息 | 是否仍使用固定 subject，发布授权是否限制目标租户 |
| 消息不断重复 | 客户端是否 ACK、是否处理超过 ack_wait、各节点 ACK 密钥是否一致 |
| ACK 403 | 身份/租户/主题是否一致，凭据是否过期或来自另一个进程密钥 |
| 标签页互相断开 | 是否共用同一个订阅身份 |
| 离线过久无历史 | stream 保留/容量、consumer 回收、消费身份是否改变 |
| 停用租户仍收推送 | 已有长连接不会因清缓存自动撤销 |

## 8. MCP 配置能力

MCP 的 `get_config_guide` 与 `resource://documentation/site-config` 读取编译进二进制的配置指南，不会自动扫描新增文档。更新内置指南后需编译并重启运行中的 MCP 服务。

`enable_jwt_for_site` 支持 JWKS 或共享密钥、Cookie 来源及身份映射，但**只给代理路由添加命名 JWT 中间件**，不会保护 notify 发布、订阅和 ACK。通知应走 `get_site_config` → `get_config_guide` → `validate_site_config` → `save_site_config`，保留原站点内容并显式为通知路由配置 auth。不能把“工具调用成功”当作整个站点全部受保护。

另见：[事件通知与插件通知](./event-notification.md)、[可靠投递协议](../04-actions/nats-events.md)、[JWT 鉴权字段](../05-middleware/authentication.md)。
