# IDS 实现 SaaS 登录与集群选路

IDS 可以把 SaaS 的 login、api、logout、refresh 分别实现为业务插件。应用按集群部署，共享应用负责租户身份验证和独立数据库选择；网关负责把请求送到所属集群，不管理租户数据库。

登录前，网关通过租户平台知道集群 code，但应用尚未返回 token。可选的 `IDSResponseHandler.OnResponse` 补齐这个时间差：请求阶段保存 IDS 信息，应用登录成功后取得响应 token，再建立会话到集群信息的映射。

## 四条业务路径

| 路径 | 请求阶段 Evaluate | 响应阶段 OnResponse |
| --- | --- | --- |
| login | 查询租户平台，确定集群，生成关联头和私有 State | 校验关联头、取得 token，写入会话映射和租户索引 |
| api | 从请求头取 token，查询会话映射，生成 Match/Meta | 不需要实现 |
| logout | 根据会话映射选路，保留待删除的会话 key | 应用退出成功后删除映射和索引成员 |
| refresh | 用旧会话信息选路，生成新的关联头 | 原子建立新 token 映射并删除旧 token 映射 |

这些 Provider 可以在一个 Go 包里注册成四个名字，也可以分别发布。业务共用存储协议，不要求共用一个 Provider 实例。api 插件不实现 OnResponse，也不携带 State。

## 请求与响应如何关联

```text
POST /login，携带租户提示信息
  → login IDS 查询租户平台：tenant-a 属于 cluster-a
  → 生成随机关联 key，注入 X-IDS-Correlation
  → State 保存关联 key、tenant_id、cluster_code、租户版本
  → Match 限定 cluster-a，网关转发到应用
  → 应用登录成功，在响应头返回原关联 key 和 X-Access-Token
  → login IDS OnResponse 校验本次关联，写入 token 摘要到 IDS 信息的映射
  → 删除内部关联响应头，再把登录响应交给客户端

GET /api，Authorization: Bearer <token>
  → api IDS 查共享存储，恢复所属集群信息
  → Match 限定集群，Meta 优先选择版本
  → 网关注入可信标记并转发
  → 应用自行完成认证与租户数据库访问
```

关联 key 建议使用至少 128 位密码学随机数。必须和本次 State 中的原值完全相等，不能仅判断某个缓存中存在该 key。State 是请求内存，不写 Redis、不传给应用、不写日志；只有会话映射跨请求保存。后端必须原样回传内部关联头，成功登录还必须返回唯一的 token 响应头。

租户提示信息只用于找登录集群，不是认证凭证。不能把任意客户端请求头当作可信租户身份。应用签发的 JWT 或其他 token 的真实性和有效期仍由应用或专用认证插件校验，会话映射不替代认证。

## YAML 配置

`plugins.yaml` 定义业务插件私有存储配置。网关只注入配置，不解析存储模式、不创建 Redis 连接、不管理会话：

```yaml
providers:
  saas_session:
    stores:
      saas-session:
        mode: redis
        prefix: "saas:session:"
        ttl: 2h
        redis:
          address: "192.168.50.32:6379"
          password_env: LITEGATE_SESSION_REDIS_PASSWORD
          db: 0
```

以上 Redis 地址为配置示意，使用时替换为实际地址；不要将密码写入路由配置。单网关实验可使用：

```yaml
providers:
  saas_session:
    stores:
      saas-session:
        mode: memory
        ttl: 2h
        memory:
          max_entries: 100000
```

当前支持 memory 和 redis。memory 重启丢失映射，不跨进程共享；redis 每次查询权威共享存储，适合多个网关。memory_redis 尚未支持，配置会明确报错；避免尚未落实跨实例本地缓存失效就开放混合模式。命名存储配置变化需要重启，普通路由热更新不会清除已有内存映射。

