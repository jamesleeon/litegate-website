# IDS 请求响应关联设计

状态：设计基线。请求 State、可选响应 hook、插件私有 memory/redis 存储及 SaaS 示例已实现；实际接口、配置与限制以 [IDS SaaS 指南](ids-saas-session-guide.md) 为准。memory_redis 仍未开放。以下保留设计边界与验收要求。

## 业务边界

SaaS 共享应用按集群部署，集群内的应用自行处理租户到独立数据库的映射。网关只把请求送到租户所属应用集群。Router 决定服务名，IDS 决定该服务的 Match 和 Meta；Match 是硬边界，Meta 未命中回到同一 Match 的完整可用实例池。

login 插件查询租户平台取得集群 code，应用负责验证登录并签发 token。api 插件根据 token 查会话映射，恢复选路信息。logout 插件删除会话映射。租户关闭通过 Notify 使该租户会话失效，并阻止继续登录。

## 插件接口

保留 `IDSProvider.Evaluate(ctx, IDSInput)`。增加可选的 `IDSResponseHandler`，普通 api 插件只实现 Evaluate，不增加响应执行成本。

```go
// 拟议 SDK，名称和字段将在实现时落实。
type IDSResponseHandler interface {
    OnResponse(context.Context, IDSResponseInput) (*IDSResponseDecision, error)
}

type IDSResponseInput struct {
    Request  IDSRequest         // 不可变请求信息快照，不暴露请求流
    Options  IDSOptions         // 与 Evaluate 使用同一份路由 options 快照
    Config   ConfigProvider     // 与 Evaluate 使用同一配置快照
    State    []byte             // Evaluate 返回的插件私有状态的副本
    Response IDSUpstreamResponse
}

type IDSUpstreamResponse interface {
    StatusCode() int
    Header(name string) []string // 返回副本，不能修改后端响应
    Endpoint() IDSEndpointInfo   // 最终响应来自的实例身份
}

type IDSResponseDecision struct {
    RemoveHeaders []string      // 例如删除内部关联头，不向客户端暴露
}
```

在 `IDSDecision` 增加可选 `State []byte`，只允许 Forward 携带。State 上限建议 16 KiB；主机复制后保留到响应 hook 完成，请求结束后释放。禁用 hook 的路由返回 State 视为插件配置错误，不静默丢弃。

OnResponse 不接收或持有可变 `*http.Response`，第一版只支持 HTTP 最终响应头，不读取响应 body。nil decision 且 nil error 表示允许返回原响应；删除响应头的决策要完整校验后统一应用。不可删除 Content-Length、Transfer-Encoding 等传输字段。

插件自己判断什么状态代表登录成功，取哪个 token 头，生成什么 key/value。header 必须是单值；重复、缺失或不匹配由插件返回错误。它不修改已选中的服务、不触发第二轮代理，不负责数据库配置。

## 路由配置

下列 YAML 为拟议语法，不可直接用于当前版本。

```yaml
site: saas.example.com
services:
  api:
    discovery:
      name: api

routes:
  - match: {path: /login}
    service: api
    ids:
      provider: saas_login
      fail_policy: deny
      response_hook:
        enabled: true
        timeout: 500ms
        fail_policy: deny
      header_projection:
        allowed_headers: [X-IDS-Correlation]
      options:
        tenant_directory_ref: tenant-system
        store_ref: saas-session
        correlation_header: X-IDS-Correlation
        response_token_header: X-Access-Token
        login_success_status: "200"
        session_ttl: "2h"

  - match: {path_prefix: /api}
    service: api
    ids:
      provider: saas_api
      fail_policy: deny
      options:
        store_ref: saas-session
        request_token_header: Authorization
        request_token_scheme: Bearer

  - match: {path: /logout}
    service: api
    ids:
      provider: saas_logout
      fail_policy: deny
      response_hook:
        enabled: true
        timeout: 500ms
        fail_policy: deny
      options:
        store_ref: saas-session
        request_token_header: Authorization
        request_token_scheme: Bearer
        logout_success_status: "200"
```

`response_hook` 由网关解释；options 全部由插件描述并校验。hook 默认禁用；启用时 timeout 默认 500ms，fail_policy 默认 deny。注册描述新增 response_hook 能力声明，在加载配置时校验声明，在初始化 Provider 时校验实际接口，防止声明和实现不一致。启用 hook 的路由第一版必须是普通 HTTP proxy；静态内容、直接响应、Upgrade、gRPC 和 WASM hook 均不支持并明确报错，不静默跳过。现有 WASM 请求插件不受影响。

登录业务使用精确 path，避免 `/login-other` 被 path_prefix 意外命中。是否再限定 HTTP 方法由应用实际协议决定。

