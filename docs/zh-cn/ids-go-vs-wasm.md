# IDS Provider 选型：Go vs WASM

> WASM 支持当前为实验性、默认不编译。宿主使用合成 WASM 模块测试，但 Rust 示例产物尚未进入端到端发布验证；稳定交付场景应优先选择 Go Provider。

> 定位见 [IDS 概览](ids-overview.md)，契约见 [IDS Provider 架构](ids-architecture-v2.md)。

IDS Provider 有两种实现层。它们不是"强弱"关系，而是**覆盖不同场景**。选错会导致要么放弃安全隔离，要么在沙箱里撞上做不到的 I/O。

> **编译前提**：Go Provider 随网关默认编译；WASM 支持（wazero 运行时，约 +4MB）默认**不**编入二进制，需用 `-tags wasmids` 构建（`go build -tags wasmids ./cmd/litegate`，或 `make all-wasm`）。未带 tag 时 `ids_wasm.enabled: true` 会被忽略并打 warn。详见 [WASM 开发指南](ids-wasm-plugin-guide.md)。

## 一张表决定用哪个

| 能力 / 诉求 | Go Provider | WASM Provider |
|---|---|---|
| 查 Redis / DB / 租户系统 session | ✅ | ❌ **宿主不提供 I/O** |
| 调用外部 HTTP 服务 | ✅ | ❌ |
| 自包含计算：签名校验、JWT 验签、静态策略 | ✅ | ✅ |
| Header 变换、限流 Key 推导、路由决策 | ✅ | ✅ |
| 读共享插件配置（`config_get`） | ✅ | ✅ |
| 多语言（Rust、TinyGo…） | ❌ 仅 Go | ✅ |
| 不重编译 / 不重发网关即可热部署 | ❌ 需编入二进制并重启 | ✅ 放置产物即热加载 |
| 沙箱隔离（内存 / 超时 / 无逃逸） | ❌ 全信任 | ✅ |
| 不可信第三方作者分发 | ⚠️ 风险高 | ✅ |
| 每请求开销 | 最低 | 有序列化 + 实例化 + 调用成本 |

## 最关键的一条边界：WASM 不做 I/O

WASM 宿主只向模块暴露三个 host function（见 `internal/wasmids/host.go`）：

- `config_version` —— 读共享配置版本号
- `config_get` —— 按 `config_prefixes` 白名单读共享配置值
- `log` —— 结构化日志

**没有 HTTP、没有 Redis、没有数据库、没有任何网络或存储访问。**

这意味着架构文档里的**主力用例**——"读 JWT → 查 Redis session → 注入数据库上下文"、"读 App ID → 查租户系统取 Secret 校验签名"——**无法在 WASM 内完成**，因为它们都需要外部查询。不要在 WASM Provider 里期望访问 session 存储。

WASM 能干的是**计算密集、自包含**的决策：
- 用共享配置里的公钥/密钥做**签名或 JWT 验签**（密钥经 `config_get` 注入，验签在沙箱内算）。
- 基于请求内容的**静态策略**判定。
- **Header 变换**、**限流 Key 推导**、基于规则的 **Selector/Meta 选路**。

## 决策指引

**用 Go，如果**：决策需要查 session、查租户系统、访问任何外部存储或服务——即绝大多数有状态 SaaS 路径。

**用 WASM，如果**至少命中一条：
- 需要**多语言**（团队用 Rust 写）。
- 需要**免网关重建的热部署**（运营态频繁调整策略，不想每次重编译 + 重启网关）。
- 需要给**不可信/第三方作者**安全分发插件（沙箱限额 + 无逃逸）。
- 决策是**纯计算 + 配置**，不碰 I/O。

**两者可共存**：不同路由各选各的 Provider。常见组合是——有状态主路径用 Go，验签/策略这类纯计算切片用 WASM 交给业务团队热迭代。

## 如果确实需要"WASM + I/O"

这是一个明确的路线图取舍，不是现成能力。要让 WASM 也能查 session，需要给宿主新增 `kv_get`/`http_fetch` 之类的 host function，同时会重新引入：

- 沙箱逃逸面（模块可发起外部调用）；
- 超时与并发治理（外部调用的取消、限流、连接复用）；
- 凭据边界（谁持有 Redis 密码）。

在评估清楚这些代价前，**推荐保持"WASM 仅计算、I/O 走 Go"**，这是更诚实也更省运维的边界。

## 两层共享同一契约

无论 Go 还是 WASM，最终都产出同一个 `IDSDecision`（Forward/Respond + Headers/Route/RateLimit/Response），内核以完全相同的方式做白名单投影、Selector 硬边界、动态限流和 fail_policy。切换实现层**不改变路由配置的语义**。

## 下一步

- Go 实现 → [IDS Provider 插件开发与配置](ids-provider-plugin-guide.md)
- WASM 实现 → [IDS WASM 插件开发指南](ids-wasm-plugin-guide.md)
- 端到端场景 → [IDS 配方](ids-recipes.md)
