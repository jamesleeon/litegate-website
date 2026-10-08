# IDS Provider 插件开发与配置

定位与 IDS vs middleware 见 [IDS 概览](ids-overview.md)；架构语义见 [IDS Provider 架构](ids-architecture-v2.md)；避坑指南见 [IDS 插件开发注意事项与避坑指南](ids-plugin-caveats.md)；端到端场景见 [IDS 配方](ids-recipes.md)。

需要评估 Rust 等语言和独立热发布时，参见 [IDS WASM 插件开发指南](ids-wasm-plugin-guide.md)；该能力当前为实验性且默认不编译。

## 从开发到上线：四个环节

当前 Go IDS 插件采用编译注册。Sites 和 Litemesh 标签只引用插件，不能上传、安装或编译插件。`openapi-md5` 已在默认入口内置注册，下文用它串联配置与验收。第三方插件的 options 仍由各插件定义。V2 目前支持的是 `provider`，`plugin` 只是命名改进建议，尚不可直接配置。

### 1. 开发与发布

实现 `plugin.IDSProvider.Evaluate(ctx, input)`，从不可变 `input.Request` 读取请求，从 `input.Options` 读取路由参数。MD5 插件读取 appid、method、timestamp、signature 和原始 Body，再解析密钥和验签。协议见 [MD5 插件](openapi-md5-ids-plugin.md)。

- 业务验证通过：返回 `ActionForward`；只做验签时省略 `Discovery`。
- 业务验证失败：返回 `ActionRespond` 和 401/403，不返回系统 error。
- 密钥系统不可用等基础设施失败：返回 error，交给宿主执行 fail_policy。

通过 `RegisterIDSProvider("openapi-md5", registration)` 发布 Factory、Description、Options 描述和 Validate。另用 `RegisterManifest` 发布 `Kind: "ids"`、同名 Name、Version、`APIVersion: plugin.APIVersion`、Description 与 ConfigExample，使 CLI 能显示版本、用途和示例。IDS Description 与通用 Manifest 是两份元数据，目前 CLI inspect 读取 Manifest，并不会自动展示 IDS Options Schema。

在最终网关入口空导入插件包，再 `go build ./cmd/litegate`。Go 插件代码或注册发生变化需要重新编译并替换网关；仅修改路由参数则走配置热加载。不要将 Go Provider 单例的共享状态当成单请求变量。

### 2. 绑定到 Sites YAML

```yaml
site: open.example.com
https: true
/api:
  proxy: 127.0.0.1:8080
  ids:
    provider: openapi-md5
    fail_policy: deny
    options:
      secret_env_prefix: OPENAPI_SECRET_
      max_clock_skew: 5m
      max_body_size: 1MiB
```

后端地址为示例。`provider` 必须与注册名一致；options 由插件定义。密钥注入运行 LiteGate 的进程，不是仅注入业务服务。保存前用 `litegate -t -config config.yaml` 检查文件；保存后检查运行实例实际加载的配置。`-t` 不能证明后端连通或业务验签成功。

如果后端实例来自 Litemesh，也可以由文件维护路由，在本地 services 中写 `discovery: orders` 并使用 `service: orders-backend`，替代固定 proxy 地址。需要先配置发现客户端；发现源接入与 IDS 插件注册是两个独立前提。

### 3. 服务注册 Litemesh，由标签发布路由

假设注册服务名为 `orders`，在服务注册信息中附加以下 Tags（每行是一个 `key=value` 标签）：

```properties
litegate.http.routers.api.match.hosts=open.example.com
litegate.http.routers.api.match.path_prefix=/api
litegate.http.routers.api.service=orders-backend
litegate.http.routers.api.ids.provider=openapi-md5
litegate.http.routers.api.ids.failpolicy=deny
litegate.http.routers.api.ids.options.secret_env_prefix=OPENAPI_SECRET_
litegate.http.routers.api.ids.options.max_clock_skew=5m
litegate.http.routers.api.ids.options.max_body_size=1MiB
litegate.http.services.orders-backend.timeout=5s
```

