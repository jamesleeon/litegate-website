# LiteGate 插件开发指南（Plugin Authoring Guide）

> 本文教你如何在**独立仓库**里为 LiteGate 编写插件，编译出带你自己插件的网关二进制，以及**必须注意的坑**。
> 公共契约包：[`github.com/jamesleeon/LiteGate/pkg/plugin`](https://github.com/jamesleeon/LiteGate/blob/master/pkg/plugin)。
> 可运行的插件参考实现见 [`internal/action/plugin_external_test.go`](https://github.com/jamesleeon/LiteGate/blob/master/internal/action/plugin_external_test.go) 和 [`pkg/plugin`](https://github.com/jamesleeon/LiteGate/blob/master/pkg/plugin) 下的测试。
> 设计原理与取舍见同目录 [`plugin-architecture.md`](plugin-architecture.md)。

---

## 一、这是什么 / 适用范围

LiteGate 采用 **编译期注册表（compile-time registry）** 插件模型，类似 Caddy：

* 插件是一个普通 Go 包，在 `init()` 里通过公共包 `pkg/plugin` 向注册表登记自己。
* 你写**自己的 `main`**，空导入插件包并调用 `litegate.Run()`，`go build` 即得带插件的二进制。
* **不用 fork、不用改 LiteGate 核心代码** —— 插件住在你自己的仓库里。

> ✅ 公共契约已从 `internal/` 毕业到 [`pkg/plugin`](https://github.com/jamesleeon/LiteGate/blob/master/pkg/plugin)，入口在 [`pkg/litegate`](https://github.com/jamesleeon/LiteGate/blob/master/pkg/litegate)。
> 因此**第三方独立仓库**现在可以直接 `import` 并编译，无需把代码放进本仓库（in-tree 的老方式已不推荐）。

**不支持**运行时动态加载 `.so`（Go 在 Windows 不可用、Linux 脆弱，已明确排除）。

---

## 二、通用插件

全部定义在公共包 `pkg/plugin`：

| 类型 | 用途 | 注册函数 | 必选接口 | 配置入口 |
|---|---|---|---|---|
| **Action** | 终结请求、产出响应（代理、渲染、鉴权终结…） | `plugin.RegisterAction` | `Execute` | `ActionConfig`（YAML 内联键） |
| **Middleware** | 请求链上加工（限流、改写、注入…），再交给下一环 | `plugin.RegisterMiddleware` | `Wrap` + 注册描述符 | `config plugin.MiddlewareConfig` |
| **LoadBalancer** | 自定义上游选择策略 | `plugin.RegisterLoadBalancer` | `Next` | `action.lb_policy` |
| **KV Provider** | 为 `serve` / `template` 提供持续更新的内容 | `plugin.RegisterKVProvider` | `Watch` | `action.kv_provider` / `kv_key` |
| **Ingress** | 指定入口上，在 Site 匹配前接管 HTTP 请求 | `plugin.RegisterIngress` | `Claim` | 全局 `ingress_plugins[].config` |

* **Action** 必须注册纯校验函数 `ActionRegistration.Validate`，加载期不构造运行实例。可选 `Validator` 用于实例初始化后、依赖宿主全局配置的运行期语义检查。
* **Middleware / LoadBalancer** 同样支持可选的**生命周期接口**：`Provisioner` / `CleanerUpper`（初始化和清理皆被网关生命周期管理托管）。
* 公共注册入口分别为 `RegisterAction` 和 `RegisterMiddleware`，不保留工厂独立注册或旧版接口。

所有注册函数都返回 `error`：空名、nil 工厂、重名、或与内置类型冲突都会被拒绝。

Ingress 的校验、工厂与关闭契约见 [入口插件开发指南](ingress-plugin-guide.md)；
可运行的正向代理实现见 [forward_proxy 示例](https://github.com/jamesleeon/LiteGate/blob/master/examples/plugins/ingress/forwardproxy/README.md)。

> 除上述通用插件外，LiteGate 还按同一编译期注册表范式开放了三类**领域插件**，各有专门指南：
> - **DNS Provider**（接管 ACME 证书 DNS-01 质询与 DDNS 同步）→ [dns-provider-plugin-guide.md](dns-provider-plugin-guide.md)
> - **IDS 鉴权**（自定义凭证 Provider / 会话 Issuer / 模式处理器）→ [ids-provider-plugin-guide.md](ids-provider-plugin-guide.md)
> - **Discovery Provider**（向动态路由和上游池提供服务/Endpoint）→ [discovery-provider-plugin-guide.md](discovery-provider-plugin-guide.md)

---

## 三、快速开始：在你自己的仓库写一个 Action 插件

标准 LiteGate 二进制默认编入 NATS Action、OpenAPI MD5 IDS 和 forward proxy 入口插件，
可通过 `litegate plugins list` 与 Dashboard 的 “Compiled Plugins” 查看并复制配置。
开发时参考 [NATS](https://github.com/jamesleeon/LiteGate/blob/master/internal/plugins/nats)、[OpenAPI MD5](https://github.com/jamesleeon/LiteGate/blob/master/internal/plugins/openapi_md5)
和 [forward proxy](https://github.com/jamesleeon/LiteGate/blob/master/pkg/plugins/forwardproxy) 的实际实现；独立 module 示例见
[examples/plugins](https://github.com/jamesleeon/LiteGate/blob/master/examples/plugins/README.md)。各插件需显式配置才启用。

建议每个插件组件同时注册统一 Manifest，供构建产物进行版本与兼容性诊断：

```go
plugin.RegisterManifest(plugin.Manifest{
    Kind: "action", Name: "my_action", Version: "1.2.0",
    APIVersion: plugin.APIVersion,
    DisplayName: "My Action", Capabilities: []string{"response"},
    // 只放可公开展示的最小配置，不要写 token、密码或真实域名。
    ConfigExample: `routes:
  - name: my-action
    match:
      path: /my-action
    action:
      type: my_action`,
})
```

`Kind` 支持 `action`、`middleware`、`load_balancer`、`kv`、`dns`、`ids` 和
`discovery`、`ingress`。未注册 Manifest 的旧插件仍可运行，但 `plugins doctor` 会提示版本与兼容性未知。
`ConfigExample` 会同时出现在 `litegate plugins inspect` 和 Dashboard 的插件卡片中，用户可展开并复制；
它最多 16 KiB，属于公开运行状态数据，因此必须使用占位值，绝不能包含密钥。

### 第 1 步：建模块，写插件包

```
my-litegate/
  go.mod        // module my-litegate
                // require github.com/jamesleeon/LiteGate vX.Y.Z
  greeting/
    greeting.go
  main.go
```

`greeting/greeting.go` —— 最小骨架：

```go
package greeting

import (
	"fmt"
	"net/http"

	"github.com/jamesleeon/LiteGate/pkg/plugin"
	"github.com/rs/zerolog/log"
)

// actionType 是用户写在 YAML action.type 里的名字，不能与内置类型重名。
const actionType = "greeting"

type handler struct {
	deps *plugin.Dependencies // 仅放全局、只读、线程安全的东西
}

type config struct {
	Message string `json:"message"`
}

// Execute 是唯一必须实现的方法。每个命中本路由的请求都会调用它，可能并发。
func (h *handler) Execute(ctx *plugin.Context, cfg plugin.ActionConfig) error {
	// 每请求从 cfg 现读“本条路由”的配置，不要缓存到结构体字段上。
	var c config
	if err := cfg.Decode(&c); err != nil {
		return err
	}
	if name := ctx.Req.URL.Query().Get("name"); name != "" {
		c.Message += ", " + name
	}
	ctx.W.Header().Set("Content-Type", "text/plain; charset=utf-8")
	ctx.W.WriteHeader(http.StatusOK)
	_, err := ctx.W.Write([]byte(c.Message))
	return err
}

// init 在包被导入时自动注册本插件。
func init() {
	err := plugin.RegisterAction(actionType, plugin.ActionRegistration{
		Factory: func(deps *plugin.Dependencies) plugin.Handler {
			return &handler{deps: deps}
		},
		Validate: func(cfg plugin.ActionConfig) error {
			var c config
			if err := cfg.Decode(&c); err != nil {
				return err
			}
			if c.Message == "" {
				return fmt.Errorf("message must not be empty")
			}
			return nil
		},
	})
	if err != nil {
		log.Error().Err(err).Str("plugin", actionType).Msg("register failed")
	}
}
```

### 第 2 步：写你自己的 `main`，把插件编进去

`main.go`：

```go
package main

import (
	"log"

	"github.com/jamesleeon/LiteGate/pkg/litegate"

	_ "my-litegate/greeting" // ← 空导入即触发 init() 注册
)

func main() {
	if err := litegate.Run(); err != nil {
		log.Fatalf("litegate exited: %v", err)
	}
}
```

`litegate.Run()` 复用 LiteGate 全部 CLI 旗标与启动逻辑；也可传选项，如 `litegate.Run(litegate.WithConfigPath("custom.yaml"))`。

### 第 3 步：配置 —— YAML 里直接写自定义键

`action` 下任何**未匹配命名字段**的键会被自动收进插件配置，由 `ActionConfig` 读取：

```yaml
routes:
  - name: "demo"
    match: { path_prefix: "/demo" }
    action:
      type: "greeting"         # ← 你注册的名字
      message: "hi"            # ← cfg.Get("message") / cfg.Decode 可读
      threshold: 100           # ← 数字进来是 int/float
```

读取配置三种方式（见 §4.2）：`cfg.Type()`、`cfg.Get(key)`、`cfg.Decode(&struct)`。

### 第 4 步：编译

```bash
cd my-litegate
go mod tidy
go build -o litegate .
./litegate -config config.yaml
```

完成 —— 配置里写 `type: greeting` 即生效。本地联调 LiteGate 源码时，可在 `go.mod` 里用 `replace github.com/jamesleeon/LiteGate => ../LiteGate`。

---

## 四、接口契约详解（`pkg/plugin`）

### 4.1 行为接口

```go
// Action
type Handler interface {
	Execute(ctx *Context, cfg ActionConfig) error
}

// Middleware 运行接口；V2 的位置、顺序和校验由注册描述符声明
type MiddlewareHandler interface {
	Wrap(next http.Handler, site SiteConfig, name string, config plugin.MiddlewareConfig) http.Handler
}

type KVProvider interface {
	Watch(ctx context.Context, key string, update func([]byte)) error
}

// LoadBalancer
type LoadBalancer interface {
	Next(endpoints []Endpoint, key string) Endpoint
}
```

### 4.2 请求上下文与配置（窄视图，不泄漏内部类型）

Middleware 注册项可以提供可选的 `InlineConfig func(value any) (map[string]any, error)`，让统一站点 YAML 支持以插件类型名为键的站点/路由简写。它把 YAML 标量或对象转换成命名中间件的同一配置，由宿主继续调用 `Validate`，再生成普通 middleware 绑定。转换和校验必须无副作用、可并发；panic 或错误会阻止配置加载。站点声明被路由继承，路由声明替换完整配置，也可通过 snippets/import 复用。现有插件省略此字段时行为不变；示例见 `pkg/plugins/forwardauth`。

```go
// Context —— 插件能看到的请求信息（只有这些字段）
type Context struct {
	W             http.ResponseWriter
	Req           *http.Request
	Site          string
	MatchedPrefix string
	ClientIP      string
}

// ActionConfig —— 只读配置视图
type ActionConfig interface {
	Type() string                 // action.type
	Get(key string) (any, bool)   // 取单个原始值
	Decode(target any) error   // 解码到你的 struct（按 json tag）
}

// SiteConfig —— 中间件能看到的站点信息
type SiteConfig interface {
	Domain() string
	Port() int
	MaxRequestBodySize() int64
}

// Endpoint —— 负载均衡能看到的后端端点（只读）
type Endpoint interface {
	ID() string
	Address() string
	Port() int
	Weight() int
	Healthy() bool
	Tags() []string
	ServiceName() string
	Metadata() map[string]string
	ActiveRequests() int64
	Latency() time.Duration
}
```

> 这些都是**窄接口/窄 DTO**，刻意不暴露 `loader.Action`、`loader.SiteConfig`、`discovery.ServiceEndpoint` 等内部重型类型——这样核心可以自由演进而不破坏你的插件。

### 4.3 可选生命周期接口（实现才生效）

| 接口 | 方法 | 何时被调用 | 用途 |
|---|---|---|---|
| `Provisioner` | `Provision(deps *Dependencies) error` | 首次实例化时（一次） | 全局初始化（Action / Middleware / LoadBalancer 均支持） |
| `Validator` | `Validate(cfg ActionConfig) error` | 配置加载/重载期，逐路由 | 实例初始化后的语义检查；加载期必须用 `ActionRegistration.Validate` |
| `CleanerUpper` | `Cleanup() error` | 释放/关机时（一次） | 优雅释放资源（Action / Middleware / LoadBalancer 均支持） |

### 4.4 宿主依赖 `Dependencies`

Action / Middleware 的工厂收到 `*plugin.Dependencies`（LoadBalancer 工厂不收依赖）：

```go
type Dependencies struct {
	Logger    *zerolog.Logger
	Discovery DiscoveryClient
	Config    ConfigProvider
}

// 服务发现的窄只读视图
type DiscoveryClient interface {
	GetEndpoints(ctx context.Context, serviceName, namespace, serviceTag string) ([]string, error)
}
```

`GetEndpoints` 默认查询网关**实际配置的发现源**（consul / litemesh / docker…），返回健康端点的 `host:port` 列表。
`Config` 是热更新的完整 `plugin_config` 只读快照；可用 `Lookup`、`Scope` 和 `Version` 读取。`litegate -t` 也会加载并校验这份配置。

---

## 五、生命周期全景

```
程序启动
  └─ 各插件包 init() → RegisterAction / RegisterMiddleware / RegisterLoadBalancer / RegisterKVProvider
配置加载 / 热重载
  ├─ 加载并发布完整 plugin_config 快照
  └─ 调用 ActionRegistration.Validate / MiddlewareRegistration.Validate
       [纯校验、fail-closed，不创建运行实例]
首个请求命中该 Action 类型（懒加载，singleflight 去重）
  └─ 工厂 factory(deps) → Provisioner.Provision(deps)     [一次，全局初始化，拿不到路由配置]
每个请求
  └─ Handler.Execute() / Wrap 后的中间件链 / LB.Next()    [高并发，类型级共享实例]
关机
  └─ CleanerUpper.Cleanup()                               [一次，优雅释放]
```

> Middleware 的 `Wrap` 在**构建期**（配置加载/重载）调用一次，返回的 `http.Handler` 才是每请求执行——所以中间件的初始化放在**工厂函数**里即可。

---

## 六、Middleware 插件要点

```go
type settings struct {
    Threshold int  `json:"threshold"`
    Disabled bool  `json:"disabled"`
}
type myMW struct{ deps *plugin.Dependencies }
func (h *myMW) Wrap(next http.Handler, site plugin.SiteConfig, name string, raw plugin.MiddlewareConfig) http.Handler {
    var cfg settings
    if err := raw.Decode(&cfg); err != nil { panic(err) }
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        // 使用 cfg.Threshold 执行业务检查。
        next.ServeHTTP(w, r)
    })
}
func init() {
    _ = plugin.RegisterMiddleware("my_mw", plugin.MiddlewareRegistration{
        Factory: func(deps *plugin.Dependencies) plugin.MiddlewareHandler { return &myMW{deps: deps} },
        Descriptor: plugin.MiddlewareDescriptor{Phase: plugin.PhaseAuthentication, Order: 500},
        Validate: func(raw plugin.MiddlewareConfig) error {
            var cfg settings
            if err := raw.Decode(&cfg); err != nil { return err }
            if cfg.Threshold <= 0 { return errors.New("threshold must be positive") }
            return nil
        },
        Active: func(raw plugin.MiddlewareConfig) bool {
            var cfg settings
            if err := raw.Decode(&cfg); err != nil { panic(err) }
            return !cfg.Disabled
        },
    })
}

```

Middleware 有八个精确阶段，`Order` 越小越靠外、越早进入；相同 Order 保留配置声明顺序：

| Phase | 典型用途 |
|---|---|
| `PhasePreflight` | CORS 预检 |
| `PhaseRequestTransform` | URL / Header 改写 |
| `PhaseSecurity` | IP 规则、WAF |
| `PhaseTrafficControl` | 限流、连接数限制 |
| `PhaseAuthentication` | 身份认证、IDS |
| `PhasePostAuth` | 鉴权后的审计、镜像 |
| `PhaseResponse` | 压缩、缓存、响应加工 |
| `PhaseUpstream` | 紧贴 Action 的最后一层 Handler 包装 |

公共插件当前使用 `ExecutionHandler`。`ExecutionUpstream` 保留给宿主直接编译 retry / circuit-breaker 的底层上游策略，不开放 Transport 对象。公共行为接口只包含 `Wrap`；Stage / Priority 已删除，执行位置统一由 Descriptor 声明。

---

## 七、LoadBalancer 插件要点

```go
type gpuLB struct{}

// Next 从给定端点里选一个返回；返回的必须是入参切片中的某个元素。
func (l *gpuLB) Next(endpoints []plugin.Endpoint, key string) plugin.Endpoint {
	var best plugin.Endpoint
	for _, ep := range endpoints {
		if !ep.Healthy() {
			continue
		}
		if best == nil || ep.ActiveRequests() < best.ActiveRequests() {
			best = ep
		}
	}
	return best // 无可用时返回 nil，宿主会回退到 round_robin
}

func init() {
	_ = plugin.RegisterLoadBalancer("gpu_aware", func() plugin.LoadBalancer {
		return &gpuLB{} // 注意：LB 工厂不收 Dependencies
	})
}
```

配置：`action.lb_policy: "gpu_aware"`。

* `Next` 在**每次选上游时**被调用（热路径），**必须线程安全、不可阻塞**。
* **必须返回入参 `endpoints` 中的某个元素**（宿主据此映射回真实端点）；返回 `nil` 表示放弃，宿主回退到 `round_robin`。
* 别把 `Endpoint` 引用缓存到结构体字段——它只在本次调用有效。

---

## 八、KV Provider 插件要点

```go
type provider struct{}

func (provider) Watch(ctx context.Context, key string, update func([]byte)) error {
	// 首次成功读取后推送完整快照；内容变化时继续推送。
	// ctx 取消后应尽快停止后台读取并返回。
	update([]byte("initial content"))
	<-ctx.Done()
	return ctx.Err()
}

func init() {
	_ = plugin.RegisterKVProvider("my_kv", provider{})
}
```

配置 `serve` / `template` Action 时使用 `kv_provider: my_kv` 与 `kv_key: ...`。回调参数是完整内容快照，不是增量 patch；插件不得在回调返回后继续修改同一字节切片。

---

## 九、⚠️ 必须注意的事（踩坑清单）

1. **Handler / LB 是【跨路由的类型级单例】**。所有用该类型的路由共享一个实例并发调用。**每路由不同的配置必须在 `Execute` 里从 `cfg` 现读，不能缓存到结构体字段**，否则路由间互相覆盖。结构体字段只放全局只读/线程安全的东西。

2. **不能覆盖内置类型**。`RegisterAction("proxy", …)`、`RegisterMiddleware("cors", …)`、`RegisterLoadBalancer("round_robin", …)` 都会返回 error。取个不冲突的名字。

3. **`Validate` 是 fail-closed**。Action V2 与 Middleware V2 的任何一条配置非法，都会让启动/重载失败。校验函数必须确定、无副作用、可并发调用；不要开连接、启动 goroutine 或修改全局状态。

4. **panic 有兜底，但别依赖它**。工厂、`Provision`、`Validate`、以及插件的 `Execute` 都被宿主 recover 成 error / 500，不会拖垮进程。请自己处理错误，别把 recover 当正常流程。

5. **Middleware / LoadBalancer 支持可选的生命周期钩子**。它们可以通过实现可选的 `Provisioner` 和 `CleanerUpper` 接口来参与生命周期的全局 `Provision` 与 `Cleanup`（由宿主统一调度与安全恢复），不再需要完全在 Wrap/Next 内自行做复杂的资源管理。当然，简单初始化仍可在工厂函数内做。

6. **`Provision` 拿不到路由配置**。它只做与路由无关的全局初始化。需要路由配置的逻辑放 `Execute`。

7. **配置值类型要小心**。YAML 数字进来是 `int`/`float64`，不是 string。优先用 `cfg.Decode(&struct)`（按 json tag 解码，省去逐个断言）；用 `cfg.Get` 时务必类型断言并处理失败。

8. **依赖最小集**。插件只拿到 `Logger`、`Discovery` 与只读热更新 `Config`。需要更多宿主能力，应推动在 `pkg/plugin` 里**追加窄接口**，而不是依赖内部具体类型。

9. **热更新（Reload）期间可能短暂双实例**。优雅重载会把旧实例放入宿主追踪的延迟清理队列（通常 15 秒），新请求同时使用新实例；进程退出时队列会被同步排空。插件仍需保证独占资源的交接安全，或容忍短暂双实例。

10. **IDS 不再只保护 proxy**。只要 Action 配置了 IDS，`respond`、`serve`、`template`、WebDAV 和第三方 Action 都会先经过 IDS；proxy 的实例感知检查仍保留，但同一请求不会重复 Evaluate。

---

## 十、构建与分发

### 方式 1：利用 `litegate build --with` 一键构建（推荐）
LiteGate 内置了仿 `xcaddy` 的一键构建命令行工具。你只需在本地配置好 Go 工具链且网络能够访问 module proxy，即可执行：
```bash
litegate build --with example.com/your/plugin@v1.2.3 -o my-litegate
```

`--with` 可重复，并支持 `package[@version][=local_module_dir]`。版本只参与依赖解析，生成的 Go 源码只导入纯 package path：

```bash
# 本地插件子包；右侧必须指向包含 go.mod 的插件模块根目录
litegate build \
  --with example.com/acme/litegate-plugin/dns=../litegate-plugin \
  --with example.com/acme/litegate-plugin/action=../litegate-plugin \
  -o my-litegate

# 通用依赖替换可重复；不产生空导入
litegate build \
  --with example.com/acme/litegate-plugin@v1.2.3 \
  --replace example.com/acme/sdk=../sdk \
  -o my-litegate
```

* **核心版本**：默认使用当前 LiteGate 的版本；可用 `--litegate-version vX.Y.Z` 或 `LITEGATE_VERSION` 明确选择。插件解析完成后会核对最终核心版本，依赖把 LiteGate 偷偷升级/降级时构建会失败，而不是生成版本标识错误的二进制。
* **LiteGate 源码联调**：兼容 `--replace=<LiteGate源码目录>` 和 `LITEGATE_LOCAL_PATH`。这是旧式核心快捷写法；通用替换必须写成 `module=target`。
* **平台与工具链**：继承 `GOOS`、`GOARCH`、`GOARM`、`CGO_ENABLED`、`GOPROXY` 和私有模块认证环境；`LITEGATE_GO` 可选择 Go 命令。
* **诊断与构建**：`--keep-workdir` 保留生成模块，另有 `--race`、`--debug`、`--no-trimpath`。默认开启 `-trimpath`。
* **本地示例**：[`examples/plugins`](https://github.com/jamesleeon/LiteGate/blob/master/examples/plugins) 是独立 Go module，包含 Action、Middleware、LoadBalancer、KV、DNS 和 IDS，可进入目录直接编译。
* **编入检查**：定制二进制可执行 `litegate plugins list` 或 `litegate plugins list --json`，确认插件的 `init` 注册确实存在。

### 方式 2：用户拥有 `main`
如 §三，自建 Go 模块，在主函数中空导入插件包并调用 `litegate.Run()`，随后使用原生 `go build` 编译。版本可通过 `go.mod` 锁定，本地开发可通过 `replace` 替换。

---

## 十一、测试你的插件

参考 [`internal/action/plugin_external_test.go`](https://github.com/jamesleeon/LiteGate/blob/master/internal/action/plugin_external_test.go) 与 V2 注册表测试：

* **Action**：`plugin.RegisterAction` 的纯校验 → `loader.ValidateSite` → `action.NewExecutor` + `Execute` → `CleanupPlugins`。
* **Middleware**：V2 描述符/校验 → Pipeline 精确阶段 → `Wrap` 后 `ServeHTTP` 断言。
* **LoadBalancer**：注册 → `discovery.GetLoadBalancer` → `Next` 选路并验证选中端点。
* **KV Provider**：注册/规范化查找/注销，并在 `serve` / `template` 的 KV 模式接入。

你自己的仓库里可直接对 `pkg/plugin` 的接口做单元测试（构造 `plugin.Context` 与一个实现 `ActionConfig` 的桩），无需启动整个网关。

---

## 速查表

| 我要… | 做法 |
|---|---|
| 加一个新响应类型 | Action 插件，实现 `Execute`，用 `plugin.RegisterAction` 注册 |
| 在请求链上加工 | Middleware 插件，实现 `Wrap`，用 `plugin.RegisterMiddleware` 声明 Phase/Order |
| 自定义选上游策略 | LoadBalancer 插件，实现 `Next`，`plugin.RegisterLoadBalancer` |
| 为 serve/template 提供内容 | KV Provider，实现 `Watch`，`plugin.RegisterKVProvider` |
| 读插件配置 | Action 用 `cfg.Decode`/`cfg.Get`；Middleware 用 `config.Decode` |
| 一次性初始化 | Action/Middleware/LB 均可实现 `Provision`（亦可在工厂里做简单逻辑） |
| 校验配置 | ActionRegistration / MiddlewareRegistration 的 `Validate`（fail-closed） |
| 释放资源 | Action/Middleware/LB 均可实现 `Cleanup`（由网关全局托管释放） |
| 查服务发现 | `deps.Discovery.GetEndpoints(ctx, name, ns, tag)` |
| 读共享配置 | `deps.Config.Scope(prefix).Lookup(key)`，用 `Version()` 感知更新 |
| 编进二进制 | `litegate build --with package[@version][=local_dir]`，或自建 `main` 后 `go build` |

### 配置源 Watch 的取消约定

扩展配置源的 `ConfigSourceProvider.Watch(ctx, publish)` **必须响应 ctx 取消**：取消阻塞 I/O，停止后台读取和发布回调，并尽快返回。热重载会复用未变的配置源实例，宿主等待旧一代 `Watch` 退出后才启动新一代；若插件忽略取消，该配置源的后续更新会一直等待。网络请求应使用传入的 context，阻塞等待应同时监听 `ctx.Done()`。