## 请求与响应的连接

1. Evaluate 查询租户信息，生成至少 128 位的密码学随机关联 key。
2. Forward 中返回 Match、白名单投影头 `X-IDS-Correlation` 和 State。State 包含关联 key、tenant_id、集群信息、租户状态版本等业务数据。
3. 网关保留本次请求的 State、options/config 快照及 Provider 使用权。无需建立 request_id 到状态的临时 Redis 或全局 cache。
4. 下游应用处理请求。登录成功响应必须原样回传 X-IDS-Correlation，同时返回约定 token 头。
5. 网关在代理重试结束后，对最终响应调用本次请求原 Provider 的 OnResponse，一次请求最多调用一次。
6. 插件对成功响应验证关联头与 State 中原值完全相等，不能只判断它在某个 cache 中存在；取 token 并确认租户仍允许建立会话。
7. 插件提交 token 摘要到 IDS 信息的映射及租户反向索引。返回删除内部关联头的决策。
8. 网关应用决策，然后发送原响应，结束请求后释放状态和 Provider 使用权。

失败登录的 401/403 仍进入 hook，由插件识别后放行，不要求 token 或关联头；仍移除内部关联响应头。前置 IDS Respond、限流 429、发现失败和没有最终后端响应的传输错误不调用 OnResponse，但必须释放请求状态。重试复用同一个请求关联 key，中间响应不触发 hook。

选路冲突检查、限流检查失败时也释放关联状态。镜像请求不执行登录绑定；响应缓存命中不会产生新的后端登录响应，因此启用 hook 的路由第一版拒绝配置响应缓存，不能让缓存绕过绑定。

## 回调执行保护

hook 在复制后端响应头或 WriteHeader 之前执行，客户端收不到未经映射提交的成功 token。默认 deny 时，错误、panic、超时和并发拒绝返回网关 503，并关闭后端响应 body；不将存储错误计入应用实例故障，不自动重试应用登录。allow 是显式可选策略，登录绑定样例固定 deny。

callback 使用有限超时和独立于 Evaluate 的并发保护；耗时、结果和 inflight 单独统计。回调必须遵守 context。Go 无法强制终止忽略 context 的插件，因此超时后保留其并发占位和 Provider 使用权直到实际退出，拒绝迟到的响应修改；存储调用必须支持期限。不能把超时理解成 Redis 一定没有提交。

Provider 在整个请求及其响应 hook 期间不能 Close。热更新先停止向旧实例分配请求，再等待已有调用释放；不能在响应阶段重新按名称获取另一实例。配额、生命周期和 hook 状态均需考虑迟到回调，避免 reset 后恢复无限调用。API 路由不建立响应状态或 hook lease，但 Evaluate 也需要安全的资源退役流程。

客户端断开前后的映射提交不能与 HTTP 交付做分布式事务。写入已成功但响应未交付时，允许残留会话按 TTL 清理；不能在无法确认交付结果时删除可能已被客户端使用的会话。绑定写入必须幂等，禁止重放扩大原到期时间。

## 会话存储配置

```yaml
# plugins.yaml：由 SaaS 插件解释
providers:
  saas_session:
    stores:
      saas-session:
        prefix: "saas:session:"
        ttl: 2h                   # 默认 TTL；路由 TTL 不得超过此上限
        redis:
          address: "192.168.50.32:6379"
          password_env: LITEGATE_SESSION_REDIS_PASSWORD
          db: 0
```

| 模式 | 语义 |
| --- | --- |
| memory | 单进程权威存储，有容量上限和 TTL；重启丢失会话 |
| redis | 共享 Redis 权威存储，支持多个网关实例 |
| memory_redis | Redis 权威存储，本机短 TTL 缓存；写 Redis 成功后写本地，缓存 miss 回填 |

请求关联状态始终在请求内存，不受 mode 控制。mode 决定跨请求的会话存储。TTL 为最终确定的到期时间，不随 API 请求滑动续期；如需 refresh，由业务插件建立新会话并按策略撤销旧 token。

网关只执行插件并注入配置，不提供 IDS 存储接口。memory、Redis、连接池、TTL、容量、会话映射、租户索引和原子操作全部由业务插件实现。示例的存储接口是插件私有实现，不属于 SDK。其他 IDS 插件可以自行选择数据存储。

第一版实现 memory 和单 Redis 实例；memory_redis 在跨实例失效与断线恢复落实后实现。模式枚举只开放已实现的模式，其余明确校验失败。Redis Cluster 的多 key 原子写涉及 hash slot，需单独确定分区策略；第一版不宣称支持 Cluster 原子索引。

## 会话与租户失效