`api` 是 Router 资源名称，`orders-backend` 是标签 Service 资源名称，实际后端是注册这些标签的 `orders` 服务。插件运行在 LiteGate 中，业务服务注册标签不会让网关自动获得插件代码。网关必须已接入 Litemesh Catalog，并具备对应入口与 HTTPS 证书配置。

标签使用 `ids.failpolicy`，YAML 使用 `fail_policy`；标签 Header 白名单使用 `ids.allowedheaders`，YAML 使用 `header_projection.allowed_headers`。`ids.options.<key>` 保留参数键大小写。`ids.operation` 是传给插件的 operation 参数，内核不实现 login/resolve 等业务模式。当前命名标签 IDS 属性没有 YAML runtime 的完整配置入口，不要推断所有 YAML 字段都能直接写成标签。

同一注册服务的路由标签应在各实例上一致。采用标签管理 API 时，不要再在文件声明相同 `/api` 期待逐字段合并：Hybrid 合并路由集合，不会自动组合“文件 IDS + 标签后端”。

### 4. 确认注册、绑定、初始化与实际执行

| 要确认什么 | 当前检查方式 | 不能据此推断什么 |
|---|---|---|
| 当前二进制有插件 | `litegate plugins list`、`litegate plugins inspect ids/openapi-md5` | 不代表运行进程已用该二进制，也不代表路由绑定 |
| Manifest 完整与兼容 | `litegate plugins doctor` | 不证明密钥、网络或验签正常 |
| 配置被接受并绑定 | 文件校验、加载日志、运行时最终路由；标签还要检查 Catalog 与标签校验 | 文件 -t 不验证未来动态标签 |
| 实例已创建 | Dashboard `/status/json` 的 `ids_providers`：provider、instantiated、health、inflight、circuit_open | 没实现 Health 时的 healthy 不证明外部依赖可用 |
| Evaluate 被调用 | 开启 metrics 后观察 `litegate_ids_evaluate_total{provider="openapi-md5"}` 增量 | `result="success"` 是调用没报错，正常返回 401 也计入 success |
| 业务规则真实生效 | 正确签名可达后端；错误、缺失、过期签名被拒绝且不访问后端 | 单次 HTTP 200 或 401 不能单独证明 IDS 执行 |

Dashboard 端点使用网关现有认证和监听设置；`ids_providers` 已有 JSON 数据，当前 HTML 尚没有专门展示这些状态的 IDS 面板。Health 可能是 pending、未实现或尚未实例化，必须结合 instantiated 和 Message 判断。慢调用、超时、panic、熔断与并发拒绝可用宿主日志和指标定位。

上线验收应发送一组可控请求，并同时核对调用计数、插件拒绝原因及后端访问记录。只有正确签名进入后端，缺失/错误/过期签名均被插件拒绝，才证明整条链路生效。关闭指标时不能依靠 Prometheus 判断执行。

建议后续补齐用户可见的闭环：插件参数 Schema 查询；运行面板显示插件与路由绑定、实例及健康状态；宿主单独统计 Forward/Respond 决策；以 trace_id 关联插件名称、拒绝原因和路由。以上为改进建议，当前未实现，不应写成现成功能。拒绝原因使用固定枚举，日志不要记录密钥、完整签名或原始 Body。


## 实现与注册

