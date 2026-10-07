# LiteGate NATS 能力矩阵与消费者契约

> 本文档描述 LiteGate `nats` Action 插件**当前已实现**的能力边界,以及下游消费者(Go Sidecar / 纯 Go 微服务 / 其他语言)必须遵守的协议契约。
>
> 对应实现:`internal/plugins/nats/`
> **部署步骤见:[nats_deployment_guide.md](./nats_deployment_guide.md)**
> 设计背景与迁移方案见:[nats_legacy_asset_integration_design.md](https://github.com/jamesleeon/LiteGate/blob/master/docs/zh-cn/nats_legacy_asset_integration_design.md)

---

## 1. 一句话定位

LiteGate 是一个 **HTTP → NATS 的单向客户端适配器**。它只作为 NATS 的**发布方(Publisher)和请求方(Requester)**,永远不订阅、不消费、不管理 Stream/Consumer,也不嵌入 NATS Server。

```
HTTP 客户端 → LiteGate(TLS/鉴权/限流/路由)→ NATS → 消费者(Sidecar / Go 服务)
                     ↑ 本文档描述这一段            ↑ 消费者契约见第 7 节
```

---

## 2. 对照 NATS 核心概念的能力矩阵

| NATS 核心概念 | LiteGate 支持情况 | 说明 |
|---|---|---|
| **Publish-Subscribe** | ◐ 仅 Publish | 作为发布方发送消息。**不提供订阅能力**,网关不消费任何消息 |
| **Subjects** | ✓ 静态 Subject | 路由配置中写死,加载期校验。**禁止**通配符、`_INBOX.`、`$SYS.`、空白字符、首尾/连续点号 |
| **Request-Reply** | ✓ 完整支持 | `mode: request`,基于 Core NATS,自动管理 inbox,支持 context 取消与超时 |
| **Queue Groups** | ✓ 天然兼容 | 网关侧无需配置。负载分担完全由消费者侧 `QueueSubscribe` 决定,这是灰度迁移的基础 |
| **JetStream** | ◐ Publish + 兜底建流 | `mode: jetstream_publish`。收到 PubAck 确认返回。支持 `stream.create_if_absent` 兜底建流（只建不改，防配置漂移）与缺流主动诊断 |
| **Topologies**(集群/超级集群/Leaf Node) | ✓ 透明 | 多地址逗号分隔配置即可,拓扑对网关透明 |
| **Security** | ◐ 客户端凭据 | 支持 Token / User-Password / Credentials(.creds)。**不管理 Account、不下发权限** |
| KV / Object Store | ✗ 不支持 | 不在网关职责内 |
| 消息重放 / 死信队列 / Consumer 状态 | ✗ 不支持 | 由 NATS 运维侧配置管理 |

图例:✓ 完整支持　◐ 部分支持　✗ 不支持

---

## 3. 三种工作模式

通过路由的 `mode` 字段选择,共用一套连接管理器和消息协议。

### 3.1 `request` — 同步 Request-Reply(默认)

```
HTTP 请求 → NATS Request(subject, msg, timeout) → 等待 Reply → 转换为 HTTP 响应
```

- 基于 **Core NATS**,语义为**至多一次(at-most-once)**、不持久化
- 使用 HTTP 请求的 Context 作为上限:**客户端断开会立即取消等待**
- **网关不做任何自动重试** —— 避免有副作用的业务被执行两次
- 响应在完全校验通过后才提交 `WriteHeader`,不会写出半截响应

**适用**:查询、校验、耗时较短且可容忍失败重试的事务。

### 3.2 `publish` — 即时异步

```
HTTP 请求 → Core NATS Publish → FlushTimeout 确认已交给连接 → HTTP 202
```

- `202` 仅表示**消息已进入 NATS 客户端发送链路**,不代表已持久化,更不代表业务已执行
- `publish_timeout` 内 Flush 失败 → `504`(超时)或 `503`(其他失败)

**适用**:允许丢失、状态会被后续消息覆盖、或仅需"尽力通知"的场景。

### 3.3 `jetstream_publish` — 可靠异步

```
HTTP 请求 → JetStream Publish(带 MsgId)→ 等待 PubAck → HTTP 202 + stream/sequence
```

- 收到 **PubAck 才返回 202**,证明消息已按 Stream 配置被接受
- **发布侧去重窗口**：优先使用客户端传入的 `Idempotency-Key`，未提供时兼容使用合法的 `X-Request-Id`；网关结合租户、路由、连接、Stream 与最终 Subject 生成确定性的 `Nats-Msg-Id`。显式 `Idempotency-Key` 为空、重复、超过 64 字符或包含非法字符时返回 `400`，不会静默失去幂等保护
- **Stream 绑定与自愈**：推荐由运维预先创建；若配置 `stream.create_if_absent` 则进行路由级全显式参数兜底建流与即时自愈

> ⚠️ **`MsgId` 去重只覆盖发布侧重复**(网关重发同一条消息)。它**不覆盖消费侧重投** —— 消费者崩溃导致的重复投递必须由业务侧幂等处理,见 7.4 节。

### 3.4 定时投递(`jetstream_publish` + `schedule`,JetStream 消息调度 ADR-51)

```
HTTP 请求 → 发布到 schedule 主题(带 Nats-Schedule: @at <时间>)→ PubAck → HTTP 202
                 ⋯ 到点 ⋯ NATS 服务端把消息投递到 subject → 消费者照常消费
```

需要 NATS Server ≥ 2.12,Stream 必须开启 `allow_msg_schedules`(开启后不可关闭)。**消费者无需任何改动**:到点投递的消息 body 与 LiteGate header 原样保留(`Nats-Msg-Id` 由服务端剥离,不会被去重误杀)。

典型场景:店铺授权 token 刷新接力 —— 授权/刷新成功后预约"过期前 10 分钟"再刷新一次。

```yaml
# 预约(或改期)刷新
- name: token-refresh-schedule
  match: { path_prefix: /api/token/schedule, method: ["POST"] }
  action:
    type: nats
    mode: jetstream_publish
    subject: token.refresh           # 到点投递的目标,消费者订阅它
    message_deadline: 10m            # 从"触发时间"起算,不是发布时间
    stream:
      name: TOKEN
      create_if_absent:              # 自动带上 allow_msg_schedules
        subjects: ["token.refresh", "sched.token.>"]
        retention: workqueue
        storage: file
        max_age: 72h                 # 必须 > max_delay
        duplicates: 2m
        replicas: 1
    schedule:                        # 以下是 pkg/natspub 客户端的约定写法
      subject_prefix: sched.token    # 调度主题 = sched.token.<key>
      key_from: header.X-Schedule-Key       # 缺省:Idempotency-Key,再缺省:请求 ID
      at_from: header.X-Schedule-At         # RFC3339 绝对时间
      delay_from: header.X-Schedule-Delay   # 或相对延迟:"110m" / 秒数;两者一次只能给一个
      max_delay: 24h

# 取消(店铺解除授权)
- name: token-refresh-cancel
  match: { path_prefix: /api/token/schedule, method: ["DELETE"] }
  action:
    type: nats
    mode: jetstream_cancel_schedule
    stream: { name: TOKEN }
    schedule: { subject_prefix: sched.token, key_from: header.X-Schedule-Key }
```

`*_from` 支持 `header.<名>`、`query.<参数>`、`body.<JSON 顶层字段>` 三种来源。用 SDK 时请统一按上面的 header 写法配置,这样 body 就是纯业务数据,消费者收到的与发布的完全一致。

Go 发布方使用 `pkg/natspub`,无需引入 NATS 客户端:

```go
pub := natspub.New("https://gateway.internal")

pub.Publish(ctx, "/api/orders", order)                                          // 可靠发布
pub.Publish(ctx, "/api/orders", order, natspub.IdempotencyKey("order-1001"))    // 去重发布
pub.PublishAfter(ctx, "/api/token/schedule", shopID, 110*time.Minute, job)      // 延迟发布(同 key 再发即改期)
pub.PublishAt(ctx, "/api/token/schedule", shopID, expireAt.Add(-10*time.Minute), job) // 定时发布
pub.CancelSchedule(ctx, "/api/token/schedule", shopID)                          // 取消
```

SDK 默认对网络错误与 429/502/503/504 重试 2 次;未指定幂等键时每次调用自动生成一个,所有重试共用,保证重试不会重复入队。

- **每个 key 同时只有一个待触发调度**:对同一 `shop_id` 再次预约会覆盖旧的(即改期),不会重复刷新
- **取消是幂等的**:purge `sched.token.<key>`,调度不存在也返回 `200`
- **过去的时间立即投递**;超过 `max_delay` → `400`;`@at` 为秒级精度,向上取整
- 202 响应附带 `schedule.subject` 与 `schedule.fire_at`;`response_body` 模板可用 `{{schedule_subject}}`、`{{fire_at}}`
- 已有 Stream 未开启调度时发布返回 `502`,提示开启 `allow_msg_schedules`(网关不会自动修改已有 Stream)
- **多条路由共用一个 Stream 时,每条路由的 `create_if_absent` 都要写 `allow_msg_schedules: true`**:谁先收到请求谁建流,普通路由先建出的流不带调度能力,之后调度路由会一直 `502`

> ⚠️ **消费者的 filter 只能订目标 subject**(如 `token.refresh`),不能覆盖 `sched.token.>`,否则 WorkQueue 下 ack 会把调度删掉。natsconsume 要求 filter 与订阅 subject 严格相等,天然满足。
>
> ⚠️ **接力可能断**:刷新连续失败耗尽 MaxDeliver、或预约下一次时失败,该店铺的循环会静默停止。建议配一个周期巡检兜底,补齐"快过期却没有待触发调度"的店铺。

---

## 4. 消息协议

### 4.1 `nats_headers` 模式(默认,推荐)

元数据走 NATS 原生 Header,请求体走 `msg.Data` **原始二进制透传,无 Base64 编码**。

**LiteGate → 消费者(请求 Header)**

| Header | 是否必有 | 说明 |
|---|---|---|
| `LiteGate-Request-Id` | ✓ 总是 | **网关生成的 UUID**,不可被客户端伪造。全链路追踪与幂等键 |
| `LiteGate-Client-Request-Id` | 可选 | 客户端 `X-Request-Id`,**仅在 ≤64 字符且只含 `[A-Za-z0-9_-]` 时透传**,否则丢弃。主要用于关联追踪；JetStream 发布在没有 `Idempotency-Key` 时会兼容使用这个值派生发布去重键 |
| `LiteGate-Trace-Id` | 可选 | 来自 `traceparent` 或 `X-Trace-Id` |
| `LiteGate-Tenant-Id` | 可选 | **仅在网关鉴权通过(`X-Lito-Verified: true`)后注入**,不接受客户端原始值 |
| `LiteGate-Method` | ✓ 总是 | HTTP 方法 |
| `LiteGate-Path` | ✓ 总是 | 请求路径,**不含 query string** |
| `LiteGate-Query` | 可选 | 原始 Query String(如 `id=123&type=A`),URL 无 Query 时不注入。⚠️ **可能含密钥、令牌或个人信息,消费者侧禁止写入日志** |
| `LiteGate-Deadline` | 同步必有;异步仅在配置 `message_deadline` 时下发 | 绝对截止时间(Unix 毫秒时间戳)。语义是**这份工作还有多久失去价值**,不是网关等了多久 |
| 白名单业务 Header | 可选 | 见 4.3 |

**消费者 → LiteGate(响应)**

| Header | 说明 |
|---|---|
| `LiteGate-Http-Status` | HTTP 状态码,**必须在 200–599**。缺省为 `200`。1xx 和越界值会被拒绝为 `502` |
| `Nats-Http-Status` | 旧名,仅作向后兼容读取,**新消费者请用上面那个** |
| `LiteGate-Request-Id` | 可选。**若设置,必须与请求的值一致**,否则网关返回 `502`(防串包) |
| 业务 Header | 如 `Content-Type`,原样回写给 HTTP 客户端 |
| `msg.Data` | 原始响应体,直接写入 HTTP 响应 |

响应中所有 `LiteGate-*`、`Nats-*` 前缀的 Header 以及 hop-by-hop Header(`Connection` / `Transfer-Encoding` / `Content-Length` / `Set-Cookie` 等)**不会**回写给客户端。

### 4.2 `envelope_json` 模式(兼容备选)

整个请求打包成一个 JSON 对象放在 `msg.Data`,**请求体经 Base64 编码**(体积 +33%,有 CPU 开销)。

```jsonc
// 请求
{ "version": 1, "request_id": "...", "client_request_id": "...", "trace_id": "...",
  "tenant_id": "...", "operation": "<subject>", "method": "POST", "path": "/legacy/orders",
  "query": "id=123&type=A", "deadline": "RFC3339Nano", "content_type": "application/json",
  "headers": {}, "body_base64": "..." }

// 响应
{ "version": 1, "request_id": "<必须与请求一致>", "status": 200,
  "content_type": "application/json", "headers": {},
  "body_base64": "...", "error": "可选错误描述" }
```

约束:`version` **必须为 1**;`request_id` 必须回填且一致;`status` 必须在 200–599(否则若带 `error` 字段则降级为 `502`,不带则报错)。

> **选型建议**:新消费者一律用 `nats_headers`。`envelope_json` 只在消费端难以处理 NATS Header 时使用。

### 4.3 Header 透传规则(默认白名单)

入站 Header 按以下顺序过滤:

1. **无条件丢弃** 所有 `LiteGate-*` 和 `Nats-*` 前缀(防客户端伪造控制头)
2. **无条件丢弃** 敏感 / hop-by-hop:`Authorization`、`Cookie`、`X-Api-Key`、`Host`、`X-Forwarded-*`、`Connection` 等
3. **白名单放行**:默认白名单为 `content-type`、`accept`、`accept-language`、`content-encoding`;配置 `headers_whitelist` 后为**默认白名单 ∪ 自定义白名单**

即:**未列入白名单的 Header 一律不会到达消费者。**

---

## 5. 配置参考

### 5.1 连接级(`plugin-config.yaml`,基础设施配置)

```yaml
plugins:
  nats:
    connections:
      legacy:
        servers: "nats://nats-1:4222,nats://nats-2:4222"   # 必填,缺失则 fail-closed 报错
        credentials: "${LITEGATE_NATS_CREDS}"              # 或 token / user+password
        connect_timeout: "3s"
        reconnect_wait: "1s"
        max_reconnects: "-1"                               # -1 = 无限重连
        name: "litegate-legacy-bridge"
```

- 键路径也支持简写 `nats.connections.<name>.<key>`
- 所有值都经过 `os.ExpandEnv` 展开(注意:含 `$` 字面量的密码会被误展开,建议改用 `credentials` 文件)
- **`servers` 缺失时直接报错,不会静默回退到 localhost**

### 5.2 路由级(站点配置)

| 字段 | 默认值 | 说明 |
|---|---|---|
| `mode` | `request` | `request` / `publish` / `jetstream_publish` |
| `connection` | `default` | 引用上面的连接名 |
| `subject` | 二选一必填 | 静态 Subject,加载期严格校验 |
| `subject_from` | 二选一必填 | 动态 Subject 来源,接受 `query.<键>`、`header.<键>` 或 `body.<键>`。见 5.3 |
| `payload_from` | 空(原样透传) | 从 JSON Request Body 的顶层字段提取消息体,接受 `body.<键>`(如 `body.content`)。若为 JSON String 会自动解引号 |
| `stream.name` | 空 | 绑定的 Stream 名称。配置后在请求期主动校验 Stream 覆盖,缺流提供明确诊断指导;若不配则完全跳过拓扑校验(此时流不存在会由 NATS 返回原生的 'no response from stream') |
| `stream.create_if_absent` | 空 | 兜底建流配置(含 `subjects`, `retention`, `storage`, `max_age`, `duplicates`, `replicas`)。流已存在时原样复用绝不覆盖 |
| `subject_prefix` | 空 | 动态 Subject 的静态前缀,最终 = `<prefix>.<topic>` |
| `subject_default` | 空 | 来源取不到值时的兜底 topic;不配则返回 `400` |
| `subject_allowlist` | 空 | 允许的 topic 列表。`["*"]` 表示放行任意合法 topic |
| `response_body` | 空 | 异步模式响应体模板,支持 `{{request_id}}` / `{{subject}}` / `{{mode}}`;JetStream 还支持 `{{stream}}` / `{{sequence}}` / `{{duplicate}}`。不配则返回包含 PubAck 元数据的默认 JSON |
| ~~`timeout`~~ | `5s` | ⚠️ **当前无法在站点配置中设置**,见下方说明。实际固定为默认值 `5s` |
| `publish_timeout` | `3s` | `publish` 的 Flush 上限 / `jetstream_publish` 的 PubAck 上限。**仅约束网关自身的发送,不会传给消费者** |
| `message_deadline` | 空(不下发) | 异步消息的**业务有效期**。不配则不下发 `LiteGate-Deadline`,消费者不会因排队时间长而丢弃任务 |
| `envelope_mode` | `nats_headers` | `nats_headers` / `envelope_json` |
| `max_in_flight` | `0`(不限) | 路由级在途并发上限,超限立即 `429` |
| `max_request_body` | `1048576`(1 MiB) | 超限返回 `413`。**必须 ≤ NATS 服务端 `max_payload`** |
| `response_status` | `202` | 异步模式的成功状态码,必须 200–599 且不能是 204/304 |
| `idempotency_header` | 空(默认优先认 `Idempotency-Key` 再认 `X-Request-Id`) | 自定义提取客户端幂等键的 Header 名(如 `x-msg-id` / `X-Order-Id`)。配置后自动放行透传至 NATS Headers 并用于生成 `Nats-Msg-Id` 进行去重 |
| `headers_whitelist` | 空 | 追加到默认白名单之上 |

```yaml
routes:
  - name: legacy-order-query
    match:
      rule: "PathPrefix(`/legacy/orders/query`)"
    action:
      type: nats
      mode: request
      connection: legacy
      subject: legacy.orders.query.v1
      max_in_flight: 200
```

> ⚠️ **已知问题:`timeout` 字段名与 LiteGate 内建字段冲突,插件收不到。**
>
> `internal/loader/types.go` 的 `Action` 结构体已声明 `Timeout int`(单位:秒)。YAML 会把 `timeout` 绑定到该内建字段,因此**它不会进入 `Extra`**,而插件只能通过 `Extra` 读取自定义参数([action/registry.go 的 `actionConfigAdapter.Get`](https://github.com/jamesleeon/LiteGate/blob/master/internal/action/registry.go))。后果:
>
> - 写 `timeout: 5s` → **整个站点加载失败**(`cannot unmarshal !!str '5s' into int`)
> - 写 `timeout: 5` → 静默落入内建字段,插件仍用自己的默认值 `5s`
>
> 在修复前,同步超时**只能使用默认的 5s**。修复方向二选一:把插件字段改名为 `request_timeout` 之类不冲突的名字(改动小,推荐),或让 `actionConfigAdapter.Get` 在 `Extra` 未命中时回退到内建字段(影响所有插件,需谨慎)。

### 5.3 动态 Subject(用于替换 HTTP → MQ 生产者服务)

支持 `POST /mq?topic=xxx` 这类"一个端点 + 参数选队列"的老接口形态,便于把既有的 HTTP→RabbitMQ 生产服务迁移过来。

```yaml
routes:
  - name: legacy-mq-producer
    match:
      rule: "Path(`/mq/sync`)"
    action:
      type: nats
      mode: jetstream_publish
      subject_from: body.topic           # 从 JSON body 的 {"topic": "..."} 取
      payload_from: body.content         # 从 JSON body 的 {"content": "..."} 取真实消息体
      subject_prefix: "legacy."          # 最终 = legacy.<topic>
      subject_allowlist:
        - order_created
        - user_updated
      response_status: 200
      response_body: '{"code":1,"message":"success","success":true,"data":null}'
      stream:
        name: LEGACY_MQ
        create_if_absent:
          subjects: ["legacy.>"]
          retention: workqueue
          storage: file
          max_age: 168h
          duplicates: 2m
          replicas: 1
```

**安全约束(全部在加载期或请求期强制):**

| 约束 | 行为 |
|---|---|
| **必须收口** | `subject_from` 启用时,`subject_allowlist` 与 `subject_prefix` **至少配一个**,否则加载期报错。想完全放开必须显式写 `subject_allowlist: ["*"]` |
| topic 字符集 | 必须匹配 `[a-zA-Z0-9_-]+(\.[a-zA-Z0-9_-]+)*`,不合法返回 `400` |
| 通配符 | topic 与前缀均禁止 `*`、`>` |
| 保留命名空间 | topic 与前缀均禁止 `_INBOX`、`$SYS` 开头 |
| 白名单不匹配 | 返回 `403` |
| 取不到值且无 `subject_default` | 返回 `400` |

**白名单的匹配语义**:条目可写裸 topic(`order_created`)或完整 subject(`legacy.order_created`),两种写法都会被**归一化成最终 subject 后再比较**。不会出现"条目写完整形态、却被裸值绕过发到别处"的情况。

> ⚠️ **应用层白名单不是唯一防线。** LiteGate 使用的 NATS 账号应当只被授予目标前缀(如 `legacy.>`)的 publish 权限 —— 这一层在 NATS 服务端强制,配置写错也绕不过去。两层都要有。

### 5.4 Subject 模板(多租户分层)

按请求字段拼出分层 subject,典型用法是把租户放进 subject,供下游按租户分流到各自集群组:

```yaml
action:
  type: nats
  mode: jetstream_publish
  subject_template: orders.{body.tenant_id}.created   # {body.x} / {header.x} / {query.x}
  stream:
    name: ORDERS
    create_if_absent: { subjects: ["orders.>"], retention: limits, storage: file, max_age: 72h, duplicates: 2m, replicas: 1 }
```

`{"tenant_id":"t001", ...}` → `orders.t001.created`。订阅侧:`orders.>` 收全部租户,`orders.*.created` 收所有租户的下单事件,`orders.t001.>` 只收 t001。

| 规则 | 行为 |
|---|---|
| 占位符 | 必须独占一段;第一段必须是字面量(命名空间由运维决定,调用方改不了) |
| 占位符取值 | 只允许 `[A-Za-z0-9_-]`,1–128 字符;不能含 `.`(不能多造层级)和 `*`/`>`;JSON 数字也可 |
| 取不到值 / 值非法 | 返回 `400` |
| 组合限制 | 不能与 `subject`、`subject_from` 同用;`subject_prefix`/`subject_default`/`subject_allowlist` 只属于 `subject_from` |
| 指标标签 | 用模板本身(如 `orders.{body.tenant_id}.created`),不会因租户数膨胀 |

> ⚠️ 租户取自请求 body,网关不校验它是否属于调用方。伪造一个**存在的**租户 ID 会被正常投递到该租户,下游分流识别不出来;适用于内网、调用方可信的场景。

**外部调用方场景:用 URL 路径和网关已验证的身份定 Subject**

除 `query.` / `header.` / `body.` 外,`subject_from`、`subject_template` 占位符、`schedule.key_from` 等所有"字段来源"还支持:

| 来源 | 含义 |
|---|---|
| `path.N` | 匹配路由前缀之后的第 N 段(从 1 起)。路由 `/nats` 下 `POST /nats/orders_created` 取 `path.1` = `orders_created`。前缀只在路径段边界匹配 |
| `auth.tenant` | 网关**已验证**的租户(需 `X-Lito-Verified: true`,客户端自带的 `X-Tenant-ID` 不认)。取不到返回 `403` |
| `auth.site` | 请求所属站点名。取不到返回 `403` |

```yaml
# 外部调用方只能写进自己租户的命名空间,租户由网关认证结果决定,调用方无法伪造
subject_template: tenants.{auth.tenant}.events.{path.1}
# REST 风格:POST /mq/order_created → legacy.order_created
subject_from: path.1
subject_prefix: legacy
subject_allowlist: [order_created]
```

---

## 6. 错误映射

| 情况 | HTTP 结果 |
|---|---|
| 正常 Reply | 使用 `LiteGate-Http-Status`,缺省 `200` |
| 无消费者(No Responders) | `503` |
| 等待 Reply 超时 / Publish Flush 超时 | `504` |
| 连接不可用 / 连接配置缺失 | `503` |
| 回复格式非法(状态码越界、`request_id` 不匹配、JSON 版本错、Base64 解码失败) | `502` |
| 请求体超过 `max_request_body` | `413` |
| 在途并发超过 `max_in_flight` | `429` |
| 客户端主动断开 | 终止等待,不写响应 |

所有错误均以 `*action.ActionError` 返回给网关 Executor 统一渲染,插件**不直接写错误响应**,因此可被路由的 `on_error` 降级策略接管。

---

## 7. 消费者实现契约

> **这一节是编写 Sidecar 或 Go 消费者时的唯一依据。**

### 7.1 同步消费者(`mode: request`)

```go
nc.QueueSubscribe("legacy.orders.query.v1", "orders_workers", func(msg *nats.Msg) {
    reqID := msg.Header.Get("LiteGate-Request-Id")   // 幂等键,始终存在

    // 1. 检查绝对截止时间,已超时则直接丢弃,不做无用功
    if ds := msg.Header.Get("LiteGate-Deadline"); ds != "" {
        if ms, err := strconv.ParseInt(ds, 10, 64); err == nil {
            if time.Now().UnixMilli() > ms {
                return
            }
        }
    }

    // 2. msg.Data 就是原始 HTTP Body,无编码
    body, status := handle(msg.Data)

    // 3. 回复
    reply := nats.NewMsg(msg.Reply)
    reply.Header = make(nats.Header)
    reply.Header.Set("LiteGate-Http-Status", strconv.Itoa(status))
    reply.Header.Set("LiteGate-Request-Id", reqID)   // 建议回填,网关会校验一致性
    reply.Header.Set("Content-Type", "application/json")
    reply.Data = body
    _ = msg.RespondMsg(reply)
})
```

> ⚠️ **异步模式下不要拿 `LiteGate-Deadline` 当"过期即丢弃"的依据。**
>
> 该 header 只在路由配置了 `message_deadline` 时才下发,语义是业务有效期。异步消息在流中排队是**可靠投递的正常现象**,把排队时间当作过期并 `Term()`,会把调用方被承诺一定会执行的任务永久丢掉。
>
> 网关侧已保证不会把 `publish_timeout`(仅约束自身发送)写成消息的 deadline。

**必须遵守**:

- 使用 **Queue Group** 订阅,组名相同的消费者之间自动负载分担 —— 这是新旧服务混布灰度的基础
- 回复状态码**必须在 200–599**,1xx 会被网关拒绝为 `502`
- 若回填 `LiteGate-Request-Id`,**必须与请求一致**,否则网关判定串包返回 `502`
- **务必总是回复**。不回复会让网关等到 `timeout` 才返回 `504`,白白占用在途配额
- **日志脱敏**:只记录 `LiteGate-Request-Id`、`LiteGate-Path`、耗时和结果分类。**`LiteGate-Query` 和请求体禁止整体入日志** —— query 中常含 `token`、`api_key`、手机号等敏感值

### 7.2 JetStream 消费者(`mode: jetstream_publish`)

网关只负责 Publish。消费侧的 Stream、Durable Consumer、`MaxAckPending`、最大投递次数、死信策略**全部由你自己或 NATS 运维配置**,网关不参与。

### 7.3 灰度迁移

新 Go 服务与旧 Sidecar **加入同一个 Queue Group**,NATS 自动在两者间分发。加减实例即调整流量比例,**网关配置一行不用改,对外 HTTP API 完全无感,随时可回滚**。

### 7.4 幂等是消费者的责任(重要)

JetStream 是 **at-least-once**;Core NATS Request-Reply 在超时 / 崩溃时客户端也可能重试。因此:

> **有副作用的业务,必须以 `LiteGate-Request-Id` 为键,在业务数据库事务内部完成去重。**

```sql
BEGIN;
  -- request_id 上建唯一索引
  INSERT INTO processed_requests(request_id, result) VALUES (:req_id, ...);
  -- 主键冲突 → 说明已执行过 → 回滚并返回上次存储的结果
  ...业务写入...
COMMIT;
```

**去重标记必须与业务写入在同一事务提交。** 原因:消费者在"提交成功"和"回复送达"之间崩溃时,外部**无法区分**它是提交前死的还是提交后死的,消息一定会被重投。这个窗口只能在数据库内部关闭,Sidecar 侧的任何逻辑都替代不了。

---

## 8. 明确的能力边界(不做的事)

- 不嵌入、不启动、不管理 NATS Server
- 不订阅、不消费任何消息;网关永远是发布 / 请求方
- 不创建 Stream、Consumer,不管理死信与重投策略
- 不做**无约束**的动态 Subject —— 动态来源必须经白名单或静态前缀收口(见 5.3),且永远不接受请求体拼接
- 不支持 KV / Object Store
- 不支持 SSE / WebSocket → NATS 的多结果流式返回
- 不自动重试同步请求

---

## 9. 已知缺口(实现待补)

| 缺口 | 影响 | 优先级 |
|---|---|---|
| Header 大小不受约束 | `max_request_body` 只约束 body。超长 query string 叠加接近上限的 body,可能让 NATS 消息总大小超过服务端 `max_payload`,publish 报错后被映射成 `502`,错误信息难以定位 | 中 |
| Pending Buffer 未监测 | `publish` 模式仅靠 `FlushTimeout` 间接兜底,未按设计文档读取客户端缓冲水位做 fail-closed | 中 |
| `counters` 不清理 | `max_in_flight` 计数器 map 以 `connection:subject` 为键,路由删除后条目泄漏(量级小) | 低 |
| `os.ExpandEnv` 副作用 | 含 `$` 字面量的密码会被误展开成空串 | 低 |

---

## 9.5 可观测性

在 `config.yaml` 打开 `metrics.enabled` 后,`/metrics` 暴露以下指标（NATS 已默认编入）:

| 指标 | 标签 |
|---|---|
| `litegate_nats_requests_total` | connection, subject, mode, **status**, **result** |
| `litegate_nats_request_duration_seconds` | connection, subject, mode |
| `litegate_nats_inflight_requests` | connection, subject |
| `litegate_nats_publish_bytes_total` | connection, subject, mode |
| `litegate_nats_connection_status` | connection(1 = 可用) |
| `litegate_nats_reconnects_total` | connection |

**`status` 与 `result` 都记录**,因为它们回答不同的问题:status 是调用方看到的,result 是原因。同样是 `503`:

```
result="no_responders"   ← 没有消费者订阅该 subject
result="unavailable"     ← NATS 连接断开或配置缺失
result="rejected"        ← max_in_flight 耗尽(背压)
```

三者的修复动作完全不同,只有 status 时全是一片 503。完整取值:`ok` / `no_responders` / `timeout` / `rejected` / `unavailable` / `bad_reply` / `too_large` / `forbidden` / `bad_request` / `canceled` / `error`。

**标签基数**:全部由配置约束。**动态 subject 路由上报固定的 `<prefix>.<dynamic>` 桶** —— 若用解析后的实际 subject,调用方就能通过传不同 topic 创建时间序列。需要按具体 topic 排查时看访问日志。

---

## 10. 当前状态

- 实现位置:`internal/plugins/nats/`(树内插件)
- 注册方式:`cmd/litegate/plugins.go` 默认注册，标准发行版直接携带 NATS Action，无需 `-tags nats`
- 自检:`litegate plugins list` 会列出 `action nats`,可确认二进制是否带了该插件
- 连接策略:**懒连接** —— 编译但未配置 NATS 路由时不会主动连接
- 热更新:make-before-break(锁外拨号,新连接建立成功才切换,失败保留旧连接),引用计数优雅 drain,在途请求不会被中断
- 构建与测试:`go build ./cmd/litegate` 与 `go test ./internal/plugins/nats/...` 均通过
