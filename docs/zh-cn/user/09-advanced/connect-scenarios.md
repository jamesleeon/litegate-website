# Connect 场景与架构指南

[Connect 配置与上线指南](connect.md)讲的是“怎么配”，本文讲的是“什么场景该怎么用、为什么这样设计”。
如果你正在规划一个需要把数据送进客户内网、却不想让任何一方开放入站端口的系统，建议先读完本文再动手配置。

本文的核心是第 2 节：**电商订单私有化落地**。这是 Connect 最典型、也最有价值的场景：
许多团队至今仍靠“开放消息队列端口给客户”或“让客户开防火墙”来解决它，而 Connect 可以把它简化为一次 HTTPS POST。

## 1. 先选模式

Connect 有三种发布方式，区别在于 **TLS 在哪里终止**，这直接决定了 Cloud 能否看到明文：

| 模式 | TLS 终止位置 | Cloud 能否看到明文 | 适合场景 | 文档 |
| --- | --- | --- | --- | --- |
| CLI HTTP 模式（`litegate connect http`） | Cloud | **能** | 快速发布单个内网网站、演示、内部工具 | [CLI 发布 HTTP 服务](connect-cli-http.md) |
| Site 模式（`publish_sites`） | Private / Home | **不能**（只按 SNI 转发密文） | 私有化部署、多租户数据通道、对数据保密有要求的场景 | [配置与上线指南](connect.md) |
| L4 Stream（`publish_streams`） | 取决于上层协议 | 取决于上层协议 | 非 HTTP 的 TCP 服务 | [配置与上线指南 §6](connect.md#6-发布-l4-tcp--socks5-stream) |

一句话选择：

- 只想把一个内网网站快速放到公网 → **CLI HTTP 模式**；
- 数据属于客户、或经过的云环境不应接触明文 → **Site 模式**；
- 协议不是 HTTP → **L4 Stream**。

> 本文后续内容都基于 **Site 模式**。CLI HTTP 模式在 Cloud 终止 TLS，不满足“Cloud 不接触明文”的前提，不要用于私有化数据通道。

## 2. 参考架构：电商订单私有化落地

### 2.1 问题是什么

电商 ISV 通常同时提供 SaaS 和私有化两种交付。订单必须在平台指定的云环境内（例如聚石塔）完成下载和转化，
而私有化客户要求数据最终落在自己机房的业务库里。于是需要一条 **“云内 → 客户内网”** 的数据通道。

常见做法和它们的问题：

| 做法 | 问题 |
| --- | --- |
| 对公网开放 RabbitMQ / Kafka 端口，客户自己来消费 | MQ 端口暴露在公网，要为每个客户维护账号和权限；客户需要写 MQ 消费代码；积压发生在客户侧，你看不到 |
| 让客户开放入站端口，由你推送 | 每个客户都要走一遍防火墙审批，很多企业根本不允许；客户网络变更就会断 |
| 客户定时调用你的 API 拉取 | 实时性差，拉取节奏由客户决定，失败重试和补数逻辑都压在客户开发身上 |
| VPN / 专线 | 成本高、开通慢，运维复杂，不适合几十上百家客户 |

### 2.2 Connect 的做法

```text
【平台云内（如聚石塔）】
  切片 ──▶ 下载 ──▶ 转化 ──▶ 消息队列（按租户分流）
                                    │
                        租户消费者（自带流控、重试）
                                    │  HTTPS POST  https://tenant-a.example.net/ods/v1/orders
                                    ▼
                  Cloud LiteGate A / B（只监听 443，按 SNI 转发密文，不解密）
                                    │  Connect 隧道（由 Private 主动建立）
【客户内网 / 私有化机房】             ▼
                  Private LiteGate（本地终止 TLS，私钥只在这里）
                                    │  jetstream_publish，等待 PubAck
                                    ▼
                  NATS JetStream（3 节点，replicas=3）
                                    │
                  ODS Consumer ──▶ 解析 ──▶ 客户业务库
```

关键变化：

- **客户只需要允许出站 443**。Private 主动连接 Cloud，隧道建立后，你的推送沿着这条隧道“反向”进入客户内网。客户不开任何入站端口。
- **你只需要开放 443**。消息队列端口不再对外暴露。
- **Cloud 看不到明文**。Cloud 只读取 TLS 握手中的 SNI 来决定转发给哪个租户，TLS 在 Private 上终止。
- **从“客户拉”变成“你推”**。投递节奏、重试、积压都在你自己的消息队列里，可观测、可控制。

### 2.3 对开发者意味着什么

这套方案最大的收益在开发侧：**推送方只需要会发 HTTP POST**。

| 角色 | 以前需要掌握 | 现在需要掌握 |
| --- | --- | --- |
| 云内推送方（你的开发） | MQ 客户端、连接管理、客户侧网络问题排查 | 发一个 HTTPS POST，按状态码决定 ack / 重试 |
| 客户侧开发 | MQ 消费、断线重连、TCP 长连接、消息确认 | 从本地 JetStream 消费（或直接用你交付的 ODS Consumer） |
| 运维 | 为每个客户开端口、配账号、配防火墙 | 为每个客户发一个 Token 和一个子域名 |

不需要自己实现 TCP 长连接、心跳、断线重连、内网穿透，这些都由 Connect 负责。

### 2.4 域名规划：公共域与租户域分离

建议准备两套独立的注册域名：

| 域名 | 用途 | 证书在哪里 | 示例 |
| --- | --- | --- | --- |
| 公共域 | Connect 控制端点、公共 API、静态资源 | Cloud（可用泛域名证书） | `connect.example.com` |
| 租户域 | 每个租户一个子域名，作为该租户的数据通道 | 各自的 Private，**每个租户一张精确证书** | `tenant-a.example.net` |

分离的原因：

- 租户域的证书只放在各自的 Private 上。某个租户的机器被攻破，影响范围只是它自己的子域名。
- 公共域的证书和凭据只在 Cloud 上，不会因为租户侧的问题泄露。
- Cookie、CAA 记录、证书签发额度都互不影响。

> 在本文的实践中，公共域对应 `example.com`，租户域对应 `example.net` 下的租户子域名。

### 2.5 推送契约

推送方与 Private 之间的约定非常简单：

**请求**

```http
POST /ods/v1/orders HTTP/1.1
Host: tenant-a.example.net
Content-Type: application/json
Idempotency-Key: tenant-a:batch-20261111-000123
Authorization: Bearer <推送方凭据>

{ ...一批订单，建议 200～400 单，1MB 以内... }
```

- `Idempotency-Key`：**必须携带**，同一批次重试时保持不变。长度 1–64 个字符，只允许 `[A-Za-z0-9_:-]`。
  建议使用 `租户:批次ID`。Private 会以它为基础生成 JetStream 的 `Nats-Msg-Id`，在去重窗口内重复投递只会被存一次。
- 订单数据本身保持平台要求的加密或脱敏状态，Connect 不关心 body 内容。

**响应**

| 状态码 | 含义 | 推送方应该怎么做 |
| --- | --- | --- |
| `202` | 已写入 JetStream 并收到 PubAck（响应体中 `jetstream.duplicate: true` 表示命中去重） | ack 上游消息 |
| `413` | 批次超过 `max_request_body` | 不要重试；拆小批次，或调整配置（见 §2.8） |
| `429` | Private 端在途请求达到 `max_in_flight` 上限 | 退避后重试 |
| `503` | 隧道离线、租户 Private 不可用，或 NATS 不可用 | 退避后重试，不 ack |
| 其他 `5xx`、超时、连接错误 | 结果未知 | 用**同一个** `Idempotency-Key` 重试，不 ack |

规则只有一条：**只有拿到 2xx 才 ack 上游消息，其他情况一律保留在上游队列里重试。**

### 2.6 可靠性语义

整条链路是 **“至少一次投递 + 两级去重”**：

| 故障位置 | 结果 | 由谁兜底 |
| --- | --- | --- |
| Cloud 宕机 | 推送失败 | 消息留在云内队列；内网 DNS 或推送方重试切换到另一台 Cloud |
| 隧道断开 / Private 宕机 | Cloud 返回 503 | 消息留在云内队列，Private 恢复后自动追赶 |
| NATS 不可用 | Private 返回 5xx | 同上 |
| 已写入 JetStream，但响应在返回途中丢失 | 推送方看到超时并重试 | JetStream 按 `Nats-Msg-Id` 去重 |
| 重试间隔超过 JetStream 去重窗口 | 可能写入两次 | ODS Consumer 按业务主键做幂等写入 |

因此需要满足两个配置约束：

1. **推送方的 HTTP 超时 < 上游队列的 ack 等待时间**，否则上游会在推送仍在进行时重投，造成不必要的重复。
2. **JetStream 的 `duplicates` 窗口 ≥ 推送方最长的重试间隔**。超出窗口的重复由 ODS Consumer 的幂等写入兜底，
   所以入库最好是“按订单号 upsert”，而不是“直接 insert”。

Cloud 上不需要任何队列或缓冲：它只负责转发，积压永远发生在你可控的云内队列里。

### 2.7 配置示例

#### Cloud（平台云内）

```yaml
connect:
  server:
    enabled: true
    hostname: connect.example.com
    path: /_litegate/connect/v1
    state_file: data/connect-registry.json
    peers:
      tenant-a:
        token_file: /etc/litegate/secrets/tenant-a.token
        # 路由授权：只允许该租户发布自己的子域名
        allowed_domains:
          - tenant-a.example.net
        # 证书授权：只允许为自己的子域名申请证书
        allowed_cert_domains:
          - tenant-a.example.net
        max_sites: 5
        max_connections: 512
        sessions: 4
```

要点：

- **每个租户的 `allowed_domains` 只写它自己的精确子域名**，不要所有租户都写 `*.example.net`。
- Cloud 直接监听 443，**不要在前面放七层负载均衡或 WAF**：七层设备会在自己身上终止 TLS，Cloud 拿不到原始 SNI，也就无法做密文转发。如果必须有负载均衡，用四层 TCP 透传。
- Cloud 需要持有租户域的 DNS 凭据，才能替 Private 完成 ACME DNS-01 验证（见 §4）。

#### Private（客户内网）

主配置：

```yaml
entrypoints:
  websecure:
    address: ":8443"
    tls: true

auto_cert:
  enabled: true
  email: ops@example.com
  storage_secret: "env://PRIVATE_STORAGE_SECRET"   # 本地私钥落盘加密，不要写明文
  certs_dir: ./certs
  dns_providers:
    # 证书委托 Cloud 签发：私钥在本机生成，只把 CSR 发给 Cloud
    - name: cloud-csr-delegate
      type: connect
      enabled: true
      domains:
        - tenant-a.example.net

connect:
  client:
    enabled: true
    name: tenant-a
    remotes:
      - https://connect-a.example.com/_litegate/connect/v1
      - https://connect-b.example.com/_litegate/connect/v1
    sessions: 4                  # 至少为 Cloud 数量的 2 倍
    token_file: /etc/litegate/secrets/tenant-a.token
    publish_sites: true
    publish_streams: false
```

NATS 连接（`plugin-config.yaml`）：

```yaml
plugins:
  nats:
    connections:
      ods:
        servers: "nats://10.0.0.11:4222,nats://10.0.0.12:4222,nats://10.0.0.13:4222"
        connect_timeout: "3s"
        reconnect_wait: "1s"
        max_reconnects: "-1"
```

租户 Site（`sites/tenant-a.yaml`）：

```yaml
domain: tenant-a.example.net
entrypoints:
  - websecure
tls:
  enabled: true                  # 证书由 auto_cert 的 connect 委托自动获取和续期
routes:
  - name: ods-orders
    match:
      path: /ods/v1/orders
      method: ["POST"]
    action:
      type: nats
      mode: jetstream_publish    # 等待 PubAck 后才返回 202
      connection: ods
      subject: ods.orders
      publish_timeout: 3s
      max_in_flight: 2000
      max_request_body: 4194304  # 4 MiB，留出余量
      stream:
        name: ODS_ORDERS         # 推荐由运维预先创建；以下参数仅用于兜底建流
        create_if_absent:
          subjects: ["ods.>"]
          retention: limits
          storage: file
          max_age: 168h
          duplicates: 30m        # ≥ 推送方最长重试间隔
          replicas: 3
```

> 同一个 Private 上可以按路径拆分多个路由，例如订单、退款、商品分别投到不同 subject。

#### 推送方（云内消费者）

伪代码：

```text
for msg in 上游队列.按租户消费(tenant):
    resp = POST https://{tenant}.example.net/ods/v1/orders
             headers: Idempotency-Key = "{tenant}:{msg.batch_id}"
             body:    msg.payload
             timeout: 30s                     # 小于上游 ack 等待时间

    if resp.status 为 2xx:
        msg.ack()
    elif resp.status == 413:
        告警并转人工 / 拆批后重新入队          # 重试不会成功
    else:
        msg.nack(延迟重试)                    # 429、503、5xx、超时、连接错误
```

推送方用内网 DNS 把 `*.example.net` 解析到 Cloud 的内网地址即可，不需要为每个租户单独配置。

### 2.8 容量与大促

大促的峰值首先由云内的切片、下载和队列吸收，这几层都可以横向扩容。
**进入隧道的流量取决于每个租户消费者的并发，而不是平台订单的峰值**。所以隧道和 Private 只需要按“消费速度”准备容量，不需要按大促峰值准备。
某个租户的网络慢或本地解析慢，结果只是它在云内的队列积压，不会报错，也不会拖累其他租户。

需要提前核算的几个上限：

| 位置 | 配置 | 建议 |
| --- | --- | --- |
| Private NATS 路由 | `max_request_body` | 大于最大批次，例如 4 MiB |
| NATS Server | `max_payload` | **≥ `max_request_body`**，这是 server 级配置，只调 stream 不够 |
| JetStream Stream | `max_msg_size`（如有设置） | ≥ `max_request_body` |
| Cloud Peer | `max_connections` | ≥ 该租户推送并发 |
| Connect 隧道 | 每个 stream 的 HTTP/2 流控窗口为 4 MB | 单租户吞吐还受客户上行带宽限制，大租户建议大促前实测 |

建议按字节数而不是订单数切批次，避免个别大订单把批次撑过上限。

估算示例：一个租户大促当天 100 万单，400 单一批，约 2500 批、2.5 GB，分摊到几个小时内，对隧道没有压力。
需要关注的是**积压时长**而不是积压条数：对发货时效敏感的租户，应该对“最老一条未投递消息的等待时间”设置告警。

## 3. 安全模型

### 3.1 各方能看到什么

| 组件 | 能看到 | 看不到 |
| --- | --- | --- |
| Cloud | SNI（租户域名）、流量大小和时间、来源 IP | 请求路径、头部、body |
| 平台云网络 | 与 Cloud 相同 | 同上 |
| Private | 完整明文 | — |
| 推送方 | 完整明文（它是数据的来源） | — |

“Cloud 看不到明文”成立的前提：

1. 使用 **Site 模式**，不是 CLI HTTP 模式；
2. 租户证书的**私钥只在 Private 上生成和保存**，从未经过 Cloud；
3. 推送方**严格校验证书**，不能关闭证书校验（例如 `InsecureSkipVerify`）。

需要说清楚的边界：推送方本身运行在平台云内，订单在源头就存在于平台环境中。
Connect 保证的是**转发这一段不经手明文**，而不是“平台完全接触不到数据”。
订单本身保持平台要求的加密或脱敏状态，是另一层保护。

### 3.2 为什么私钥必须留在 Private

如果 Cloud 持有某个租户证书的私钥，控制了 Cloud 的人只要改一下配置，把这个域名从“密文透传”改成“在 Cloud 上终止 TLS 再重新加密转发”，就能看到明文，而推送方拿到的仍是合法证书，完全察觉不到。

TLS 1.3 有前向保密，拿到私钥也解不开**过去**抓下的流量，但足以做**主动中间人**。所以“私钥不经过 Cloud”是整个安全模型的基础，而不是锦上添花。

### 3.3 推送方认证与来源限制

TLS 保证了“推送方连到的是真正的 Private”，但 Private 还需要确认“请求来自真正的推送方”：

- 在路由上启用认证中间件（例如 `api_key` 或 `jwt_auth`），见[认证概述](../05-middleware/authentication.md)；
- 通过路由级 `ip_restriction.allow_ips` 只允许推送方的出口网段。Site 模式下 Private 看到的是推送方的真实来源 IP；
- Token、DNS 凭据、`storage_secret` 一律用 `env://`、`file://` 或 `vault://` 引用，不写进配置文件。

## 4. 证书策略

租户证书采用 **CSR 委托签发**：

1. Private 在本地生成私钥和 CSR；
2. 通过 Connect 控制通道把 CSR 发给 Cloud；
3. Cloud 校验 CSR 中的每一个域名：不能是通配符、不能是保留域名、必须在 `allowed_cert_domains` 内、并且**当前由该 Peer 精确注册**；
4. Cloud 用自己持有的 DNS 凭据完成 ACME DNS-01 验证，把证书链（不含私钥）返回给 Private；
5. Private 校验证书与本地私钥匹配、覆盖所申请的域名后才启用，并在到期前自动续期。

详细流程、校验规则和配置见 [Connect 证书委托签发](../06-certificates/connect-csr-delegation.md)。

几条原则：

- **禁止向 Private 下发泛域名证书和私钥**。泛域名私钥一旦发到客户机器上，任何一个客户都能冒充所有租户。
- **每个租户一张精确证书**。一个租户出问题，不影响其他租户。
- **注意公网 CA 的签发额度**。Let's Encrypt 对每个注册域名每周约 50 张新证书（续期不计入），整个租户域共享这一额度。
  按 60 天续期估算，可支撑约三四百个租户。
- **规模更大时考虑私有 CA**。这条链路只走内网 DNS，唯一需要校验租户证书的是你自己的推送方，完全可以只信任一个专用的私有 CA：
  没有签发额度限制，也不依赖公网 DNS 验证。私有 CA 应与服务网格的 CA 分开，并用 Name Constraints 限制只能签发租户域。

## 5. 多 Cloud 与高可用

### 5.1 Cloud 侧

- 部署两台或以上 Cloud，Private 在 `remotes` 中列出全部 Cloud，`sessions` 至少为 Cloud 数量的 2 倍，保证每台 Cloud 上都有不止一条隧道；
- 每条 session 固定连接一台 Cloud，某台 Cloud 宕机后，另一台上的 session 仍然可用；
- 推送方通过内网 DNS 返回多个 Cloud 地址，或在失败后换地址重试，实现 Cloud 之间的切换；
- 每台 Cloud 各自维护注册表，互不依赖；需要确认单台 Cloud 能承担全部租户的连接和流量。

### 5.2 Private 侧（当前限制）

同一个 Connect 名称下，**后连上的实例会顶替先前的实例**。因此两台 Private 用同一个名称同时连接同一台 Cloud，会互相顶替、反复重连。在正式的多实例支持完成之前：

- **主备方式**：备节点平时不启动 Connect client，由外部机制（如 keepalived、systemd 健康检查）在主节点故障后拉起；
- **分 Cloud 双活**：Private-1 只连 Cloud A，Private-2 只连 Cloud B。两台 Cloud 的注册表相互独立，不会冲突；但 Private-1 故障时 Cloud A 会返回 503，需要推送方重试到 Cloud B。

下游是 JetStream 且带去重，两台 Private 同时写入是安全的，所以未来的多实例方案更适合做成**双活**，而不是主备。

## 6. 反模式

| 反模式 | 后果 | 正确做法 |
| --- | --- | --- |
| 私有化数据通道使用 CLI HTTP 模式 | TLS 在 Cloud 终止，Cloud 看得到明文 | 使用 Site 模式 |
| Cloud 前面放七层 SLB / WAF | 拿不到原始 SNI，密文转发失效；HTTP Upgrade 可能被拦截 | Cloud 直接监听 443，或用四层透传 |
| 向客户下发泛域名证书和私钥 | 任何客户都能冒充所有租户 | 每个租户精确证书，CSR 委托签发 |
| 所有租户共用 `allowed_domains: ["*.example.net"]` | 租户之间可以抢注、抢签彼此的域名 | 每个租户只授权自己的精确子域名 |
| 继续对公网开放 MQ 端口 | 攻击面大，账号权限难管理 | 推送走 Connect，MQ 只在内网 |
| 推送时不带 `Idempotency-Key`，或每次重试生成新 key | 超时重试会产生重复数据 | 同一批次始终使用同一个 key |
| 收到超时就 ack 上游消息 | 可能丢数据 | 只有 2xx 才 ack |
| 配置文件里写明文凭据 | 凭据随配置文件、备份、截图泄露 | 使用 `env://`、`file://`、`vault://` 引用 |
| 推送方关闭证书校验 | “Cloud 看不到明文”不再成立 | 严格校验；使用私有 CA 时只信任该 CA |

## 7. 上线检查清单

**Cloud**

- [ ] 直接监听 443（或四层透传），公共域证书有效
- [ ] 每个租户一个 Peer，独立 Token，`allowed_domains` / `allowed_cert_domains` 只含该租户的精确子域名
- [ ] 租户域的 DNS 凭据以引用方式配置，并确认 DNS-01 能正常完成
- [ ] 至少两台 Cloud，单台可承担全部流量

**Private**

- [ ] 只需出站访问 Cloud 的 443，无任何入站端口
- [ ] `storage_secret`、Token 均不以明文出现在配置中
- [ ] `auto_cert` 使用 `type: connect` 委托签发，首次启动后证书已就绪
- [ ] `sessions` ≥ Cloud 数量 × 2
- [ ] NATS `max_payload` ≥ 路由 `max_request_body` ≥ 最大批次
- [ ] Stream 已预先创建，`duplicates` ≥ 推送方最长重试间隔，`replicas` 与集群规模一致
- [ ] 路由已启用认证中间件和来源 IP 限制

**推送方**

- [ ] 严格校验证书
- [ ] 每个批次携带稳定的 `Idempotency-Key`
- [ ] HTTP 超时 < 上游 ack 等待时间
- [ ] 只在 2xx 时 ack；413 单独处理；其他情况重试
- [ ] 按租户独立消费和重试，一个租户故障不阻塞其他租户
- [ ] 对“积压时长”设置告警

**端到端验证**

- [ ] Dashboard 的 Connect 页面中，该租户在线、域名为 `ready`
- [ ] 推送一个测试批次，确认返回 202，且 JetStream 中可见
- [ ] 用同一个 `Idempotency-Key` 再推一次，确认响应中 `duplicate: true`
- [ ] 断开 Private 网络，确认推送方收到 503 且消息留在上游；恢复后自动追赶

## 8. 常见问题

**Q：Private 能不能不开放本地的 8443 端口？**
Connect 注入的流量不经过本地网络监听。如果本地没有直接访问的需求，可以用主机防火墙限制 8443 只允许本机访问。

**Q：客户已有自己的证书，能不能用？**
可以。在租户 Site 中直接配置 `cert_file` / `key_file` 即可，不需要启用委托签发。但要保证该证书的私钥只在客户的 Private 上。

**Q：同一个客户有多个业务系统，需要多个 Private 吗？**
不需要。一个 Private 可以发布多个 Site（受 `max_sites` 限制），也可以在同一个 Site 下按路径分发到不同的 subject 或上游。

**Q：客户要求数据先落到他们自己的 Kafka / RabbitMQ，而不是 NATS？**
把租户 Site 的路由 action 换成 `proxy`，转发到客户内网的写入服务即可；可靠性语义由该服务的返回码决定，推送契约（2xx 才 ack、带幂等键重试）保持不变。

## 相关文档

- [Connect 配置与上线指南](connect.md)
- [使用 CLI 发布内网 HTTP 服务](connect-cli-http.md)
- [Connect 证书委托签发与端到端私钥安全管理](../06-certificates/connect-csr-delegation.md)
- [Forward 与 Connect 总览](forward-and-connect.md)
- [NATS 部署指南](../../nats_deployment_guide.md)