插件保存如下信息，网关不解析：

```text
session:<token摘要> → {schema_version, tenant_id, cluster_code, meta, expires_at, tenant_version}
tenant:<tenant_id>:sessions → Sorted Set(token摘要, expires_at)
```

login 原子写入会话和租户索引；logout 原子删除会话和索引成员。Redis 中索引成员不随会话 TTL 自动过期，必须按 score 清理，并设置合理索引到期时间，避免缩短已有长会话的索引寿命。大租户撤销分批执行，不使用全库扫描或长时间阻塞脚本。

api 先查配置的存储，再生成 Match/Meta；miss 或过期返回 401，存储不可用返回 503，租户关闭返回 403，不把故障当作 miss，不回退到无隔离的服务池。转发前清除伪造信任头，由网关注入可信标记。标记只在可信网关连接上有意义，应用自身认证和数据库选择不变。

多网关的 logout 发布 session.revoked，租户平台保存关闭状态后发布 tenant.disabled。各实例广播订阅后清本地 cache；共享 Redis 删除幂等。租户事件需要 tenant_id 和单调版本或可核对的版本信息，重复事件无副作用，旧事件不能覆盖新状态。

租户关闭必须先更新权威关闭状态或版本，再清会话。login 回调提交时进行版本条件校验，防止关闭前发出的登录响应在清理后创建新映射。api 必须检查相应撤销状态，尤其清理仍在进行时。Redis 状态与租户平台之间需要明确同步和可恢复协议，普通查询后写入的两步检查不提供原子保证。

现有 Notify 是失效信号，不是可靠持久事件；启动、重连、丢消息或 handler 失败会触发 Resync。Resync 要清本地缓存并与权威租户状态核对，不能只清内存后重新读取尚未撤销的 Redis 会话。需要离线会话删除保证时，应引入可恢复的清理任务或持久事件消费，而不是仅依赖一次 Core NATS 发布。最大失效延迟要由状态校验与本地缓存 TTL 明确界定，不能承诺广播绝对实时。

## 实现位置与兼容性

| 位置 | 变更 |
| --- | --- |
| pkg/plugin/ids.go | State、可选响应接口、不可变响应视图和能力声明 |
| internal/loader/types.go 与 loader 校验 | response_hook 配置、默认值、动作和能力校验 |
| internal/middleware/ids_governance.go | 同一快照与同一 Provider 的请求状态、lease、清理 |
| internal/middleware/ids_guard.go | hook 独立执行保护、退役时等待实际调用退出 |
| internal/action/proxy.go | 最终响应进入 handleResponse 前调用 hook，覆盖全部早退路径 |
| examples/ids-saas-session/ids/sessionstore | 插件私有存储、连接管理、TTL、原子批处理 |
| examples/ids-saas-session | login/api/logout/refresh、token 回传及 NotifySubscriber 示例 |

旧插件及未配置 hook 的旧 YAML 保持现有行为。已部署的 header routing 和限流样例在本次设计阶段不改变。Catalog 标签生成、CLI inspect 和 doctor 也需明确显示能力和配置约束。第一版不为每个插件创建不同的响应 hook 注册名，避免配置里选中的 handler 与请求 Provider 不一致。

## 验收场景

1. login 回调取响应 token，与请求的集群信息绑定；api 读取映射正确选路。
2. api 插件不实现 OnResponse，选路、限流与现有行为一致。
3. 登录失败原样返回；成功响应缺 token、重复 token、缺关联头或关联不一致均拒绝。
4. 交换两个并发 login 的关联头不能交叉绑定，token 与 State 不进入日志。
5. Redis 提交失败返回 503，不先缓存成功；Redis 不可用与映射 miss 区分。
6. 重试只处理最终响应一次，前置限流、直接拒绝和传输失败释放状态。
7. 请求中途热更新仍使用原 Provider 和原配置快照，Close 不抢先关闭资源。
8. hook timeout/panic 受控，迟到回调不修改 HTTP 响应，并发占位不会过早释放。
9. 两个网关通过 Redis 共享会话；logout 和 TTL 使会话失效，租户索引同步清理。
10. 租户关闭撤销所有会话，关闭与登录并发不会重新建立有效映射；通知断线后可核对恢复。
11. 原 13 组选路测试和 8 组 IDS 限流测试继续通过。

## 实施顺序

先实现 State 和可选 response hook，用不依赖 Redis 的小插件验证请求与最终响应关联、失败策略和生命周期。随后实现命名 memory/redis 存储以及 login/api/logout 会话闭环。最后实现租户反向索引、Notify 撤销和断线恢复，再开放 memory_redis。每一步都有真实 HTTP 验证，避免只验证接口注册成功。