```go
type Provider struct {
    // 并发安全、可复用的 HTTP/Redis/DB 客户端和缓存
}

func (p *Provider) Evaluate(ctx context.Context, input plugin.IDSInput) (*plugin.IDSDecision, error) {
    token := first(input.Request.Header(input.Options.Get("token_header")))
    if token == "" {
        return &plugin.IDSDecision{
            Action: plugin.ActionRespond,
            Response: &plugin.DirectResponse{Status: http.StatusUnauthorized},
        }, nil
    }

    session, err := p.lookupSession(ctx, token)
    if err != nil { return nil, err }
    if session == nil {
        return &plugin.IDSDecision{Action: plugin.ActionRespond,
            Response: &plugin.DirectResponse{Status: http.StatusUnauthorized}}, nil
    }

    return &plugin.IDSDecision{
        Action: plugin.ActionForward,
        Headers: http.Header{
            "X-Tenant-Ref": {session.TenantRef},
            "X-Database-Ref": {session.DatabaseRef},
        },
        Discovery: &plugin.DiscoveryDecision{
            Selector: &plugin.DiscoverySelector{
                Match: map[string]string{"cluster": session.Cluster},
                Meta: map[string]string{"version": session.PreferredVersion},
            },
        },
        RateLimit: &plugin.RateLimitDecision{
            Key: session.SubjectRef,
            RequestsPerSecond: session.QPS,
        },
    }, nil
}

func init() {
    err := plugin.RegisterIDSProvider("saas-session", plugin.IDSProviderRegistration{
        Description: plugin.IDSProviderDescription{
            Summary: "SaaS session identity provider",
            Version: "1",
            Options: []plugin.IDSOptionDescriptor{
                {Name: "token_header", Type: plugin.IDSOptionString, Required: true},
                {Name: "policy_ref", Type: plugin.IDSOptionString},
            },
        },
        Validate: func(options plugin.IDSOptions) error {
            // 站点加载时执行，不创建 Provider 实例。
            return nil
        },
        Factory: func(deps *plugin.Dependencies) (plugin.IDSProvider, error) {
            return newProvider(deps.Logger, deps.Config), nil
        },
    })
    if err != nil { panic(err) }
}
```

若只做验证和 Header 注入，Forward 时省略 `Discovery`。插件包必须被最终网关二进制导入，通常在自定义入口中空导入：

```go
import _ "example.com/company/litegate-tenant-ids"
```

Provider 按名称作为单例复用。网关启动及配置更新时会初始化当前路由引用的 Provider；运行时也保留按需创建路径。重复注册会报错；确需覆盖时使用 `ReplaceIDSProvider`。

Provider 不会接收到 `*http.Request`。`IDSInput.Request` 只提供 Method、Scheme、Host、Path、Query、Header、RemoteAddress 和 `Body()`；Body 的物化上限由宿主固定为 8 MiB，Provider 不能自行扩大。Provider 配置的更小限额属于读后业务策略：宿主可能先读取到 8 MiB，再由 Provider 复查并拒绝。返回的 Header、Query、Body 均为副本，插件不能修改网关原始请求。路由 options 通过不可变的 `IDSOptions` 读取。

## 生命周期

注册信息中的 Description/Schema 与 Validate 在站点加载时使用，不会提前创建运行实例。Provider 由 Factory 创建为长生命周期单例（启动与配置更新时初始化已引用插件），并可选择实现：

```go
type IDSHealthChecker interface {
    Health(ctx context.Context) plugin.IDSHealthStatus
}

type IDSConfigReloader interface {
    ReloadConfig(ctx context.Context, cfg plugin.ConfigProvider, version uint64) error
}

type IDSCloser interface {
    Close(ctx context.Context) error
}
```

共享 `plugin-config.yaml` 发布新快照后，已实例化 Provider 会收到 ReloadConfig；没有实现该接口的 Provider 仍可通过长期持有的 `deps.Config` 实时读取。配置成功重载后，已不再被任何路由引用的 Provider 会退出运行表、清空治理状态并调用 `Close`；LiteGate 退出时也会关闭其余实例。若新配置初始化失败，旧 Provider 保持运行，不会被提前回收。

## 路由配置

`ids` 可配置在任意 Action 上，不限于 `proxy`。它会在 Action 执行前统一完成身份裁决、可信 Header/Query/Body 变更和动态限流；对 `respond`、`serve`、`template`、WebDAV 与第三方 Action 同样生效。只有 proxy 会消费 IDS 返回的 Selector/Meta 进行实例选路。

```yaml
action:
  type: proxy
  service_name: shared-saas-service
  ids:
    provider: saas-session
    fail_policy: deny
    selector_merge_policy: intersect
    runtime:
      timeout: 500ms
      slow_threshold: 100ms
      max_concurrency: 100
      circuit_breaker:
        enabled: true
        minimum_requests: 20
        failure_ratio: 0.5
        open_duration: 30s
    options:
      token_header: Authorization
      policy_ref: order-read
    header_projection:
      allowed_headers: [X-Tenant-Ref, X-Database-Ref]
```

