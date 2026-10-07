# NATS Consumer 框架架构设计(原 Sidecar)

> **定位修订**:本组件不是"给 Delphi 用的桥接进程",而是一个**通用 NATS 消费者框架**。
> 「通过 IPC 转发给 Delphi」只是其中**一个可插拔的 Handler**,与纯 Go 业务 Handler 平级。
>
> 设计参照:`ecp.topicconsume.template.v3`(RabbitMQ 消费者框架)的分层与注册表模式
> 上游契约:[nats_capability_matrix.md](./nats_capability_matrix.md) 第 7 节
> 迁移背景:[nats_legacy_asset_integration_design.md](https://github.com/jamesleeon/LiteGate/blob/master/docs/zh-cn/nats_legacy_asset_integration_design.md)

---

## 1. 核心定位:框架,不是桥

```
        ┌─────────────────────────────────────────────┐
        │       NATS Consumer 框架(pkg/consumer)      │
        │  连接 / 订阅 / 重连 / 并发 / 分片 / Ack语义  │
        │  —— 业务无关,永远不用改                     │
        └──────────────────┬──────────────────────────┘
                           │ Handler 接口 + classname 注册表
        ┌──────────────────┼──────────────────┬───────────────┐
        ▼                  ▼                  ▼               ▼
  ┌───────────┐     ┌────────────┐    ┌────────────┐   ┌──────────┐
  │delphi_ipc │     │orders_go   │    │url_forward │   │  ...     │
  │ Handler   │     │ Handler    │    │ Handler    │   │          │
  └─────┬─────┘     └─────┬──────┘    └─────┬──────┘   └──────────┘
        │ 管道             │ 纯 Go 业务       │ HTTP
        ▼                  ▼                 ▼
  Delphi 进程池        数据库            下游服务
```

### 1.1 这个定位带来的最大好处:迁移变成改一行配置

```jsonc
// 迁移前
{ "subject": "legacy.orders.query.v1", "classname": "delphi_ipc" }

// 迁移后 —— 不改代码、不换程序、不动网关配置
{ "subject": "legacy.orders.query.v1", "classname": "orders_query_go" }
```

**灰度**:同一个 Queue Group 里起两个实例,一个配 `delphi_ipc`,一个配 Go Handler,按实例数调流量比例,随时可回滚。

这比"Sidecar 和 Go 服务是两个不同程序"的方案干净得多 —— 它们现在是**同一个二进制的两种配置**。

---

## 2. 可以从 RabbitMQ 框架直接搬的

| 能力 | 说明 | 搬运难度 |
|---|---|---|
| **Handler 接口 + classname 注册表** | `Register("name", handler)`,配置里 `classname` 对上号,新增消费者只加一行 | 直接搬,是整套设计的核心 |
| **可选接口能力探测** | `RoutingKeyProvider`、`ConsumerConfigValidator` 用类型断言探测,启动期 fail-fast | 直接搬 |
| **实例内分片(Sharding)** | `fnv(key) % concurrency` 把同 key 路由到固定 slot,保证有序 | 直接搬,**对 Delphi 比原版更契合**(见 4.2) |
| **panic 恢复** | 单条消息 panic 不能拖垮整个进程 | 直接搬,但重投策略要改(见 3.4) |
| **JSON 配置 + 多订阅** | 一个进程消费多个 subject,配置驱动 | 直接搬 |
| **启动期 fail-fast** | 配置与 Handler 能力不匹配立即拒绝启动 | 直接搬 |
| **退避 / 熔断** | `internal/backoff`、`internal/gobreaker` 保护下游 | 直接搬 |
| **分布式锁** | 同 key 跨实例互斥 | 可搬,但有更省的做法(见 3.5) |

---

## 3. 必须改的:NATS ≠ RabbitMQ

这几条是从 RabbitMQ 迁到 NATS 最容易踩的坑。

### 3.1 Core NATS 请求-应答没有 Ack —— Handler 接口要分叉

RabbitMQ 每条消息都要 Ack/Nack。但 NATS 有两套完全不同的语义:

| | 消息归宿 | 不处理会怎样 |
|---|---|---|
| **Core NATS 请求-应答**(`mode: request`) | **回复就是 ack**,没有 requeue、没有 discard | 网关空等到 timeout,返回 504 |
| **JetStream**(`mode: jetstream`) | Ack / Nak / Term / InProgress | 到 AckWait 后自动重投 |

所以框架需要**两个 Handler 接口**,订阅配置的 `mode` 决定用哪个,启动期校验 Handler 是否实现了对应接口(和现有 `RoutingKeyProvider` 校验同一套路):

```go
// 请求型:框架负责 RespondMsg
type RequestHandler interface {
    HandleRequest(ctx context.Context, req *Request) (*Response, error)
}

// 事件型:返回 Action,框架负责 Ack/Nak/Term
type EventHandler interface {
    HandleEvent(ctx context.Context, msg *Message) (Action, error)
}
```

### 3.2 Action 语义映射

| RabbitMQ | JetStream | Core NATS 请求 |
|---|---|---|
| `Ack` | `msg.Ack()` | 回复 2xx |
| `NackRequeue` | `msg.Nak()` / **`NakWithDelay(d)`** | 回复 5xx(无重投机制) |
| `NackDiscard` | `msg.Term()` | 回复 4xx |
| `Manual` | 手动 | 手动 |
| —— | **`msg.InProgress()`** | —— |

两个**白赚的增量能力**:

- **`InProgress()`** —— RabbitMQ 没有。Delphi 长事务超过 `AckWait` 时定期续期,避免被误判失败而重投。**长事务场景必须用上**。
- **`NakWithDelay(d)`** —— 服务端延迟重投。现有框架的 `nackdelayms` 是本地 `time.Timer` + map 维护(`timers map[*time.Timer]*amqp.Delivery`),NATS 直接甩给服务端,**这块本地状态可以整个删掉**。

### 3.3 ⚠️ Prefetch 的对应物,以及一个真陷阱

| | 缓冲行为 | 超限后果 |
|---|---|---|
| RabbitMQ `prefetch=N` | broker 最多推 N 条未 ack,其余**留在 broker** | 安全 |
| **NATS Core 推送订阅** | 客户端有 pending 上限 | ⚠️ **触发 Slow Consumer,消息被直接丢弃** |
| **JetStream 拉取消费者** | `MaxAckPending` + `Fetch(batch)` | 安全,且天然背压 |

**从 RabbitMQ 迁过来最容易踩这个** —— RabbitMQ 的 `prefetch` 是**信用制推送**(服务端按未 ack 数发额度,超出的留在 broker),而 NATS Core 推送**压根没有流控**,积压是**直接丢消息**,且丢了不易察觉。

#### Push 还是 Pull:分路径决策,不是全局二选一

Pull 是 **JetStream 独有的概念**,三种上游模式里只有一种能用:

| 上游 mode | 消费方式 | 能用 Pull? | 原因 |
|---|---|---|---|
| **`request`**(同步) | Core NATS 订阅 + 必须回复 | ✗ | 请求方在临时 inbox 同步等待且有超时,消息躺在流里等人拉取时早已超时;且 JetStream 中 `msg.Reply` 是 ACK 主题而非原请求方 inbox,请求-应答传递不过去 |
| **`publish`**(即时异步) | Core NATS 订阅(推送) | ✗ | **根本没有流** —— 消息不落盘,发出瞬间无人订阅即丢失,无处可拉 |
| **`jetstream_publish`**(可靠异步) | JetStream Consumer | ✓ **推荐** | 消息持久化在 stream 中,可按自身产能取 |

> ⚠️ **`publish` 是三种模式里最危险的**:无流控(积压触发 Slow Consumer 直接丢消息)、无持久化(Sidecar 重启即丢失),而网关已回 202 让客户端以为已受理。
>
> **凡涉及数据库写入的异步任务,一律用 `jetstream_publish`。** `publish` 仅适用于"丢失无所谓"的通知类场景(如缓存刷新 —— 后续消息会覆盖状态)。

#### Pull 带来的简化

异步走 Pull 后,同步路径那一整套防御机制**全部不需要**:

| | 同步 `request` | 异步 Pull |
|---|---|---|
| 背压手段 | 本地信号量 + 有界队列 + 池满回 503 | **就是"不 Fetch"** |
| 积压后果 | 丢消息 | 留在 stream,安全 |
| 快速失败逻辑 | 必须实现 | 不需要 |

```go
idle := pool.IdleCount()
if idle == 0 {
    continue    // 没空闲 worker 就不取 —— 背压就这一行
}
msgs, _ := sub.Fetch(idle, nats.MaxWait(5*time.Second))
```

同步路径需要大量防御,正是因为它不能 Pull。

因此**同步路径的背压完全由本框架自己承担** —— 5.1 的快速失败不是优化项,是该路径唯一的保护手段。

**异步路径为什么推荐 Pull**:Queue Group 里混布异构 worker 时(慢的 Delphi + 快的 Go 服务,性能可能差几十倍),推送模式由服务端决定分发,**不知道谁忙**;`MaxAckPending` 只能限制慢节点囤积上限,窗口内仍会让快节点空转。拉取则天然工作窃取,且批量可精确对齐真实产能:

```go
idle := pool.IdleCount()                              // 当前空闲 worker 数
msgs, _ := sub.Fetch(idle, nats.MaxWait(5*time.Second)) // 取多少 = 能处理多少
```

> 补充:JetStream **推送** + `MaxAckPending` 与 RabbitMQ `prefetch` 大致等价,代码更简单。若某个异步订阅的消费者是同构且性能一致的,用它也可以;Pull 的额外价值主要体现在**异构混布**场景 —— 而这正是本项目灰度迁移期的常态。

### 3.4 panic 恢复的重投策略要改

现有实现 panic 后无条件 `Nack(requeue=true)`,代码注释里也承认这可能无限循环。NATS 侧应改为按投递次数决策:

```go
if md, err := msg.Metadata(); err == nil && md.NumDelivered >= maxRedelivery {
    return Term, err          // 毒消息,终结,进 advisory
}
return NakWithDelay(backoff), err   // 退避重投
```

### 3.5 分布式锁:NATS 自带,可以省掉 lockd

现有方案用 lockd(Raft)。**JetStream KV 支持 TTL + CAS 语义**(`Create` 唯一性 + `Purge`),可以直接实现分布式锁,不用额外部署服务 —— NATS 反正已经在了。

不过 lockd 已经在跑且经过验证,复用也完全没问题。**建议 v1 先复用 lockd,减少变量**;等 NATS 运维稳定后再评估收敛。

### 3.6 毒消息处理位置不同

- RabbitMQ:`NackDiscard` + DLX(交换机配置)
- JetStream:`MaxDeliver` + `Term()`,超限进 advisory subject —— **在 Stream/Consumer 配置里设,不在代码里**
- Core NATS 请求:无重投概念,不存在毒消息问题

---

## 4. `delphi_ipc` Handler 的实现

> 注意:以下全部是**一个 Handler 的内部实现细节**,不是框架的一部分。框架不知道 Delphi 存在。

### 4.1 核心约束:一进程一管道一请求

| 收益 | 说明 |
|---|---|
| **不需要请求关联表** | 管道严格 1:1 串行,写进去一个请求,读出来必然是它的响应 |
| **崩溃检测零成本** | 进程死 → 管道 EOF,OS 直接告知,100% 可靠 |
| **卡死可安全 kill** | 一个进程只承载一个请求,强杀只损失它;DB 连接断开自动回滚 |
| **不必改造老代码** | 用进程数换并发,不用锁换并发 |

```
        Handler.HandleRequest()
                 │
                 ▼
        ┌──────────────────┐
        │ Worker Pool (N)  │  ← N = 并发上限
        │ [W1][W2]...[WN]  │
        └──┬───┬───────┬───┘
           │   │       │  管道(每 worker 一条)
        ┌──▼┐┌─▼─┐  ┌──▼┐
        │D1 ││D2 │  │DN │   Delphi 进程,各自单线程 + 独立 FDConnection
        └───┘└───┘  └───┘
```

### 4.2 分片(Sharding)在这里比原版更契合

RabbitMQ 版本里 slot 是 goroutine;在这里 **slot 直接就是 Delphi 进程 index**:

```
fnv(routing_key) % pool_size  →  固定投递到某个 Delphi 进程
```

同一个订单/客户的请求永远进同一个进程,而该进程本来就是单线程 —— **有序性天然成立,不需要额外的锁**。这是老业务"同 key 必须串行"需求最省的解法。

### 4.3 IPC 帧协议

```
┌──────────┬────────────┬─────────────┬──────────────┬────────────┐
│ magic 4B │ hdr_len 4B │ body_len 4B │ header(JSON) │ body(raw)  │
│  "LGF1"  │  大端序    │   大端序    │    UTF-8     │  原始字节  │
└──────────┴────────────┴─────────────┴──────────────┴────────────┘
```

- **magic `LGF1`**:魔数 + 版本。**读到不匹配说明流已失步,立刻杀掉该 worker 重启,禁止尝试重新同步** —— 这是老 Delphi 代码零散 `WriteLn` 污染 stdout 的主要防线
- **body 原始字节,不做任何编码**(无 Base64)
- header 用 JSON,Delphi 侧用 `JsonDataObjects` 单文件单元解析

**请求帧 header** —— 字段与 NATS `LiteGate-*` Header 一一对应,不重命名:

```json
{
  "type": "request",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "command": "orders.query",
  "method": "POST",
  "path": "/legacy/orders/query",
  "query": "id=123&type=A",
  "deadline_ms": 1725680000000,
  "tenant_id": "",
  "trace_id": "",
  "headers": { "Content-Type": "application/json" }
}
```

**响应帧 header**:

```json
{
  "type": "response",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": 200,
  "headers": { "Content-Type": "application/json" },
  "error": ""
}
```

`status` 必须在 200–599。`request_id` 必须原样回填 —— 管道是 1:1 的,它不用来路由,**只用作失步自检**:不匹配即协议错位,杀掉 worker 重启。

**控制帧**:`ping`/`pong`(启动握手验活 + 空闲健康检查)、`shutdown`(优雅停机)。
**启动握手是必须的** —— 进程拉起后先 `ping`,收到 `pong` 才入池,否则启动失败的进程会被反复投递。

### 4.4 传输通道

| 方案 | 适用 | 注意 |
|---|---|---|
| **子进程 stdin/stdout** | 首选 | 零命名零权限,进程死立刻 EOF。前提:老代码无零散 `WriteLn`,需 `{$APPTYPE CONSOLE}` |
| **命名管道** | 老代码有脏输出时 | 帧协议相同,切换成本约等于零 |

日志一律走 stderr。

### 4.5 Worker 状态机

```
  Starting ──握手 pong──> Ready ──取出──> Busy ──响应──> Ready
     │                      │              │
     │                      │              ├─ EOF/超时 ──> Dead
     └──握手超时──> Dead <──┴──────────────┘
                     │
                     └── 退避 ──> Starting(超熔断阈值则停止)
```

---

## 5. 关键失败处理

### 5.1 池满 → 立即回 5xx,不要静默丢弃

同步模式下不回复,网关会等满 `timeout`(默认 5s)才返回 504,白占在途配额。

```
取 worker:
  ├─ 有空闲            → 立即派发
  ├─ 无空闲,队列未满   → 入队等待(出队时重新校验 deadline)
  └─ 队列已满          → 立即回 503
```

### 5.2 Delphi 卡死 → 到期强杀

到 `deadline` 仍无响应:回复 504 → **强杀进程**(单进程单请求,只损失它;DB 连接断开自动回滚)→ Supervisor 重启 → 握手通过后重新入池。

### 5.3 Delphi 崩溃

管道 EOF 立即可知:

- 同步:回复 502,worker 标记死亡,退避重启
- JetStream:**Nak**(不是 Ack),按 3.4 的次数策略决定退避重投还是 Term

> ⚠️ 无论哪种,**都无法确定崩溃前数据库事务是否已提交**。这个窗口只能靠业务侧幂等关闭(能力矩阵 7.4 节),框架侧任何逻辑都替代不了。

### 5.4 崩溃循环熔断

进程反复启动失败(配置错、数据库不可达)必须指数退避,超阈值后停止重启并对该 subject 快速返回 503。否则会陷入「疯狂拉起 + 疯狂消费 + 全部失败」的放大循环。

### 5.5 优雅停机

1. 先 `Drain()` NATS 订阅 —— 停收新消息,已投递的仍会处理完
2. 等待在途请求完成(有宽限上限)
3. 发 `shutdown` 帧,超时未退则强杀
4. JetStream 未完成的不 Ack,交由重投

---

## 6. 配置草案

沿用现有框架的 JSON 风格与 `classname` 语义:

```jsonc
{
  "nats": {
    "servers": "nats://127.0.0.1:4222",
    "credentials": "${SIDECAR_NATS_CREDS}"
  },

  "subscriptions": [
    {
      "enabled": true,
      "subject": "legacy.orders.query.v1",
      "queue_group": "orders_workers",
      "classname": "delphi_ipc",        // ← 改这里就完成迁移
      "mode": "request",                 // request | jetstream
      "concurrency": 4,
      "sharding": true,                  // 需 Handler 实现 RoutingKeyProvider
      "command": "orders.query"
    },
    {
      "enabled": true,
      "subject": "legacy.reports.create.v1",
      "classname": "delphi_ipc",
      "mode": "jetstream",
      "durable": "reports_worker",
      "max_ack_pending": 8,
      "max_deliver": 5,
      "nak_backoff": "5s",
      "command": "reports.create"
    }
  ],

  "handlers": {
    "delphi_ipc": {
      "exec": "C:\\legacy\\OrderEngine.exe",
      "args": ["--ipc", "stdio"],
      "pool_size": 4,                    // ← 全系统最关键的参数,必须实测
      "startup_timeout": "10s",
      "restart_backoff": "1s",
      "restart_backoff_max": "60s",
      "crash_loop_threshold": 5,
      "queue_size": 32
    }
  }
}
```

---

## 7. 可观测性

链路 5 跳,缺分段指标排障靠猜:

```
consumer_messages_total{subject,classname,result}   # ok/timeout/crash/rejected/expired
consumer_queue_wait_seconds{subject}                # 排队时长 —— 判断池是否过小
consumer_handler_duration_seconds{classname}        # Handler 实际处理时长
consumer_workers{state}                             # ready/busy/dead(delphi_ipc 专有)
consumer_worker_restarts_total{reason}
```

`queue_wait` 与 `handler_duration` 的比值直接告诉你该加进程还是该优化业务。

**日志脱敏**:只记 `request_id`、`command`、`path`、耗时、结果分类。**`query` 和请求体禁止入日志**(可能含 token、密钥、个人信息)。

---

## 8. 实施顺序

| 阶段 | 内容 | 目的 |
|---|---|---|
| ① | **框架骨架 + `echo` Handler** | 验证订阅、注册表、Action 语义、LiteGate ↔ NATS 链路。**长期保留作对照组** |
| ② | **`fake_delphi` Handler** — 单线程、随机延迟、1% 崩溃、偶尔卡死 | 不引入真 Delphi 变量,压测进程池、崩溃重启、Nak、快速失败 |
| ③ | **真 Delphi 接管道** | 此时框架已验证,只剩编码与业务问题 |

> **不要跳过 ②。** 否则真 Delphi 出问题时无法分辨是框架 bug 还是 Delphi bug。

---

## 9. 待确认事项

| 事项 | 影响 | 如何确定 |
|---|---|---|
| **单 Delphi 进程并发能力** | 决定 `pool_size` 与部署规模 | 盘点全局状态与 `TFDConnection` 线程模型;预期为 1 |
| 老代码是否污染 stdout | 决定 stdio 还是命名管道 | 全量搜索 `WriteLn` 与第三方库输出 |
| 字符编码 | D2009 前为 AnsiString + 本地代码页 | 帧内 JSON 与 body 统一 UTF-8,Delphi 侧显式转换 |
| 是否 32 位进程 | 约束单进程内存与并发 | 检查编译目标 |
| 数据库连接数上限 | `pool_size × 每进程连接数` 不能超 | 核对数据库配置 |
| 是否复用 lockd | 见 3.5 | v1 建议复用,减少变量 |
| **异步结果如何回给客户端** | 异步模式下客户端只拿到 `202 + request_id`,目前**没有获知结果的途径** | 三选一:①结果写库 + `GET /tasks/{request_id}` 查询接口(**推荐**,Delphi 本就要写库,顺手写任务表);②结果发到另一 subject 再推送给客户端(需 SSE/WebSocket);③Webhook 回调(需客户端有可回调地址) |