站点按 path 绑定插件：

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
        max_concurrency: 100
        fail_policy: deny
      header_projection:
        allowed_headers: [X-IDS-Correlation]
      options:
        store_ref: saas-session
        tenant_directory_url: http://tenant-platform.internal
        correlation_header: X-IDS-Correlation
        response_token_header: X-Access-Token
        success_status: "200"
        session_ttl: "2h"
  - match: {path_prefix: /api}
    service: api
    ids:
      provider: saas_api
      fail_policy: deny
      options:
        store_ref: saas-session
        tenant_directory_url: http://tenant-platform.internal
        request_token_header: Authorization
        request_token_scheme: Bearer
  - match: {path: /logout}
    service: api
    ids:
      provider: saas_logout
      fail_policy: deny
      response_hook: {enabled: true, timeout: 500ms, fail_policy: deny}
      options:
        store_ref: saas-session
        tenant_directory_url: http://tenant-platform.internal
        success_status: "200"
  - match: {path: /refresh}
    service: api
    ids:
      provider: saas_refresh
      fail_policy: deny
      response_hook: {enabled: true, timeout: 500ms, fail_policy: deny}
      header_projection:
        allowed_headers: [X-IDS-Correlation]
      options:
        store_ref: saas-session
        tenant_directory_url: http://tenant-platform.internal
        response_token_header: X-Access-Token
        success_status: "200"
        session_ttl: "2h"
```

`response_hook` 是网关配置。默认禁用，启用时默认 timeout=500ms、max_concurrency=100、fail_policy=deny；并发计数按 Provider 名共享，hook 与 Evaluate 的计数分开。options 是示例插件的业务配置，不是网关内置 SaaS 字段。只有 login、logout、refresh 声明响应能力并启用 hook；api 只处理请求。

## 插件接口与执行保证

```go
type IDSProvider interface {
    Evaluate(context.Context, plugin.IDSInput) (*plugin.IDSDecision, error)
}

