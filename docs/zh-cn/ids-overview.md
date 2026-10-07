# IDS 是什么，为什么需要它

> 本文是 IDS 的入口与定位文档。契约细节见 [IDS Provider 架构](ids-architecture-v2.md)，Go/WASM 选型见 [Go vs WASM 选型](ids-go-vs-wasm.md)，可抄的场景见 [IDS 配方](ids-recipes.md)。

## 一句话

**IDS 是 LiteGate 在“路由已匹配、Action 尚未执行”之间开放的一道业务身份与选路决策接缝。** 内核不内置 `tenant_id`、`app_id`、JWT 或登录语义；由谁、准不准进、请求如何继续，全部交给插件根据原始 HTTP 请求和你的业务系统决定。

```text
客户端 → 路由匹配 → IDS Provider.Evaluate ──┬─ Forward：注入可信 Header / 限流后继续 Action（proxy 还可动态选路）
                                            ├─ Respond：直接回客户端（401/403/…）
                                            └─ error：按 fail_policy 处理
        → 动态限流 → Action（proxy：服务发现与 Selector/Meta 过滤 → 下游）
```

## 心智模型

内核只提供一个类型化契约，并对决策的每一部分**强制执行语义**：

| 决策字段 | 含义 | 内核如何对待 |
|---|---|---|
| `Action: Forward/Respond` | 放行或直接响应 | Respond 直接短路，不访问下游 |
| `Headers` | 注入下游的可信身份头 | 按 `allowed_headers` 白名单投影，敏感头兜底拦截 |
| `Route.Selector` | 硬隔离边界，如 `{cluster: a}` | 只允许进入 A 集群，**绝不降级到 B** |
| `Route.Meta` | 边界内软偏好，如 `{version: v2}` | v2 在则用 v2，不在则回退同边界默认池 |
| `RateLimit{Key, QPS}` | 按业务主体的动态限额 | Forward 后、Action 前执行，超限直接 429 |

Provider 是**按名懒加载的并发单例**；路由 `options` 每次调用传入当前值的副本，因此站点配置或服务标签热更新后**无需重启**。

## IDS 和 middleware 有什么区别

这是最常被问到的问题。标准答案：

> **Middleware 是一条"处理流水线"**——一串通用、有序、可组合的请求变换器（auth、cors、ratelimit、headers、strip_prefix），回答"这个请求该怎么被加工"。
> **IDS 是一个“决策点”**——路由匹配后、Action 执行前的单次业务身份裁决，回答“你是谁、准不准进、这次请求应如何继续”；proxy Action 还可据此选择后端实例。

结构性差异：

| 维度 | Middleware | IDS |
|---|---|---|
| 形态 | 链式、多个、有序组合 | 单点、每路由恰好一个 |
| 位置 | 通用请求管线中 | 路由匹配后、Action 执行前的边界 |
| 输出 | 不透明地改写 req/resp | 类型化决策，内核可理解并强制 |
| **能否选后端** | **不能** | **能**（Selector 硬边界 + Meta 软偏好） |
| 信任模型 | 较宽松 | 剥离客户端伪造的内部头，只投影重新生成且白名单内的值 |
| 典型职责 | 跨切面加工 | 身份裁决 + 多租户选路 + 按主体限流 |

**决定性差异只有一句：IDS 的输出会喂给服务发现，middleware 不能选后端。** 认证 + 多租户选路 + 按主体配额，在一个业务中立的契约里一次完成——这是 IDS 存在的理由，也是它无法用一个普通中间件替代的原因。

## 为什么不把它做成一个 middleware

1. **落点固定**：必须在"匹配之后、发现之前"运行，且要产出结构化决策，而不是一个通用的 `ServeHTTP` 包装。
2. **决策可被内核推理**：Forward/Respond + Selector/Meta/RateLimit/Headers 是类型化的，内核据此做白名单投影、把 Selector 当硬隔离边界、对敏感头兜底。中间件只是不透明改请求，内核无从判断它做了什么。
3. **信任边界**：IDS 先剥离客户端传入的内部身份头（`X-Lito-Verified`、`X-Request-Source` 等），只放行插件重新生成且在白名单内的头。
4. **单一裁决**：一条路由恰好一个 IDS，而中间件是一条链。

## 对标其他网关

| 方案 | 形态 | 能否选后端 | 说明 |
|---|---|---|---|
| **LiteGate IDS** | 进程内（Go）或进程内沙箱（WASM） | ✅ | 授权 + 选路 + 按主体限流一体，业务中立 |
| Envoy `ext_authz` | 进程外 RPC | ❌ | 多一跳延迟与运维，只能 allow/deny，选不了后端集群 |
| Nginx `auth_request` | 子请求 | ❌ | 只有放行/拒绝，无类型化决策与选路 |
| Kong plugins | 中间件式 | ❌ | 本质是请求加工链，非专门的选路裁决 |

**头条卖点**：别的网关的授权钩子都停在 allow/deny，IDS 的决策**直接驱动服务发现**。

## 什么时候该用 IDS

适合：
- 多租户 SaaS：读身份 → 查租户系统/Redis → 注入数据库上下文 → 按租户切库/切集群。
- 开放平台：读 App ID → 取 Secret → 校验签名 → 注入通用头。
- 灰度/多版本：同集群内按业务规则选 v2，缺失时安全回退。
- 按租户/App/设备的动态限流，而非按整条路由的静态限流。

不适合（用普通 middleware 即可）：
- 与业务身份无关的通用加工：CORS、压缩、静态限流、统一改头。
- 标准 JWT/API-Key 鉴权且无需选路——直接用内置鉴权中间件。

## 两种实现层

IDS Provider 有两种写法，覆盖不同场景，详见 [Go vs WASM 选型](ids-go-vs-wasm.md)：

- **Go Provider**：可信、可访问 Redis/DB/HTTP、性能最高。所有需要外部查询的主力路径。
- **WASM Provider**：沙箱隔离、多语言（Rust 等）、免网关重建即可热部署。**仅做自包含计算**（验签、验 JWT、静态策略、头/限流 Key 变换），宿主不提供 I/O。

## 下一步

- 理解契约与安全边界 → [IDS Provider 架构](ids-architecture-v2.md)
- 决定用 Go 还是 WASM → [Go vs WASM 选型](ids-go-vs-wasm.md)
- 抄一个端到端场景 → [IDS 配方](ids-recipes.md)
- 写 Go Provider → [IDS Provider 插件开发与配置](ids-provider-plugin-guide.md)
- 写 WASM Provider → [IDS WASM 插件开发指南](ids-wasm-plugin-guide.md)
