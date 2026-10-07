# IDS Provider 架构

> 新读者建议先看 [IDS 概览](ids-overview.md)（定位、IDS vs middleware、对标友商），再读本文了解契约细节。选型见 [Go vs WASM](ids-go-vs-wasm.md)，可抄场景见 [IDS 配方](ids-recipes.md)。

IDS 是 LiteGate 在“路由已匹配、请求尚未发往下游”之间开放的业务决策接缝。它不内置 `tenant_id`、`app_id`、JWT 或登录语义；这些都由插件根据原始 HTTP 请求和业务系统决定。

该接缝位于所有 Action 之前，并非 proxy 专属：直接响应、静态内容、模板、WebDAV 和第三方 Action 都能被 IDS 保护。Selector/Meta 的动态实例选路只在 proxy Action 中有意义。

## 数据流

```text
客户端 → 路由匹配 → IDS Provider.Evaluate
                     ├─ Forward：继续代理（Header、可选 Selector/Meta）
                     ├─ Respond：直接响应客户端
                     └─ error：按 fail_policy 处理
       → 服务发现过滤 → 下游 Proxy
```

内核只有一种 IDS 模型，不再区分 `openapi`、`verify`、`issue`、`refresh`、`revoke` 或 `gate`。登录、API 校验、刷新和注销只是不同路径选择不同 Provider，或选择同一 Provider 并传入不同 `options`。

## 公共契约

```go
type IDSProvider interface {
    Evaluate(ctx context.Context, input IDSInput) (*IDSDecision, error)
}

type IDSDecision struct {
    Action   IDSAction
    Route    *RouteDecision
    RateLimit *RateLimitDecision
    Headers  http.Header
    Response *DirectResponse
}

type RouteDecision struct {
    Selector map[string]string
    Meta     map[string]string
}
```

`req` 是当前原始请求的指针，Provider 可读取 method、URL、Header、Cookie、Body、TLS 和 context。读取 Body 后应恢复它；不要跨请求保存 `req`。

- `ActionForward`：继续代理。`Route == nil` 时走路由原本的默认下游。
- `ActionRespond`：直接返回 `Response`，不访问下游。
- `Headers`：只在 Forward 时注入；内核按 `header_projection.allowed_headers` 做白名单投影。
- `RateLimit`：Forward 后、服务发现和 Proxy 前执行的动态限流；为空表示不启用 IDS 动态限流。
- `error` 表示 Provider 系统故障。业务拒绝应返回 Respond，例如 401/403。
- Provider 必须显式返回 Action，空决策属于插件错误。

## Selector 与 Meta

`Selector` 是硬隔离边界。例如 `{cluster: a}` 只允许进入 A 集群，绝不会降级到 B。

`Meta` 是边界内的可选偏好，例如 `{version: v2}`：v2 存在时使用 v2；不存在时回退到同一 Selector 下未声明 route meta 的默认池；不会落入其他可选版本或其他 Selector。因此集群内可有三个默认实例和一个灰度实例，忘记部署灰度版本时仍安全回到该集群默认实例。

## 配置与热更新

```yaml
routes:
  - name: protected-api
    match:
      path_prefix: /api
    action:
      type: proxy
      service_name: shared-saas-service
      ids:
        provider: saas-session
        fail_policy: deny
        selector_merge_policy: intersect # 默认；与路由静态 Selector 冲突时拒绝
        options:
          token_header: Authorization
          policy_ref: order-read
        header_projection:
          allowed_headers: [X-Tenant-Ref, X-Database-Ref]
```

服务标签写法：

```text
litegate.orders.ids.provider=saas-session
litegate.orders.ids.fail_policy=deny
litegate.orders.ids.selector_merge_policy=intersect
litegate.orders.ids.options.token_header=Authorization
litegate.orders.ids.options.policy_ref=order-read
litegate.orders.ids.allowed_headers=X-Tenant-Ref,X-Database-Ref
```

新架构没有全局 `ids_providers`。Provider 工厂只接收稳定的网关依赖；路由 `options` 每次 Evaluate 都会传入，因此站点配置或服务标签热更新后无需重启。

`options` 适合非敏感策略值或密钥引用，不建议直接放 Redis 密码、数据库口令。Provider 应通过自己的配置中心、Secret Manager、环境注入或租户系统解析引用，并在单例内部复用并发安全的 Redis/HTTP/DB 客户端。连接目标动态变化时，可按配置指纹维护客户端池并淘汰旧连接。

`selector_merge_policy` 默认为 `intersect`：IDS 可以补充新的 Selector 维度，但若覆盖路由已有 key 且值不同，请求会被拒绝。只有明确允许 IDS 改写静态选路边界时才配置 `override`。

## SaaS 用法

- 开放平台：读 App ID，查询租户系统或缓存取得 Secret，校验签名，注入通用 Header，走默认下游。
- 独立数据库、共享应用：读 JWT，查 Redis session，注入数据库上下文，并返回租户 Selector。
- 独立集群：按租户返回硬 Selector；灰度时附加 Meta。
- 登录、刷新、注销：各路径选择相应 Provider。Provider 自行调用业务系统和读写 Redis；内核无需理解 token 生命周期。

缓存属于 Provider 实现。可按“进程内缓存 → Redis → 租户系统 → 回填”执行，避免每次远程访问；插件负责 TTL、负缓存、主动失效、超时和故障策略。

## 动态限流

IDS 可以在识别业务主体后返回通用限流决策，内核不理解该主体是租户、App、用户还是设备：

```go
RateLimit: &plugin.RateLimitDecision{
    Key:               "tenant-ref-42",
    RequestsPerSecond: 100,
}
```

执行顺序是 `IDS → 动态限流 → Selector/Meta 服务发现 → Proxy`。超限时直接返回 429，不查询实例也不访问下游。Key 在进入本地限流缓存、Redis 和日志前会被哈希；同一个 Provider、路由和 Key 共享一个 token bucket。路由原有的静态 `action.rate_limit` 仍然存在，它保护整条路由并在 IDS 之前执行；IDS RateLimit 则负责租户或 App 等动态主体额度。

## 安全边界

- 默认 `fail_policy: deny`；只有明确接受绕过风险时才使用 `allow`。
- 不信任客户端传入的内部身份 Header，只投影插件重新生成且在白名单中的值。
- Provider 是跨请求共享的并发单例，不能把请求状态写入普通字段。
- 外部调用必须有超时；读取请求体必须限流并恢复。
- 用结构化 Selector/Meta 选路，不允许插件直接返回任意上游 URL。