type IDSResponseHandler interface {
    OnResponse(context.Context, plugin.IDSResponseInput) (*plugin.IDSResponseDecision, error)
}
```

注册描述中设置 `IDSProviderDescription.ResponseHook: true`。启用响应 hook 的 YAML 会检查能力声明，初始化时检查实际接口。现有请求插件和 YAML 不需要修改。`plugins inspect ids/saas_login` 会显示响应能力。

Evaluate 的 Forward 决策可携带 `State []byte`，上限 16 KiB；Respond 不允许 State，未启用 hook 的路由也不允许返回 State。响应输入包含不可变的请求信息快照、同一份 options/config 快照、State 副本、响应状态码和响应头副本、最终后端实例身份。响应阶段的请求快照不提供原始请求 body。

```go
func (p *loginProvider) OnResponse(ctx context.Context, in plugin.IDSResponseInput) (*plugin.IDSResponseDecision, error) {
    // 解析 State，判断业务成功，校验关联头并取得 token。
    // 插件读取 in.Config 中 providers.saas_session 的配置并操作自己的存储。
    // 写入成功后移除内部关联头；失败则返回 error。
    return &plugin.IDSResponseDecision{
        RemoveHeaders: []string{"X-IDS-Correlation"},
    }, nil
}
```

同一个请求始终使用原 Provider 实例和原配置快照。OnResponse 在最终后端响应进入客户端响应处理前执行一次，中间重试不执行。前置 IDS 拒绝、限流、发现失败或无后端响应时不执行，但释放状态。应用 401/403 等正常 HTTP 响应也进入 hook，由插件判断不建立映射并允许返回。

deny 下 hook 错误、panic、超时、并发拒绝或非法删除响应头返回网关 503，不暴露成功 token。普通 error 可在显式 allow 时放行；panic、超时和非法决策仍拒绝。应用登录成功但 Redis 写入失败时，应保持 deny，不对应用自动重试。迟到回调不能修改客户端响应；不遵守 context 的回调会继续占用并发槽位和 Provider 使用权，直到真实退出。

允许删除业务响应头，不允许删除传输字段。第一版不提供响应 body 修改能力。响应 hook 仅支持普通 HTTP proxy，不允许 proxy_cache，Upgrade 和 gRPC 请求会拒绝。第一版没有 WASM 响应接口；原 WASM 请求接口保持兼容。站点 YAML 和 Catalog 命名路由标签均支持 response_hook。

## 通过服务发现标签创建路由

标签配置与 YAML 配置进入同一套路由校验。login 示例：

```text
litegate.http.routers.login.entrypoints=web
litegate.http.routers.login.match.hosts=saas.example.com
litegate.http.routers.login.match.path=/login
litegate.http.routers.login.ids.provider=saas_login
litegate.http.routers.login.ids.allowedheaders=X-IDS-Correlation
litegate.http.routers.login.ids.response_hook.enabled=true
litegate.http.routers.login.ids.response_hook.timeout=500ms
litegate.http.routers.login.ids.response_hook.max_concurrency=100
litegate.http.routers.login.ids.response_hook.fail_policy=deny
litegate.http.routers.login.ids.options.store_ref=saas-session
litegate.http.routers.login.ids.options.tenant_directory_url=http://tenant-platform.internal
```

api 使用独立 router 和 saas_api，不开启 response_hook；logout、refresh 使用各自路径与插件并开启 hook。插件必须先通过 build 编译进网关。MCP 的 get_tag_reference、explain_tag 和服务标签模板已同步支持这些字段。

同名服务的路由标签应在所有实例上保持一致；cluster_code、version 等实例差异放在 metadata 或 litegate.instance.labels/meta 中。ids.selector_merge_policy 默认 intersect，允许显式 override。标签只选择业务插件并传递参数；Redis/cache 配置仍由 plugins.yaml 注入插件。动态站点配置不合法时保留之前的配置，并提供标签诊断。自定义入口端口的请求 Host 应包含实际端口。

可运行 `python examples/ids-saas-session/verify.py --catalog-tags`，通过实例标签创建全部四条路由，验证跨网关会话和通知闭环。证据保存到 artifacts/ids-saas-session/catalog-tags/verification.json。

新增指标：`litegate_ids_response_duration_seconds`、`litegate_ids_response_total{provider,result}`、`litegate_ids_response_inflight`。业务 key、token 和 State 不作为指标标签。

## 会话存储与租户索引

存储实现位于示例插件的 `ids/sessionstore`，不是网关 SDK。四个插件在插件包内共享并管理存储和连接池，从注入的 ConfigProvider 读取配置，使用 store_ref 选择插件私有存储。Group 在此业务中表示 tenant_id。

| 操作 | 作用 |
| --- | --- |
| Get | 查询未过期、租户版本仍有效的会话 |
| Put | 原子写会话与反向索引，检查租户版本；幂等重写不延长 TTL |
| Replace | 原子创建新 token 映射并删除仍有效的旧 token，阻止 refresh 重放 |
| Delete | 删除映射与索引成员，重复删除可安全执行 |
| GroupState | 获取租户版本和关闭状态 |
| ChangeGroup | 只接受更新的权威版本，使旧版本会话立即不可读 |
| PurgeGroup | 分批清理旧版本或关闭租户的映射与索引 |

示例插件在 Value 外维护 Group、Generation 和 ExpiresAt。示例 Value 保存 tenant_id、cluster_code、version；业务可扩展。key 使用 token 摘要；Redis 实现进一步哈希逻辑 key 和 group，索引是按过期时间排序的 Sorted Set，成员随访问和清理回收。会话 TTL 不能超过插件配置 store.ttl，不因普通 API 请求续期。

默认 memory 上限 100000 条映射，过期项在访问或容量回收时清理。Redis 使用原子 Lua 操作，并通过组版本检查拦截关闭期间的迟到登录或 refresh；group 状态保留用于阻止旧会话复活。Group generation 必须是正向递增整数，最大 2^53；会话 Value 最大 64 KiB。Redis 数据需要持久化和业务级清理策略，关闭状态不应随会话 TTL 自动消失。

当前实现面向单 Redis 服务连接，不宣称 Redis Cluster 客户端支持。两个网关必须使用相同 store 名、prefix、Redis 地址和 db。Redis 的有效期是服务器 TTL；客户端 ExpiresAt 仅用于展示。写入已提交但 HTTP 响应未交付时允许遗留映射靠 TTL 过期，不能保证 Redis 提交和客户端收到响应是同一事务。

## NotifySubscriber 与租户关闭

现有可选接口用于让插件主动处理租户变更：

```go
func (p *provider) NotifySubjects() []string {
    return []string{"notify.saas.tenant"}
}

