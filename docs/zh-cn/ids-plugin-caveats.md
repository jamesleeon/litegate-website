# IDS 插件开发注意事项与避坑指南

> 本文总结了在 LiteGate 中开发自定义 IDS (Identity & Decision Service) 插件时的**核心设计约束、常见 Bug、安全隐患与性能陷阱**。  
> 相关文档：[IDS 概览](ids-overview.md) · [IDS Provider 架构](ids-architecture-v2.md) · [IDS 开发指南](ids-provider-plugin-guide.md) · [IDS 配方](ids-recipes.md)。

---

## 🧭 核心心智模型与架构约束

在编写 IDS 插件前，必须时刻牢记以下 3 条宿主底层规则：

1. **单例并发执行**：Provider 实例在网关内部是**全局跨请求共享的长生命周期单例**。`Evaluate` 方法会被海量 Goroutine **高并发调用**。
2. **决策驱动服务发现**：IDS 不是单纯的拦截器，它的产物（`IDSDecision`）会被宿主直接用于**微服务实例过滤（Selector/Meta）、动态限流与可信 Header 投影**。
3. **宿主强管控与熔断**：宿主层对 Provider 实施并发控制（默认并发上限 100）、执行超时控制（默认 500ms）及基于失败率的熔断机制。

---

## ⚠️ 六大致命陷阱（Footguns）与防御策略

### 🚨 陷阱 1：在 Provider 结构体上缓存请求状态（并发数据竞争）

* **错误现象**：在并发测试或生产高流量下，A 租户的请求偶然获得了 B 租户的身份，甚至出现数据交叉污染或 Panic。
* **原因分析**：Provider 结构体是全局单例，如果在结构体上定义非并发安全的变量来暂存当前请求的数据，会导致多个请求互相覆盖。

❌ **致命错误示范**：
```go
type MyIDSProvider struct {
    logger       *zerolog.Logger
    currentAppID string // ❌ 严重 Bug：每个请求互相覆盖！
    requestToken string // ❌ 严重 Bug：数据交叉泄露！
}

func (p *MyIDSProvider) Evaluate(ctx context.Context, input plugin.IDSInput) (*plugin.IDSDecision, error) {
    p.currentAppID = input.Request.Header("X-App-Id")[0]
    p.requestToken = input.Request.Header("Authorization")[0]
    // 并发时这里读取到的 currentAppID 已经被另一个 Goroutine 篡改！
    tenant, _ := p.db.FindTenant(p.currentAppID)
    ...
}
```

✅ **正确写法**：
Provider 结构体**仅持有全局只读依赖或并发安全客户端池**。所有与单个请求相关的状态必须是 `Evaluate` 方法内部的**局部变量**：
```go
type MyIDSProvider struct {
    logger *zerolog.Logger       // 全局共享只读
    rdb    redis.UniversalClient // 并发安全客户端
}

func (p *MyIDSProvider) Evaluate(ctx context.Context, input plugin.IDSInput) (*plugin.IDSDecision, error) {
    // 局部变量，栈上分配或独立生命周期，完全并发安全
    appID := first(input.Request.Header("X-App-Id"))
    token := first(input.Request.Header("Authorization"))
    ...
}
```

---

### 🚨 陷阱 2：外部 I/O 忽略 Context 导致 Goroutine 泄漏与并发槽耗尽

* **错误现象**：下游鉴权系统或 Redis 响应变慢时，网关瞬间大量抛出 `IDS provider concurrency limit reached (100)`，整条路由所有请求全部被拒。
* **原因分析**：
  - LiteGate 宿主在 `internal/middleware/ids_guard.go` 中通过原子计数器限制 Provider 的最大在途并发（`max_concurrency`，默认 100）。
  - 网关虽然有协作超时控制（默认 500ms），但 **Go 运行时无法强杀正在阻塞的网络 I/O**。
  - 如果插件在请求外部 HTTP / Redis / MySQL 时**没有传递 `ctx`**，即使网关已超时返回，后台 Goroutine 依然在死等，导致在途并发计数器（`inflight`）无法递减，迅速占满 100 个并发槽，引发全路由拒绝服务！

❌ **致命错误示范**：
```go
// ❌ 错误：使用默认客户端或 context.Background()，忽略了传入的 ctx
resp, err := http.Get("http://auth-service/verify?token=" + token)
val, err := p.rdb.Get(context.Background(), "session:"+token).Result()
```

✅ **正确写法**：
所有外部网络交互与数据库操作**必须继承传入的 `ctx`**：
```go
// ✅ 正确：当网关超时触发时，HTTP 请求和 Redis 读写会立即中止并释放资源
req, _ := http.NewRequestWithContext(ctx, http.MethodGet, "http://auth-service/verify", nil)
resp, err := p.httpClient.Do(req)

val, err := p.rdb.Get(ctx, "session:"+token).Result()
```

