# IDS 配方

> 端到端可抄的场景。契约见 [IDS Provider 架构](ids-architecture-v2.md)，选型见 [Go vs WASM 选型](ids-go-vs-wasm.md)。
> 以下 Provider 逻辑均写在 `Evaluate` 内，注册与工程结构见 [Go 开发指南](ids-provider-plugin-guide.md) / [WASM 开发指南](ids-wasm-plugin-guide.md)。

每个配方给出：**目标 → 路由配置 → Provider 决策要点**。

---

## 配方 1 · Session 查找并注入数据库上下文（Go）

**目标**：读 JWT/Token → 查 Redis session → 放行并向下游注入租户与库上下文。

```yaml
routes:
  - name: protected-api
    match: { path_prefix: /api }
    action:
      type: proxy
      service_name: shared-saas-service
      ids:
        provider: saas-session
        fail_policy: deny
        options:
          token_header: Authorization
          session_ref: tenant-session-prod
        header_projection:
          allowed_headers: [X-Tenant-Ref, X-Database-Ref]
```

**决策要点**：

```go
token := req.Header.Get(options["token_header"])
if token == "" {
    return &plugin.IDSDecision{Action: plugin.ActionRespond,
        Response: &plugin.DirectResponse{Status: http.StatusUnauthorized}}, nil
}
session, err := p.lookup(ctx, options["session_ref"], token) // 进程内缓存 → Redis → 回填
if err != nil { return nil, err }                            // 基础设施故障 → error
if session == nil {
    return &plugin.IDSDecision{Action: plugin.ActionRespond,
        Response: &plugin.DirectResponse{Status: http.StatusUnauthorized}}, nil
}
return &plugin.IDSDecision{
    Action:  plugin.ActionForward,
    Headers: http.Header{"X-Tenant-Ref": {session.TenantRef}, "X-Database-Ref": {session.DatabaseRef}},
}, nil
```

