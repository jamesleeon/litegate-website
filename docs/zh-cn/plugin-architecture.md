# LiteGate 插件体系架构（编译期注册表）

结构化 Middleware、LB 反馈、Ingress Filter 及新增六类扩展入口的当前接口与配置，请参见 [插件扩展入口 V2](https://github.com/jamesleeon/LiteGate/blob/master/docs/zh-cn/plugin-seams-v2.md)。

> 本文描述 LiteGate **已落地**的插件体系：一套 **Caddy 风格的编译期注册表（compile-time registry）**，让开发者（内部团队、企业用户、第三方独立仓库）在 **不 fork 核心代码** 的前提下扩展网关能力。第三方通过公共契约包 [pkg/plugin](https://github.com/jamesleeon/LiteGate/blob/master/pkg/plugin) + 入口 [pkg/litegate](https://github.com/jamesleeon/LiteGate/blob/master/pkg/litegate) 接入。
>
> 本文讲**原理与设计取舍**；想直接动手写插件，请看 [plugin-authoring-guide.md](plugin-authoring-guide.md)（含最小骨架、踩坑清单与测试方法）。

标准二进制默认编入 NATS Action、OpenAPI MD5 IDS 与 forward proxy 入口插件，
它们沿用公共 API 注册与 Manifest 机制，需显式配置才启用，可作为插件开发参考。
>
> 设计基线：**编译期注册表**，不依赖 Go `plugin` 动态加载（Windows 不可用、Linux 脆弱，已明确排除）。

---

## 一、目标与边界

LiteGate 早期用硬编码 `switch` 分发 action / 选负载均衡算法，加一种新能力就得改核心。现已演进为统一的注册表模型，消除了这个差距：**内置功能与插件走同一条注册路径**。

### 1.1 目标

1. 内置功能（proxy/serve/template…）与第三方插件 **走完全相同的注册路径**（Caddy 的关键原则：自己也吃狗粮）。
2. 新增能力 = 写一个 Go 包 + 一个 `init()`，核心代码零改动。
3. 企业可在 **私有仓库** 维护私有插件，编译定制二进制，不与上游冲突。
4. 零运行时性能损失（网关硬指标）。

### 1.2 非目标（明确排除）

* ❌ 运行时动态加载 `.so`（Go `plugin` 包：Windows 不支持，Linux 要求依赖版本完全一致，脆弱）。
* ❌ 进程外插件（go-plugin / gRPC）—— 每调用一次 RPC 开销，不做。
* ❌ 通用 WASM / 解释器（Yaegi）插件—— 通用请求链仍采用编译期 Go 插件。
* ✅ IDS 是例外：安全决策已有受限的 `litegate.ids/v1` WASM ABI，可按构建标签启用；它不是通用 Action/Middleware 运行时。

---

## 二、设计原则

### 2.1 接口只在“接缝”处抽，且要少

> 这套体系最常见的翻车点是**过度抽象**。Caddy 整个生态的核心也只靠 **几个生命周期接口 + 每个挂载点 1 个行为接口**。

判断是否该抽接口的唯一标准：**“这里现在/将来真的会有第二个实现，且需要在运行时按配置切换吗？”**

* ✅ 该抽：Action、Middleware、KV Provider、LoadBalancer —— 这正是插件的意义。
* ❌ 别抽：`*proxy.PoolManager`、`*Executor`、各类 cache —— 单实现，为它造接口是纯负担。
* ✅ 本就该多实现：`discovery.Client`、`discovery.LoadBalancer`。

遵循 Go 习惯：**“接口应被发现，而非被设计”**、**“接口定义在消费方、要小”**。

### 2.2 生命周期用“可选接口 + 类型断言”

生命周期接口全部 **可选**，插件需要才实现，核心用类型断言探测。简单插件只实现一个 `Execute` 方法即可，不会被一堆空 `Provision(){return nil}` 噪音淹没。

### 2.3 依赖用具体 struct 注入，不接口化

插件需要的宿主能力打包进一个具体的 `Dependencies` struct 传入，而不是为每个依赖抽接口。该 struct 刻意保持最小化以避免 import 环（见 §四）。

---

## 三、接缝清单（均已实现）

| # | 接缝 | 行为接口 | 注册函数 | 实现位置 |
|---|---|---|---|---|
| 1 | **Action**（终结型：产出响应） | `Handler` | `plugin.RegisterAction` | [pkg/plugin/register.go](https://github.com/jamesleeon/LiteGate/blob/master/pkg/plugin/register.go) |
| 2 | **Middleware**（穿透型：链上加工） | `MiddlewareHandler` | `plugin.RegisterMiddleware` | [pkg/plugin/middleware.go](https://github.com/jamesleeon/LiteGate/blob/master/pkg/plugin/middleware.go) |
| 3 | **KV 内容 Provider** | `KVProvider` | `plugin.RegisterKVProvider` | [pkg/plugin/kv.go](https://github.com/jamesleeon/LiteGate/blob/master/pkg/plugin/kv.go) |
| 4 | **LoadBalancer** | `LoadBalancer` | `plugin.RegisterLoadBalancer` | [pkg/plugin/loadbalancer.go](https://github.com/jamesleeon/LiteGate/blob/master/pkg/plugin/loadbalancer.go) |
| 5 | **DNS Provider**（证书 DNS-01 + DDNS） | `CertDNSProviderV2` / `DDNSProvider` | `plugin.RegisterDNSProviderV2`（推荐）/ V1 兼容注册 | [pkg/plugin/dns.go](https://github.com/jamesleeon/LiteGate/blob/master/pkg/plugin/dns.go) · [internal/cert/interface.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/cert/interface.go) |
| 6 | **IDS**（请求治理 Provider） | `IDSProvider` | `plugin.RegisterIDSProvider` / `ReplaceIDSProvider` | [pkg/plugin/ids.go](https://github.com/jamesleeon/LiteGate/blob/master/pkg/plugin/ids.go) |
| 7 | **Discovery Provider**（服务与 Endpoint 发现） | `DiscoveryProvider` | `plugin.RegisterDiscoveryProvider` | [pkg/plugin/discovery.go](https://github.com/jamesleeon/LiteGate/blob/master/pkg/plugin/discovery.go) |

> 前四个是原始核心接缝；**DNS Provider**、**IDS** 与 **Discovery Provider** 是后续按同一范式扩展的领域接缝，各自有专门的开发指南（见 [dns-provider-plugin-guide.md](dns-provider-plugin-guide.md) / [ids-provider-plugin-guide.md](ids-provider-plugin-guide.md) / [discovery-provider-plugin-guide.md](discovery-provider-plugin-guide.md)）。

**核心接缝仅 2 个新增行为接口（`Handler`、`MiddlewareHandler`）+ 3 个可选生命周期接口。** 其余全是具体类型与注册表 map；领域接缝（DNS / IDS）则各自抽出最小能力接口，同样落入公共注册表统一分发。

---

## 四、两层契约：内部 + 公共门面

插件契约分两层，**第三方只接触公共层，内部团队走内部层**，两者经由同一张注册表分发：

| 层 | 包 | 谁用 | 暴露什么 |
|---|---|---|---|
| **内部契约** | [internal/plugin/contract.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/plugin/contract.go) + 各 `internal/*/registry.go` | 内置功能 + 第一方 in-tree 代码 | 直接引用 `loader.Action`、`action.Context`、`discovery.ServiceEndpoint` 等内部重型类型（高能但与实现耦合） |
| **公共门面** | [pkg/plugin](https://github.com/jamesleeon/LiteGate/blob/master/pkg/plugin) | **第三方独立仓库** | 只暴露**窄接口/窄 DTO**：`Context`、`ActionConfig`、`SiteConfig`、`Endpoint`、`DiscoveryClient`；不泄漏任何内部类型 |

> [!IMPORTANT]
> **为什么要公共门面层？** 行为接口的方法签名引用了内部重型类型（`Handler.Execute` 引用 `loader.Action`/`action.Context`、`MiddlewareHandler.Wrap` 引用 `loader.SiteConfig`、`LoadBalancer.Next` 引用 `discovery.ServiceEndpoint`）。若把这些类型直接公开，就等于把内部实现冻结成对外 API。所以 `pkg/plugin` 用**窄接口**重新表达契约，内部用**适配器**（`pluginAdapter` / `middlewareAdapter` / `loadBalancerAdapter` / `actionConfigAdapter` / `siteConfigAdapter` / `endpointAdapter` / `discoveryAdapter`）把内部具体类型桥接到窄接口。核心因此能自由演进而不破坏第三方插件。

### 4.0 公共依赖 `pkg/plugin.Dependencies`

```go
// 第三方插件工厂收到的注入能力 —— 全是窄接口，不含内部具体类型。
type Dependencies struct {
	Logger    *zerolog.Logger
	Discovery DiscoveryClient // 窄只读视图：GetEndpoints(ctx, name, ns, tag) ([]string, error)
	Config    ConfigProvider   // 原子、热更新的共享插件配置视图
}

// --- 可选运行生命周期接口（Action / Middleware / LoadBalancer 按需实现）---
type Provisioner  interface { Provision(deps *Dependencies) error } // 首次实例化时的全局初始化
type Validator    interface { Validate(cfg ActionConfig) error }    // V1 Action 兼容校验
type CleanerUpper interface { Cleanup() error }                     // 优雅释放资源
```

> 内部层的 `plugin.Dependencies` 仍含 `Loader / Discovery / Logger`（供内置/第一方使用）；桥接时只把其中第三方需要的能力收窄后透传给公共 `Dependencies`（如把 `discovery.Client` 包成 `DiscoveryClient`）。内部层保持最小化以避免 `plugin` 反向依赖 `proxy`/`middleware` 造成 import 环。

### 4.1 Action 行为接口

```go
// internal/action/registry.go
type Handler interface {
	Execute(ctx *Context, action *loader.Action) error
}

// HandlerFunc 适配器：让普通函数也能当 Handler（内置 action 即靠它接入，见 §六）
type HandlerFunc func(ctx *Context, action *loader.Action) error
```

### 4.2 Middleware 行为接口与 V2 描述符

`Wrap` 是唯一运行行为接口；通过 `RegisterMiddleware` 在构造实例前声明精确阶段、顺序、作用域、配置校验和激活条件：

```go
// pkg/plugin/middleware.go
type MiddlewareHandler interface {
    Wrap(next http.Handler, site SiteConfig, name string, config MiddlewareConfig) http.Handler
}
type MiddlewareRegistration struct {
    Factory MiddlewareFactory
    Descriptor MiddlewareDescriptor
    Validate func(MiddlewareConfig) error // 必选，纯加载期校验
    Active func(MiddlewareConfig) bool // 可选，不构造运行实例
}

```

V2 的请求执行顺序固定为：`Preflight → RequestTransform → Security → TrafficControl → Authentication → PostAuth → Response → Upstream → Action`。同阶段按 `Descriptor.Order` 从小到大执行，相同 Order 保留配置声明顺序。所有公共插件必须显式声明 Descriptor，不保留旧阶段映射。

`PhaseUpstream + ExecutionHandler` 会紧贴 Action 执行；`ExecutionUpstream` 目前用于 LiteGate 内置 retry/circuit-breaker 编译器，不代表向第三方暴露底层 Transport。

### 4.3 IDS 是跨 Action 治理阶段

`action.ids` 在 Router 的 Authentication 阶段统一执行，适用于 `proxy`、`respond`、`serve`、`webdav`、`template` 和第三方 Action。proxy 仍保留直接调用时的兼容兜底，但通过不可由客户端 Header 伪造的私有 Context 标记保证每个请求只评估一次。IDS 产生的 selector/meta 由 proxy 消费；直接拒绝、Header 投影和请求级限流对所有 Action 生效。

---

## 五、注册机制

各接缝复用同一范式：注册表 + 并发保护 + 名称规范化 + 内置类型保护 + `init()` 自注册。Action V2 还把纯配置校验与运行工厂分开：

```go
plugin.RegisterAction("llm_proxy", plugin.ActionRegistration{
	Factory: func(deps *plugin.Dependencies) plugin.Handler { return newHandler(deps) },
	Validate: validateRouteConfig, // 加载期调用，不创建临时 handler
})
```

要点（与早期提案的裸 map 不同，这些都是已落地的健壮性保证）：

* **返回 `error` 而非静默覆盖**：空名 / nil 工厂 / 重名 / 覆盖内置类型一律拒绝。
* **内置类型不可覆盖**：`RegisterAction("proxy", …)` 会失败，插件必须取不冲突的名字。
* **自动打通 loader**：loader 会查询公共注册表，立刻认得新类型，无需改核心校验。
* **Middleware / LoadBalancer / KV 同构**：都有自己的名称保护与对应 `Deregister*`，方便测试隔离；Middleware V2 另外提供描述符、纯校验与激活钩子。

第三方插件包通过 `init()` 调用**公共**注册函数自注册，用户在**自己的 `main`** 里空导入即触发：

```go
// 第三方仓库 github.com/acme/litegate-llm
import "github.com/jamesleeon/LiteGate/pkg/plugin"

func init() {
	_ = plugin.RegisterAction("llm_proxy", plugin.ActionRegistration{
		Factory: func(deps *plugin.Dependencies) plugin.Handler {
			return &handler{logger: deps.Logger}
		},
		Validate: validateRouteConfig,
	})
}

// 用户自己的 main.go
import (
	"github.com/jamesleeon/LiteGate/pkg/litegate"
	_ "github.com/acme/litegate-llm" // 空导入触发注册
)
func main() { _ = litegate.Run() }
```

> 公共 Action / Middleware / LoadBalancer / KV 注册函数各自校验后落入 `pkg/plugin` 注册表；内部解析器查不到内置项时查询公共注册表，并用窄适配器包装后分发。公共名称查找统一忽略首尾空白和大小写。

---

## 六、分发与生命周期（运行时）

### 6.1 内置与插件经同一张注册表分发

内置 handler（`ExecuteProxy` 等）深度依赖 `*Executor` 的私有状态（`poolManager`、`tmplCache`、`balancers`…），**没有**被改写成独立 struct，而是用 `HandlerFunc` 闭包适配进注册表（[executor.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/action/executor.go) 的 `lazyInitHandlers`）：

```go
builtins["proxy"]   = HandlerFunc(e.ExecuteProxy)
builtins["respond"] = HandlerFunc(ExecuteRespond)
// …status / template / webdav / list / …
```

> **有意的不对等**：内置走“宿主内部捷径”（直接摸 `Executor` 私有状态），第三方走“公共契约”（只能用 `Dependencies` 暴露的能力）。两者经由**同一张注册表**分发。这是性能与封装的有意权衡，需在开发者文档中明确界定。

### 6.2 懒加载与并发安全

`lazyInitHandlers` 用 `sync.Once` 保证内置 + 已注册插件只构建一次。对于在 `lazyInit` 之后才注册、或首个请求才命中的插件类型，`Execute` 走 `singleflight` 双检懒加载（[executor.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/action/executor.go)）：并发请求只会创建并 `Provision` 一个实例，重复创建的实例会被立即 `Cleanup` 回收，避免泄露。

### 6.3 全链路 panic 兜底（fail-safe）

每个外部交互点都包了 `recover`，插件 panic 不会拖垮进程：

* **工厂 / `Provision` / `Validate`** panic → 转为 error，该插件被跳过或该次配置校验失败。
* **配置加载期** `ActionValidatorImpl.ValidateAction`（[registry.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/action/registry.go)）优先调用 V2 纯校验函数，并对插件校验做 panic 恢复，**fail-closed**：坏配置在启动/重载期就被拦下；V1 临时实例校验后也会立即 Cleanup。
* **`Execute`** 对**插件** handler 单独包 recover（内置 handler 不额外包，由全局 `CoreHandler` 兜底成 500）。

### 6.4 生命周期全景

```
程序启动
  └─ 各插件包 init() → RegisterAction / RegisterMiddleware / RegisterLoadBalancer / RegisterKVProvider
配置加载 / 热重载
  ├─ ActionRegistration.Validate(ActionConfig)
  └─ MiddlewareRegistration.Validate(config)          [均 fail-closed]
首次命中该类型（懒加载，singleflight 去重）
  └─ factory(deps) → Provisioner.Provision()         [一次，全局初始化，拿不到路由配置]
每个请求
  └─ Handler.Execute() / Wrap 后的中间件链           [高并发，类型级共享实例]
关机 / lifecycle 清理
  └─ Executor.CleanupPlugins() → CleanerUpper.Cleanup()
```

> 优雅重载会把旧 Action/LB/Middleware 实例放入 15 秒延迟回收队列；应用关机时会停止定时器并同步排空队列，避免裸 goroutine 因进程退出而漏掉 Cleanup。旧式 Action `Validator` 仍兼容，但宿主会在验证后 Cleanup 临时实例；新插件应使用无副作用的 `ActionRegistration.Validate`。

---

## 七、配置承载

插件的私有配置走 `Action.Extra`（YAML `yaml:",inline"`，见 [loader/types.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/loader/types.go)），不污染核心 `Action` struct：

```yaml
routes:
  - name: "ai"
    match: { path_prefix: "/v1/chat" }
    action:
      type: "llm_proxy"            # ← 注册的插件名
      provider: "claude"           # ↓ 以下未命名字段自动进入 Action.Extra
      model: "claude-opus-4-8"
      budget_tokens_per_min: 100000
```

内部层用 `a.Extra["model"].(string)` 读取；**第三方层**则拿到 `ActionConfig` 窄视图（`actionConfigAdapter` 包装 `Action.Extra`），用 `cfg.Type()` / `cfg.Get(key)` / `cfg.Decode(&struct)` 读取——`Decode` 按 json tag 解码，省去逐字段类型断言。**注意**：YAML 数字进来是 `int` / `float64`。Middleware 的配置则走 `Wrap` 入参的 `config plugin.MiddlewareConfig`（非 Extra）。完整示例见 [plugin-authoring-guide.md](plugin-authoring-guide.md)。

---

## 八、已知限制与未来路径

| 项 | 现状 | 说明 / 路径 |
|---|---|---|
| **第三方独立仓库插件** | ✅ 已开放 | 公共契约在 [pkg/plugin](https://github.com/jamesleeon/LiteGate/blob/master/pkg/plugin)、入口在 [pkg/litegate](https://github.com/jamesleeon/LiteGate/blob/master/pkg/litegate)。第三方在独立仓库 `import` 并通过「用户拥有 main」编译（见下条）。in-tree 老方式仍可用于第一方插件，但不再推荐。 |
| **`litegate build --with`** | ✅ 已实现 | 支持重复的 `package[@version][=local_dir]`、通用 module replace、核心版本锁定与漂移检测、本地模块边界校验、跨平台环境透传、race/debug/trimpath 以及诊断工作区保留。依赖本地 Go 工具链；远程模块需要 Go 代理或私有仓库认证。 |
| **Middleware V2** | ✅ 已支持 | 八阶段 Descriptor、加载期 Validate、Active、AllowMultiple、Scope；V1 Stage/Priority 自动兼容。 |
| **Middleware / LoadBalancer 生命周期钩子** | ✅ 已支持 | `Provisioner` / `CleanerUpper` 由宿主调度；延迟回收可在关机时排空。 |
| **公共 KV Provider** | ✅ 已支持 | 独立仓库可用 `RegisterKVProvider` 为 serve/template KV 模式提供内容监听。 |
| **IDS 跨 Action** | ✅ 已支持 | Authentication 阶段统一保护所有内置与第三方 Action；无引用 Provider 会被退休并 Close。 |
| **DNS Provider V2** | ✅ 已支持 | 宿主推导 DNS-01 FQDN/TXT Value；加载期纯校验和能力声明；工厂/运行 panic 隔离；证书与 DDNS 实例关闭。V1 保持兼容。 |
| **Discovery Provider** | ✅ 已支持 | 独立仓库可提供服务列表和 Endpoint；支持同类型多实例、Watch 通知、配置预检、panic 隔离、数量边界、Catalog 自动路由和多源融合。未知 Provider 不再回落为 Consul。 |
| **插件清单诊断** | ✅ 已支持 | `plugins list` 列出插件及 Manifest 版本/API；`plugins inspect` 查看单个插件；`plugins doctor` 检查缺失 Manifest 与 API 不兼容。旧插件保持兼容。 |
| **`Discovery` 之外的宿主能力** | ⚠️ 收窄 | `Dependencies` 提供 `Logger + Discovery + Config`。尚不暴露底层 Forwarder、Transport、Router 或连接池。 |
| **Certificate Issuer 插件** | ❌ 未开放 | 标准 ACME CA 可用 `custom + acme_url`；非 ACME 私有签发流程需要另行设计窄接口，不与 DNS Provider 混合。 |
| **配置代际原子发布** | ⚠️ 部分 | Action/Middleware V2 的纯配置错误会在加载期拒绝；运行期依赖导致的 Provision 失败仍可能只阻断对应路由，后续应演进为 candidate generation 全量预构建后发布。 |
| **Transport/Stream 插件** | ❌ 未开放 | 当前是明确边界；需要按真实用例新增窄接口，不应直接暴露内部对象。 |

---

## 九、风险与权衡

* **`Context` / `Dependencies` 即公共 API**：一旦第三方插件开始依赖，这两个结构体极难再改。v1.0 前建议将关键字段标注为 `Experimental`，保留破坏性变更的权利。
* **内置 vs 外部能力不对等**：内置 Action 保留内部高能通道（直接访问 `Executor` 非公开状态），外部插件强制走 `Dependencies` 公共契约。有意权衡，需在文档中清晰界定。
* **热重载下的资源泄露**：插件若在 `Provision` 里起了后台 goroutine，却没在 `Cleanup` 终止，多次重载后会泄露内存与句柄。规范上要求 `Provision` 启动的 goroutine 必须监听宿主 Context 取消信号，并正确实现 `Cleanup`。
* **配置校验前移**：插件的 `Validate` 必须在配置加载期执行，把坏配置拦在初始化阶段，严禁拖到运行时 `Execute` 才抛配置格式错误。

---

## 附：相关文件速查

| 关注点 | 文件 |
|---|---|
| **公共契约**（第三方面向的窄接口） | [pkg/plugin](https://github.com/jamesleeon/LiteGate/blob/master/pkg/plugin)（`register.go` / `context.go` / `config.go` / `middleware.go` / `loadbalancer.go` / `kv.go` / `dns.go` / `ids.go` / `discovery.go`） |
| **公共启动入口**（用户拥有 main） | [pkg/litegate/run.go](https://github.com/jamesleeon/LiteGate/blob/master/pkg/litegate/run.go) |
| DNS Provider 契约（证书 DNS-01 + DDNS） + 内部桥接 | [pkg/plugin/dns.go](https://github.com/jamesleeon/LiteGate/blob/master/pkg/plugin/dns.go) · [internal/cert/interface.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/cert/interface.go) · [internal/ddns/provider.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/ddns/provider.go) |
| 内部契约（Dependencies / 生命周期接口） | [internal/plugin/contract.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/plugin/contract.go) |
| Action 注册表 + 行为接口 + 桥接适配器 + 校验委托 | [internal/action/registry.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/action/registry.go) |
| Action 分发、懒加载、Cleanup | [internal/action/executor.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/action/executor.go) |
| Middleware 注册表 + Stage/Priority + 桥接适配器 | [internal/middleware/registry.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/middleware/registry.go) |
| Middleware 构建 + 链排序 | [internal/router/middleware_factory.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/router/middleware_factory.go) · [internal/router/router.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/router/router.go) |
| LoadBalancer 注册表 + 桥接适配器 | [internal/discovery/loadbalancer.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/discovery/loadbalancer.go) |
| 通用插件的可运行参考（公共 API） | [internal/action/plugin_external_test.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/action/plugin_external_test.go) · [internal/loader/plugin_v2_test.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/loader/plugin_v2_test.go) |
| 第一方 in-tree 参考插件（内部 API） | [internal/plugins/example/example.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/plugins/example/example.go) |
| 可直接编译的公共插件示例 | [examples/plugins](https://github.com/jamesleeon/LiteGate/blob/master/examples/plugins)（Action / Middleware / LoadBalancer / KV / DNS / IDS / Discovery） |
| 上手写插件（Action / Middleware / LoadBalancer） | [plugin-authoring-guide.md](plugin-authoring-guide.md) |
| 写 DNS Provider 插件（证书 DNS-01 + DDNS） | [dns-provider-plugin-guide.md](dns-provider-plugin-guide.md) |
| 写 IDS 鉴权插件 | [ids-provider-plugin-guide.md](ids-provider-plugin-guide.md) |
| 写发现源插件 | [discovery-provider-plugin-guide.md](discovery-provider-plugin-guide.md) |