---

### 🚨 陷阱 3：混淆“业务鉴权拒绝”与“系统错误”（Respond vs. Error）

* **错误现象**：用户配置了 `fail_policy: allow`（希望在鉴权微服务宕机时优雅降级放行），结果发现**黑客伪造的错误密码、过期 Token、非法签名也全被网关放行通过**！
* **原因分析**：
  - `ActionRespond`：代表**业务判定明确不允许通过**（密码错误、Token 过期、签名非法）。此时应由插件构造 401/403 等 HTTP 响应直接拦截。
  - `error`：代表**网关与插件的基础设施故障**（Redis 崩溃、DB 超时、网络断开）。
  - `fail_policy: allow` 的设计意图是：**仅当发生基础设施 `error` 且允许容灾时放行，绝不改变明确返回的 `ActionRespond` 拒绝！** 如果插件把业务鉴权失败当作 `error` 返回，网关在 `allow` 策略下会误将其作为系统故障并放行！

❌ **致命错误示范**：
```go
if !isValidSignature(appID, sign) {
    // ❌ 错误：把业务拒绝当成 error 返回！在 fail_policy: allow 时会被直接放行造成严重安全漏洞！
    return nil, fmt.Errorf("invalid signature")
}
```

✅ **正确写法**：
```go
if !isValidSignature(appID, sign) {
    // ✅ 正确：业务拒绝必须返回 ActionRespond
    return &plugin.IDSDecision{
        Action: plugin.ActionRespond,
        Response: &plugin.DirectResponse{
            Status: http.StatusUnauthorized,
            Headers: http.Header{"Content-Type": []string{"application/json"}},
            Body:   []byte(`{"code":"invalid_signature","message":"Signature verification failed"}`),
        },
    }, nil
}

// 仅当底层基础设施异常（如 Redis 挂掉）时才返回 error
tenantInfo, err := p.lookupTenantFromRedis(ctx, appID)
if err != nil {
    return nil, fmt.Errorf("redis lookup failed: %w", err)
}
```

---

### 🚨 陷阱 4：多租户 Secret 查找“静默降级”导致验签越权穿透

* **错误现象**：多租户开放平台中，某个未授权或已被禁用的 `app_id` 发起请求，只要使用全局默认测试密钥签名，居然通过了网关校验！
* **原因分析**：
  插件在实现动态多租户秘钥查找时，如果根据 `app_id` 在配置中心中未命中密钥，代码没有直接中断拒绝，而是“好心”地回退去读取默认的环境变量密钥（如 `LITEGATE_OPENAPI_MD5_SECRET`）。一旦生产环境存在全局默认环境变量，就会导致所有非法 `app_id` 均可利用该默认密钥通过鉴权。

✅ **防御准则**：
- 如果路由显式声明了租户前缀（如 `secret_ref_prefix`），当租户不存在时**必须立即判定失败**，严禁跨层回退到全局默认密钥。
- 密钥查找失败的报错信息必须明确指出是哪个租户/AppID 缺失，避免误导为环境变量缺失。

---

### 🚨 陷阱 5：敏感 Header 注入未在 `allowed_headers` 白名单登记（被 403 拦截）

* **错误现象**：插件代码中注入了 `Headers.Set("X-Tenant-Id", "1001")`，且返回了 `ActionForward`，但客户端收到的却是 `403 Forbidden: IDS sensitive header is not allowlisted: X-Tenant-Id`。
* **原因分析**：
  LiteGate 内核具有严格的[边缘零信任防护机制](ids-architecture-v2.md)。网关在执行 IDS 前会自动剥离客户端伪造的内部头；而在 IDS 执行完成后，**对注入下游的敏感 Header（包含 `tenant-id`、`tenant-code`、`db-name`、`shard-id`、`cluster-id`、`sid` 等关键字）强制实施白名单校验**。未在 YAML 中显式声明的敏感头会被网关直接拦截。

✅ **正确配置规范**：
在站点 YAML 路由中，必须使用 `header_projection.allowed_headers` 显式放行插件注入的敏感头：
```yaml
routes:
  - name: saas-api
    match:
      path_prefix: /api
    action:
      type: proxy
      service_name: core-service
      ids:
        provider: my-saas-auth
        header_projection:
          allowed_headers:
            - X-Tenant-Id
            - X-Database-Ref
            - X-Shard-Id
```

---

### 🚨 陷阱 6：无负缓存（Negative Cache）引发的缓存击穿与雪崩

* **错误现象**：外网黑客恶意用大量随机生成的虚假 Token / AppID 扫描网关，导致后端鉴权微服务或核心 DB 的 CPU 瞬间被拉满。
* **原因分析**：
  插件内部虽然做了 Redis / 内存缓存，但只缓存了**合法存在的用户**。对于“不存在的用户/非法 Token”，每次请求都会穿透缓存直接查询后端 DB。