- `provider` 必填，必须与注册名一致。
- `fail_policy` 默认 `deny`；`allow` 只处理插件 error，不改变插件明确返回的 Respond。
- `selector_merge_policy` 默认 `intersect`；IDS 与路由静态 Selector 同名不同值时拒绝。只有明确需要覆盖静态边界时才用 `override`。
- `options` 是热更新的路由参数，每次调用收到当前值的副本。
- `runtime` 完全由 LiteGate 宿主执行，第三方 Provider 不能覆盖。默认超时 500ms、慢调用阈值 100ms、最大并发 100；熔断默认启用。
- `allowed_headers` 是向下游注入 Header 的白名单。

Go Provider 的超时是协作式取消：LiteGate 会按时结束当前 HTTP 等待，但无法强杀忽略 Context 的 Go goroutine。此类调用会继续占用 Provider 的并发槽，直至真实返回；达到上限后新调用由宿主立即拒绝，避免无限堆积。连续失败或超时达到熔断条件后，宿主暂停调用该 Provider。宿主超时和 Provider panic 始终 fail-closed，即使配置了 `fail_policy: allow` 也不会转发；`allow` 只覆盖 Provider 正常返回的 error 和宿主熔断/并发拒绝。客户端取消不计入熔断成功或失败样本。

## 性能归因与监控

指标由 LiteGate 在 `Evaluate` 外部采集，不依赖第三方插件主动上报。Prometheus `/metrics` 提供：

- `litegate_ids_evaluate_duration_seconds{provider}`：宿主观测的执行耗时直方图，可计算 P50/P95/P99。
- `litegate_ids_evaluate_total{provider,result}`：`success`、`error`、`timeout`、`panic` 结果计数。
- `litegate_ids_inflight{provider}`：尚未真实退出的调用数，包含请求已经超时但插件仍卡住的调用。
- `litegate_ids_slow_total{provider}`：超过 `slow_threshold` 的调用数。
- `litegate_ids_circuit_state{provider}`：0 为关闭、2 为打开。
- `litegate_ids_rejected_total{provider,reason}`：因 `concurrency_limit` 或 `circuit_open` 被宿主拒绝的调用。

慢调用同时产生 `ids_slow_evaluation` 结构化日志，包含 Provider、耗时、阈值、超时、实际在途数和结果，不记录请求 Body、密钥或配置值。运行状态可通过内核的 `GetIDSRuntimeStatus()` 快照接入 Dashboard。

## 已知限制与后续优化

- Go Provider 超时后无法被强杀。若插件忽略 Context 并在 handler 返回后才调用 `Body()`，仍存在与 `net/http` 清理原始 Body 的窄竞态；彻底解决需要重新设计 Body 所有权或调用前物化策略。
- 为了对不响应 Context 的 Go 代码实施宿主超时，每次 Evaluate 当前会创建一个 goroutine 和结果 channel；极高 QPS 场景需要以 profile 数据决定是否引入执行池。
- WASM 当前为实验性：合成模块测试已覆盖宿主 ABI，但真实 Rust 编译产物尚未进入发布流水线的端到端测试。

以下审查项已经关闭，不再作为遗留：客户端取消不进入熔断分母；OpenAPI `max_body_size` 在加载期拒绝超过 8 MiB；完整 Body 读取不会被底层 Close 错误覆盖。

不同路径可选择不同 Provider，也可共用一个 Provider 并以 `options.operation` 区分。内核不建模 login、api、refresh、logout。

## 插件日志注入与可开关的调试日志

宿主通过 `plugin.Dependencies.Logger` 注入 `*zerolog.Logger`。当前 IDS Factory 收到的是网关系统 `log.Logger`，不是独立日志文件或自动带插件名的专属 Logger。插件应附加 `plugin` / `provider` 字段，不修改共享 Logger。路由 `log_level` 主要控制访问日志，不是自动控制插件 Evaluate 日志的开关。

调试期间可以在共享配置中打开插件自己的开关：

```yaml
# plugin.yaml
providers:
  openapi-md5:
    debug_log: true
```

测试结束改为 `false`。启用 `plugin_config.watch` 后，插件每次 Evaluate 从实时配置视图读取开关，便可随文件更新生效。内置 openapi-md5 已实现 `debug_log`；第三方插件需要自行实现，宿主不会自动识别它。