func (p *provider) HandleNotify(ctx context.Context, n plugin.Notification) error {
    if n.Resync {
        // 与租户平台当前状态核对，不能只清内存再加载旧 Redis 数据。
        return p.reconcileTenants(ctx)
    }
    // 解析 tenant_id、version、disabled；ChangeGroup 后 PurgeGroup。
    return p.applyTenantChange(ctx, n.Data)
}
```

租户平台先保存关闭状态并增加版本，然后广播：

```json
{"tenant_id":"tenant-a","version":2,"disabled":true}
```

`ChangeGroup` 原子更新版本，旧会话立即不能读取，旧版本的在途 login/refresh 不能提交新映射；随后 `PurgeGroup` 做物理清理。重复和过时事件不会覆盖新状态。重新启用租户必须使用更高版本，旧 token 不会自动恢复。

Notify 是信号，不持久化、不重投。初次订阅、重连、队列溢出或 handler 失败会触发 Resync，插件必须从租户平台恢复状态。不能把“收到一次 NATS 消息”作为唯一关闭保证。示例为便于验证，会在每次 API 请求时核对租户平台状态，也在 Resync 时核对已见租户；生产可在插件内部使用有明确 TTL、断线恢复与失效规则的租户状态缓存。平台状态写入和广播之间仍存在传播窗口，不能承诺消息发布瞬间所有网关同步拒绝。

NATS 配置放在全局 `plugin_config.path` 指向的插件配置文件中：

```yaml
plugins:
  nats:
    connections:
      default:
        servers: nats://127.0.0.1:4222
shared:
  notify:
    connection: default
```

标准发行版包含 NATS。使用自定义 build 时加入 `--with github.com/jamesleeon/LiteGate/pkg/plugins/nats` 注册 NotifyTransport。Notify 发布入口必须限制为租户平台等可信主体；通知内容不包含原始 token。每个相关网关应收到失效广播，不能通过竞争消费者分配本地缓存失效任务。

## 可运行示例与验证

源码位于 [examples/ids-saas-session](../../examples/ids-saas-session/README.md)。示例同时注册四个 IDS Provider，api 没有 OnResponse；本地实验包含两个应用集群、租户平台、两个网关、NATS 和测试用 Redis fixture。

```powershell
powershell -NoProfile -File examples/ids-saas-session/build.ps1
python examples/ids-saas-session/verify.py
```

构建通过 `litegate build --with` 完成。验证脚本只监听 loopback，停止所有自行启动的进程，不修改已有 `.24/.32` 服务。实验 Redis 使用 miniredis，不是生产 Redis 的性能或 HA 测试。

验证覆盖：跨网关 login/api、租户集群隔离、refresh 原子替换、logout、TTL、并发登录、错误关联头和重复 token、应用拒绝、NATS 关闭租户和在途登录竞争。核心测试还覆盖 callback timeout/panic、配置快照、热退役、最终重试响应、非法头删除、反向索引批量清理及多请求 refresh 竞争。

测试结果保存到 `artifacts/ids-saas-session/verification.json`，不保存原始 token。原有 Match/Meta 语义和 IDS RateLimit 行为保持不变。

## 资源边界与生命周期

网关只负责注入配置、调用 Evaluate、保留本次请求 State、转发和调用可选 OnResponse。请求状态在回调完成或请求终止后释放。OnResponse 是长期 IDS Provider 的可选方法，不是独立创建的响应插件实例；超时回调尚未实际退出时保留 Provider 引用，防止提前关闭资源。

Redis 连接池和内存会话存储由插件管理，在 Provider Close 时通过插件自己的引用计数释放。四个业务插件共享私有存储，关闭其中一个不会清除其他插件正在使用的会话。api 无需实现 OnResponse。网关其他功能现有的 Redis/缓存不属于此 SaaS 业务链路。