✅ **推荐防御策略（首推官方 `idskit.IdentityLoader`）**：
建议直接使用官方运行时包 `pkg/plugin/idskit`，其泛型 `IdentityLoader` 已内置带进程随机密钥的 128 位 HMAC-SHA-256 指纹、SingleFlight 并发合并、`WithoutCancel` 超时隔离、`ErrNotFound` 自动负缓存，以及基于原子在途状态锁的失效防复活：

```go
loader := idskit.NewIdentityLoader(func(ctx context.Context, rawToken string) (*TenantInfo, error) {
    tenant, err := p.queryBackend(ctx, rawToken) // 收到原始凭据，可直接查库
    if err != nil { return nil, err } // 基础设施错误不进负缓存
    if tenant == nil { return nil, idskit.ErrNotFound } // 自动写入 2s 负缓存
    return tenant, nil
}, idskit.LoaderOptions{
    KeyFunc:     idskit.TokenFingerprint, // 缓存/并发键用指纹，内存绝不存明文长 Token
    TTL:         30 * time.Second,
    NegativeTTL: 2 * time.Second,
})
// 调用传原始凭据：loader.Get(ctx, rawToken)
// 失效同样传原始凭据（须与 Get 一致，KeyFunc 才能算出同一键）：loader.Invalidate(rawToken)
```

如需手写底层缓存，请确保对非法/不存在的身份使用短 TTL（1~3s）写入负标记，且仅对业务 `NotFound` 缓存，网络故障与 DB 错误绝不缓存！

---

## ⚡ 性能与高可用最佳实践

### 1. 谨慎使用 `input.Request.Body()`
* `input.Request.Body()` 会在内存中物化请求体（宿主硬上限为 8 MiB，超限返回 `IDSBodyTooLargeError`）。
* 虽然宿主会在读取后还原请求体流，但在高并发、大文件上传场景下频繁物化 Body 会产生极大的 GC 压力。
* **准则**：
  - 文件上传、音视频推流等大流量路由，**切勿使用需要读取 Body 的 IDS 插件**，应仅基于 Header / Query / TLS 客户端证书进行身份验证。
  - 对于 JSON API 路由，必须在插件配置中约束 `max_body_size`（如 `64KiB`）。

### 2. 动态限流（`RateLimitDecision`）的 Key 设计
* 当在 `IDSDecision` 中返回 `RateLimit` 时，`Key` 必须是**业务主体**（如 `tenant:1001` 或 `app:order-sync`）。
* **准则**：
  - 避免将高基数、无界且动态变化的字符串（如携带随机数的 URL 或全量原始 Token）作为限流 Key，否则会撑爆网关本地限流 Token Bucket 缓存。
  - `RequestsPerSecond` 必须严格大于 0（不可为负数、NaN 或 Inf）。

### 3. 正确使用 `Selector`（硬边界）与 `Meta`（软偏好）
* **`Route.Selector`（硬边界）**：用于多租户分库分表、机房物理隔离（如 `{"cluster": "tenant-a-dedicated"}`）。**如果目标集群无可用实例，网关将直接返回 503，绝不降级到其他集群**。
* **`Route.Meta`（软偏好）**：用于灰度/金丝雀发布（如 `{"version": "v2"}`）。**如果 `v2` 实例全部挂掉或未部署，网关会自动优雅回退到该 Selector 下的默认池实例**，保障业务高可用。

---

## 📋 生产级 IDS Provider 检查清单（Checklist）

在将自定义 IDS 插件部署至生产环境前，请逐一核对以下项目：

- [ ] **推荐使用 `idskit`**：优先使用 `pkg/plugin/idskit`，自动免除 SingleFlight、Context 隔离与负缓存等并发陷阱。
- [ ] **并发安全**：结构体无请求级状态变量，无未受保护的 Map 读写；本地缓存具备 LRU 容量上限（防 OOM）。
- [ ] **Context 传递与隔离**：所有 HTTP / Redis / gRPC / SQL 调用均响应了 `ctx`；并发回源使用 `context.WithoutCancel` 隔离单 caller 取消。
- [ ] **语义区分**：业务拒绝使用 `idskit.RespondUnauthorized` / `ActionRespond`，基础设施异常才返回 `error`。
- [ ] **配置与密钥**：未在 `options` 中硬编码明文密码；多租户查找有明确的隔离边界且不胡乱降级。
- [ ] **Header 白名单**：所有注入下游的敏感 Header 均在路由配置的 `allowed_headers` 中声明。
- [ ] **防穿透设计**：对高频非法请求配置了本地短 TTL 负缓存。
- [ ] **大流量防范**：非必要不读 Body；必须读取时配置了合理的 `max_body_size`。
- [ ] **优雅关闭**：如果插件持有常驻 Goroutine 或数据库连接池，实现了 `plugin.IDSCloser` 接口。