下面片段假设 Provider 已保存 Factory 注入的 `logger *zerolog.Logger` 和 `config plugin.ConfigProvider`。在 Evaluate 的开头添加：

```go
started := time.Now()
debugLog := false
if raw, ok := p.config.Scope("providers.openapi-md5").Lookup("debug_log"); ok {
    debugLog, _ = strconv.ParseBool(raw)
}
if debugLog && p.logger != nil {
    p.logger.Info().Str("plugin", "openapi-md5").
        Str("method", input.Request.Method()).
        Msg("ids_evaluate_started")
}
```

在最终决策处记录固定枚举，如 `decision=forward/respond`、`reason=valid_signature/invalid_signature/expired_timestamp`、`duration_ms`。添加宿主请求追踪关联时应核对当前 Trace ID 接口，不直接信任客户端提供的身份或追踪字段。初始化日志只能证明 Factory 执行；Evaluate 进入和最终决策日志才证明这次请求经过插件。

示例用受 debug_log 控制的 Info 事件，便于系统日志级别为 info 时可见；若选用 Debug 事件，还要将系统日志级别设为 debug。系统级别为 warn/error 时，Info 事件也会被过滤。关闭 debug_log 只关闭插件的详细请求日志，建议保留初始化失败、配置失败和依赖故障日志，以及宿主指标。

长期运行时，不要把 debug_log 只读一次存成普通 bool，否则文件更新不会生效。也不要为了插件调试直接把共享 Logger 改成 DebugLevel。保存 Logger 指针并在调用时附加字段，可以跟随当前宿主 Logger；长期保存一个派生 Logger 副本时则要考虑宿主日志级别更新的同步。

不要记录 Secret、原始 Token、完整签名或 Body。高流量时可在插件内实现采样，固定原因枚举便于统计。调试日志与“放行/拒绝”决策计数相互补充；日志开关不改变验签行为。

## 插件配置文件、环境变量与路由参数的分工

LiteGate 已支持独立共享插件配置文件，并把实时只读配置视图传给插件。文件名由主配置指定，不固定为 `plugin.yaml`：

```yaml
# config.yaml
plugin_config:
  path: plugin.yaml
  watch: true
```

```yaml
# plugin.yaml（使用 plugin-config.yaml 作为文件名也可以）
shared:
  redis:
    url: '${LITEGATE_REDIS_URL}'
providers:
  openapi-md5:
    secrets:
      orders: '${ORDERS_OPENAPI_SECRET}'
```

环境变量必须存在于 **LiteGate 进程环境** 中。宿主加载文件时展开 `${NAME}`；未设置且没有默认值会使加载失败。`${NAME:-default}` 仅在变量不存在时使用默认值；变量存在但为空时保留空值，不采用 shell 中“空值也回退”的语义。`${…}` 写在 YAML 单引号里也会展开，因为这是宿主解析后的处理。

嵌套映射被展开为点分键，如 `providers.openapi-md5.secrets.orders`。配置接受标量和映射，不接受 YAML 列表；标量最终作为字符串读取。命名空间 shared/providers 是组织约定，并非宿主强制或权限隔离，插件不会自动只看到自己的配置。

| 配置来源 | 谁处理 | 用途 |
|---|---|---|
| LiteGate 进程环境变量 | 部署环境注入；宿主或插件读取 | 密钥和部署地址 |
| plugin.yaml | 宿主展开环境变量并发布配置视图；插件解释字段 | 插件私有配置、跨路由共享密钥和共享基础设施 |
| Sites 的 ids.options | 宿主按路由传入；插件解释字段 | 选择策略、密钥引用、操作类型 |
| Litemesh 的 ids.options.<key> | 编译为同一种路由 options | 与 Sites 参数相同的职责 |

内置 openapi-md5 已实现 `secret_ref`，可以这样引用上面的密钥：

```yaml
site: open.example.com
/api:
  proxy: 127.0.0.1:8080
  ids:
    provider: openapi-md5
    options:
      secret_ref: orders
```

对应标签为 `litegate.http.routers.api.ids.options.secret_ref=orders`。内置 openapi-md5 通过 secret_ref 解析 plugin.yaml 密钥，并禁止同时设置 secret_env / secret_env_prefix。第三方插件仍需自行定义参数含义与优先级。