- 业务拒绝用 `Respond`，基础设施故障用 `error`（由 `fail_policy` 决定放行还是 503）。
- 注入头必须由插件**重新生成**；客户端伪造的同名头已被内核剥离。
- Redis/DB 客户端是 Provider 单例里并发安全的复用连接，密码走[共享插件配置](ids-provider-plugin-guide.md#动态配置密钥和缓存)而非 `options`。

---

## 配方 2 · 开放平台签名校验（Go 或 WASM）

**目标**：读 App ID → 取 Secret → 校验请求签名 → 注入通用身份头。

纯验签是**自包含计算**，可用 WASM（Secret 经 `config_get` 注入，验签在沙箱内算）；若 Secret 需实时从租户系统拉取则用 Go。

```yaml
    action:
      type: proxy
      service_name: open-platform
      ids:
        provider: openapi-sign     # WASM 或 Go 均可，同名契约
        fail_policy: deny
        options: { app_header: X-App-Id, sign_header: X-Sign }
```

**决策要点**：读 `app_id` → `deps.Config.Scope("providers.openapi-sign").Lookup(app_id)` 取 Secret → 用 Secret 重算签名与 `X-Sign` 比对 → 通过则 `Forward` 注入 `X-App-Verified`，否则 `Respond 401`。

> 已有内置示例 [openapi-md5-ids-plugin](openapi-md5-ids-plugin.md) 可直接参考。

---

## 配方 3 · 按租户切库 / 切集群（Selector 硬边界）

**目标**：租户 A 的流量**只能**进入 A 集群，绝不降级到别的集群。

`Selector` 是硬隔离边界。返回 `{cluster: a}` 后，服务发现只在带该标签的实例中选，找不到就失败，**不会**落到其他集群。

```go
return &plugin.IDSDecision{
    Action: plugin.ActionForward,
    Route:  &plugin.RouteDecision{Selector: map[string]string{"cluster": session.Cluster}},
}, nil
```

下游实例需带对应发现标签（如 `cluster=a`）。用于物理隔离的独立集群/独立库租户。

---

## 配方 4 · 灰度多版本（Meta 软偏好）

**目标**：同一集群内优先命中 v2，v2 未部署时安全回退到该集群默认实例。

`Meta` 是 Selector 边界内的软偏好：`{version: v2}` 存在则用 v2，不存在则回退到**同一 Selector 下未声明 route meta 的默认池**，不会落入其他版本或其他 Selector。

```go
return &plugin.IDSDecision{
    Action: plugin.ActionForward,
    Route: &plugin.RouteDecision{
        Selector: map[string]string{"cluster": session.Cluster}, // 硬边界
        Meta:     map[string]string{"version": "v2"},            // 软偏好
    },
}, nil
```

因此集群内可有三个默认实例 + 一个灰度实例；忘记部署灰度版本时仍安全回到集群默认实例。灰度比例、AB 分流规则由 Provider 自行决定（如按租户尾号）。

---

## 配方 5 · 按业务主体动态限流（RateLimit）

**目标**：按"租户/App/设备"等业务主体限额，而非按整条路由。内核不理解该主体是什么。

```go
return &plugin.IDSDecision{
    Action:    plugin.ActionForward,
    RateLimit: &plugin.RateLimitDecision{Key: session.SubjectRef, RequestsPerSecond: session.QPS},
}, nil
```

- 执行顺序：**IDS → 动态限流 → Selector/Meta 服务发现 → Proxy**。超限直接 429，不查实例、不访问下游。
- `Key` 是不透明业务主体，`QPS > 0`；进入本地缓存/Redis/日志前会被哈希。同一 Provider + 路由 + Key 共享一个 token bucket。
- 与路由静态 `action.rate_limit` 并存：静态限流保护整条路由、在 IDS **之前**执行；IDS 动态限流负责按主体的额度。

---

## 配方 6 · WASM 纯计算 Provider（Rust）

**目标**：用 Rust 写一个自包含验签/校验 Provider，放置产物即热加载，不重建网关。

manifest（放在 IDS WASM 目录）：

```yaml
name: rust-ids
kind: ids
abi: litegate.ids/v1
module: rust-ids.wasm
request:
  headers: [Authorization]     # 仅按需暴露请求字段，最小化输入面
  query: false
  body: false
config_prefixes: [shared.identity, providers.rust-ids]  # config_get 白名单
limits: { timeout_ms: 100, memory_pages: 512, max_input_bytes: 1048576, max_output_bytes: 262144 }
```

Provider 导出 `alloc` + `evaluate`，输入输出为 linear memory 上的 JSON（`IDSDecision`）。完整骨架见 `examples/wasm-ids-rust/` 与 [WASM 开发指南](ids-wasm-plugin-guide.md)。

**约束提醒**：WASM 内**无法**查 Redis/DB/HTTP——只能读 `config_get` 注入的值做计算。需要外部查询请改用 Go（见[选型](ids-go-vs-wasm.md)）。

---

## Header 投影规则（所有配方通用）

内核对 Forward 注入的 Header 做安全投影：

- **保留头被丢弃**：`Authorization`、`Cookie`、`X-Forwarded-*`、`X-Real-IP`、`X-Lito-Verified`、`X-Request-Source`。
- **敏感名需白名单**：Header 名含 `tenant-id`、`tenant-code`、`db-name`、`database-name`、`db-cluster`、`shard-id`、`cluster-id`，或含独立 `sid` 段时，**必须**列入 `allowed_headers`，否则返回 403。
- 非敏感、非保留的头正常投影。
- 放行后内核自动附加 `X-Lito-Verified: true` 与 `X-Request-Source: trusted-router`，下游据此判断请求已过网关裁决。

> 命名建议：用 `X-Tenant-Ref` / `X-Database-Ref` 这类"引用"命名可避开敏感片段；确需注入敏感名时务必显式 `allowed_headers`。

---

## 配置三种写法速查

同一 IDS 配置可用路由 YAML、服务标签或[共享插件配置](ids-provider-plugin-guide.md#动态配置密钥和缓存)表达。服务标签写法：

```text
litegate.orders.ids.provider=saas-session
litegate.orders.ids.fail_policy=deny
litegate.orders.ids.options.token_header=Authorization
litegate.orders.ids.allowed_headers=X-Tenant-Ref,X-Database-Ref
```

- `options` 是热更新路由参数，改动不重启，放**策略/引用**而非明文密钥。
- 跨 Provider 的密钥/连接目标放共享插件配置文件（`${ENV}` 注入 Secret，原子快照，仅接受标量与映射）。