插件在 Factory 中通过 `deps.Config` 保存配置视图，也可在 Evaluate 中使用 `input.Config`。二者当前均由 `plugin.SharedConfig()` 提供。读取示例：

```go
ref := input.Options.Get("secret_ref")
if ref == "" {
    return nil, fmt.Errorf("secret_ref is required")
}
secret, ok := input.Config.Scope("providers.openapi-md5.secrets").Lookup(ref)
if !ok || secret == "" {
    return nil, fmt.Errorf("secret configuration is unavailable")
}
// 用 secret 验签；不要记录 secret。
```

推荐插件契约明确区分“路由选择密钥引用”和“共享配置保存密钥”；如同时支持路由参数和插件默认值，应在插件文档明确优先级，并在 Validate/Evaluate 中校验。

`watch: true` 监控文件变化。有效更新原子发布新快照，持有的 ConfigProvider 视图继续读取最新值；已实例化 IDS 插件若实现 `ReloadConfig` 会收到通知。直接在 Factory 里读取并保存的字符串不会自动更新；连接池、Redis/DB 客户端与插件缓存也要由插件重建或失效。环境变量本身不是监控对象，外部修改环境也不会更新现有进程环境。

首次加载失败会使网关启动失败；文件热更新失败保留上一份有效快照。日志 `Shared plugin configuration loaded`、`Plugin configuration reloaded` 带配置版本；`Plugin configuration reload rejected; keeping previous snapshot` 表示宿主拒绝更新。宿主接受新快照不等于插件重建资源成功：插件 ReloadConfig 失败会另记日志，插件旧资源可能继续使用。这些状态需要分别检查。

## 动态配置、密钥和缓存

跨 Provider 共享且需要运行时更新的配置，可使用独立的插件配置文件：

```yaml
# config.yaml
plugin_config:
  path: plugin-config.yaml
  watch: true
```

```yaml
# plugin-config.yaml
shared:
  redis:
    url: ${LITEGATE_REDIS_URL}
  rabbitmq:
    url: ${LITEGATE_RABBITMQ_URL}
providers:
  saas-session:
    key_prefix: "ids:session:"
```

LiteGate 监听文件并在完整解析成功后原子发布新快照；格式错误或缺少环境变量时继续保留旧版本。Provider 可以长期保存配置视图，并在每次使用时读取最新值：

共享插件 YAML 当前只接受标量和映射；列表会被拒绝。需要列表时可使用逗号分隔字符串或 JSON 字符串，并由插件自行解析。

```go
cfg := deps.Config.Scope("providers.saas-session")
prefix, ok := cfg.Lookup("key_prefix")
version := cfg.Version()
```

共享基础设施可以从 `deps.Config.Scope("shared")` 读取。YAML 适合组织共享和私有命名空间；`${ENV_VAR}` 适合注入 Secret。配置读取是实时的，但 Redis、RabbitMQ 或数据库连接是否以及如何重建由插件负责。

Provider 工厂不接收主配置，所以修改路由 options 不要求重启。options 应放策略或引用，而不是明文秘密：

```yaml
options:
  tenant_source: primary
  redis_ref: tenant-session-prod
```

插件用引用向自己的配置中心解析地址和凭据。连接池保存在 Provider 单例中；引用变化时可按引用或配置指纹懒加载新客户端。

推荐查询顺序是进程内短缓存 → Redis → 租户系统 → 回填。缓存键必须包含所有影响校验和选路的维度；不存在的数据使用较短负缓存；登录、刷新、注销时主动失效。

### 缓存与并发回源（官方工具包 idskit）

Provider 是**长生命周期单例、被并发调用**（见[生命周期](#生命周期)），所以缓存和回源合并都应放在 Provider 结构体里，`Evaluate` 进来先查缓存、未命中再回源。冷缓存下最容易踩的坑是**惊群**：同一身份的成百上千个请求同时未命中、同时打后端。

为了避免开发者重复手写复杂的 SingleFlight、Context 隔离与负缓存逻辑，LiteGate 提供了官方运行时电池包 **`pkg/plugin/idskit`**（可选加速器），将高并发回源的最佳实践全部封装在泛型 `idskit.IdentityLoader[V]` 中。

#### 推荐做法：使用 `idskit.IdentityLoader`

```go
import (
    "context"
    "errors"
    "net/http"
    "time"

    "github.com/jamesleeon/LiteGate/pkg/plugin"
    "github.com/jamesleeon/LiteGate/pkg/plugin/idskit"
)

type provider struct {
    loader *idskit.IdentityLoader[*Claims]
}

func newProvider(deps *plugin.Dependencies) *provider {
    return &provider{
        loader: idskit.NewIdentityLoader(func(ctx context.Context, token string) (*Claims, error) {
            // 纯粹的后端回源逻辑（已自动切断 caller 取消链路并带有 FetchTimeout 保护）
            // 这里的 token 是原始凭据，已与内部内存缓存的哈希指纹解耦
            claims, err := queryAuthBackend(ctx, token)
            if err != nil {
                return nil, err // 基础设施错误：绝不进负缓存，且自动触发 Forget 供下次重试
            }
            if claims == nil {
                return nil, idskit.ErrNotFound // 业务未找到/凭据非法：自动触发短命负缓存
            }
            return claims, nil
        }, idskit.LoaderOptions{
            KeyFunc:      idskit.TokenFingerprint,  // 自动将长 Token 映射为 128 位安全指纹，内存中绝不存明文长 Key
            TTL:          30 * time.Second,        // 正向缓存生命周期
            NegativeTTL:  2 * time.Second,         // 负缓存生命周期（防穿透）
            FetchTimeout: 800 * time.Millisecond,  // 单次回源上限
            MaxEntries:   10000,                  // LRU 容量上限（防 OOM）
        }),
    }
}

func (p *provider) Evaluate(ctx context.Context, in plugin.IDSInput) (*plugin.IDSDecision, error) {
    token := idskit.FirstHeader(in.Request, "Authorization")
    if token == "" {
        return idskit.RespondUnauthorized(), nil
    }

    // 查缓存/自动 SingleFlight 并发回源（传入原始 token，内部自动通过 KeyFunc 计算指纹进行缓存和收敛）
    claims, err := p.loader.Get(ctx, token)
    if err != nil {
        if errors.Is(err, idskit.ErrNotFound) {
            return idskit.RespondUnauthorized("Invalid token"), nil
        }
        return nil, err // 基础设施故障返回 error
    }

    return idskit.ForwardWithHeaders(http.Header{
        "X-Tenant-Ref":   {claims.TenantRef},
        "X-Database-Ref": {claims.DatabaseRef},
    }), nil
}

// 当发生用户注销/刷新事件时，主动失效：
// p.loader.Invalidate(token) // 内部原子删除缓存 + 标记在途任务失效 + Forget SingleFlight，彻底防旧值复活
```

---

#### 新手容易写错的关键点与 `idskit` 的底层防护机制

如果选择手写底层 SingleFlight 与 Cache，必须严格遵守以下 6 点（`idskit` 已在内部自动兜底）：

- **① 缓存键取身份指纹并加进程随机密钥**：
  - 缓存键必须是身份指纹，不能直接用全量请求或长原始 Token 作为 Key。
  - `idskit.Fingerprint` 采用长度前缀编码与 128 位截断 HMAC-SHA-256（带进程随机密钥），保证组件边界严格保留且彻底防预计算碰撞。
- **② 必须用 `DoChan` + `select ctx.Done()`，不要用 `sf.Do`**：
  - `sf.Do` 会**忽略调用者的 ctx**：leader 那次回源一旦卡住，所有等待的请求全被拖死，直到宿主超时。`DoChan` 才能在 caller 超时/取消时先脱身。
- **③ 回源闭包使用 `context.WithoutCancel` 隔离超时**：
  - 切勿把某个 caller 的 ctx 直接传给回源闭包——它一取消会连带取消其他共享者的回源。`idskit` 使用 `context.WithTimeout(context.WithoutCancel(callerCtx), timeout)`，既切断取消链，又完整保留链路 trace/baggage 上下文。
- **④ 严格的负缓存边界**：
  - 鉴权失败（`idskit.ErrNotFound`）才进短 TTL 负缓存，防止黑客用假 Token 打穿后端。
  - **网络抖动、DB 超时等基础设施错误绝不进负缓存**，并立即调用 `sf.Forget(key)`，确保下一个请求可以立即重试。
- **⑤ 失效防复活（原子在途状态锁）**：
  - 注销/刷新时调用 `cache.Remove(key)` + `sf.Forget(key)`。`idskit` 在同一互斥锁下管理在途状态（In-flight State），回源结束写回缓存前原子校验失效标志，彻底杜绝慢回源落后完成导致的“旧值复活”。
- **⑥ 并发安全与容量淘汰**：
  - 内存缓存必须具备容量上限（`golang-lru/v2`），避免使用无淘汰机制的 `sync.Map` 导致内存暴涨（OOM）。

> Selector 应表达真实的硬隔离维度。高基数 Selector 会增加逐请求实例过滤成本；对于仍启用查询缓存的自定义发现类型，还应评估缓存基数。LiteGate 内置的实时发现类型（LiteMesh、Consul、K8s 等）不会按每个 Selector 值长期缓存过滤结果。

## 实现约束

- Evaluate 会被并发调用，共享字段必须线程安全；冷缓存回源用 singleflight 合并，见[缓存与并发回源（官方工具包 idskit）](#缓存与并发回源官方工具包-idskit)。
- req 只在当前调用有效；读取 Body 后恢复 Body。
- 业务拒绝返回 Respond，基础设施故障返回 error。
- 外部访问继承 ctx 并配置超时。
- 不记录原始 token、密码或 Secret。
- Selector 是硬边界；Meta 只是边界内可回退的偏好。
- RateLimit Key 是不透明业务主体，QPS 必须大于 0；超限请求在 Action 执行前返回 429（proxy 因而不会进入服务发现）。
- 不回传客户端伪造的内部 Header，必须生成新值并配置投影白名单。


## 可选的事件通知与状态同步

IDS 不强制使用缓存，也不强制订阅 notify。例如仅做 MD5 验签的 Provider 可以只实现 `Evaluate`，无需通知接口或 `shared.notify` 配置。只有实现 `NotifySubscriber` 并声明非空 subject 的实例才建立订阅。

插件为了性能可以把租户、凭据等缓存在进程内。缓存什么、怎么删由插件自己决定，宿主不做假设；宿主提供的是**可选的通知投递**：Provider 实现可选接口 `plugin.NotifySubscriber`，声明自己关心的 subject，外部系统（如租户系统）状态变化后向这个 subject 发一个信号，宿主就把它投递给该 Provider。

```go
func (p *Provider) NotifySubjects() []string { return []string{"notify.tenant"} }

func (p *Provider) HandleNotify(ctx context.Context, n plugin.Notification) error {
	if n.Resync { // 订阅刚生效、断线重连或之前处理失败：可能漏了消息
		p.tenants.InvalidateAll()
		return nil
	}
	var signal struct {
		TenantID string `json:"tenant_id"`
	}
	if json.Unmarshal(n.Data, &signal) == nil && signal.TenantID != "" {
		p.tenants.Invalidate(signal.TenantID)
	}
	return nil
}
```

声明 subject 的 Provider 实例创建时宿主才订阅，退役或关闭前退订；同一实例的回调串行执行。消息不持久化、不重投，宿主改为保证 `Resync`：订阅生效后、断线重连或丢消息后、回调返回错误或 panic 之后。`idskit.IdentityLoader.InvalidateAll` 同时隔离在途回源，旧结果不会写回缓存。租户停用后 `Evaluate` 仍须返回明确的拒绝，缓存失效只负责让它尽快读到新状态。配置方式、发布方法和 Redis 等共享缓存的处理见 [插件订阅通知](user/09-advanced/event-notification.md#9-插件订阅通知插件自己定义-subject)。


`Resync` 表示可能漏过通知，需要按插件自身语义重新校准状态，不等同于“必须清缓存”。有缓存可以失效缓存，持有快照可以重新读取配置源，无本地状态则可直接成功返回。回调必须尊重 context 的取消和期限；宿主等待旧回调退出后才启用新订阅，保证跨连接切换也串行。
