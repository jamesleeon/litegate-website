# 插件开发者说明 (Plugin Authoring Guide)

本文档面向需要在**独立代码仓库**中为 LiteGate 开发扩展能力的 Go 研发人员与架构师。
涵盖 LiteGate 公共契约包 [`pkg/plugin`](file:///d:/ecp_source/LiteGate/pkg/plugin) 的设计规范、全部 9 大扩展点的接口签名与代码骨架、生命周期管理、Panic 容错机制与生产级并发避坑指南。

---

## 一、契约与工程脚手架

### 1.1 独立仓库开发原则

- **只依赖公共契约包**：外部插件仅需 `go get github.com/jamesleeon/LiteGate`，并导入公共包 `github.com/jamesleeon/LiteGate/pkg/plugin`。
- **严禁引用 `internal/...`**：LiteGate 的 `internal/` 目录属于内部实现，不对外提供稳定性承诺。所有对外能力均已通过 `pkg/plugin` 封装为轻量、解耦的窄接口。
- **自动初始化与注册**：插件包在自身的 `init()` 函数中调用 `plugin.Register*` 注册，由使用者在构建入口处空导入（Blank Import `_ "your/plugin/path"`）触发。

### 1.2 注入宿主能力：`plugin.Dependencies`

插件在首次实例化构建时，工厂方法会收到宿主环境注入的依赖对象：

```go
type Dependencies struct {
    // 实例上下文。Ingress 插件在此 Context 取消时表示网关正在关闭或卸载该实例。
    Context   context.Context

    // 结构化日志记录器。已预填充网关系统上下文，插件应使用 With().Str("plugin", ...) 派生子日志。
    Logger    *zerolog.Logger

    // 服务发现只读视图。插件可直接根据服务名、命名空间、标签获取健康的后端 IP:Port 端点列表。
    Discovery DiscoveryClient

    // 共享动态配置只读视图。可读取网关热重载后的全局配置只读镜像。
    Config    ConfigProvider
}
```

### 1.3 可选生命周期接口

LiteGate 遵循 **“可选接口 + 类型断言”** 的设计哲学。你的插件如果是无状态纯函数，只需实现核心行为方法；若涉及后台连接、预热或资源回收，可选实现以下接口：

```go
// 1. 全局初始化钩子: 在配置校验通过、实例首次构建时由宿主调度一次
type Provisioner interface {
    Provision(deps *Dependencies) error
}

// 2. 优雅清理钩子: 在网关配置重载（旧代实例延迟回收）或停机关机时由宿主调用
type CleanerUpper interface {
    Cleanup() error
}
```

---

## 二、9 大插件扩展点开发实战

### 1. Action 插件 (终结型动作)

Action 负责终结 HTTP 请求并生成响应。

```go
package myaction

import (
	"fmt"
	"net/http"

	"github.com/jamesleeon/LiteGate/pkg/plugin"
)

type customConfig struct {
	Greeting string `json:"greeting"`
	Code     int    `json:"code"`
}

type actionHandler struct {
	deps *plugin.Dependencies
}

// Execute 接收请求上下文 ctx (包含 ctx.Req 和 ctx.W) 以及当次路由配置 cfg
func (h *actionHandler) Execute(ctx *plugin.Context, cfg plugin.ActionConfig) error {
	var c customConfig
	if err := cfg.Decode(&c); err != nil {
		return fmt.Errorf("invalid action config: %w", err)
	}

	ctx.W.Header().Set("Content-Type", "application/json; charset=utf-8")
	ctx.W.WriteHeader(c.Code)
	_, err := ctx.W.Write([]byte(fmt.Sprintf(`{"message": %q}`, c.Greeting)))
	return err
}

func init() {
	_ = plugin.RegisterAction("my_greeting", plugin.ActionRegistration{
		Factory: func(deps *plugin.Dependencies) plugin.Handler {
			return &actionHandler{deps: deps}
		},
		Validate: func(cfg plugin.ActionConfig) error {
			var c customConfig
			if err := cfg.Decode(&c); err != nil {
				return err
			}
			if c.Greeting == "" {
				return fmt.Errorf("greeting message cannot be empty")
			}
			return nil
		},
	})
}
```

---

### 2. Middleware V2 插件 (中间件流水线)

Middleware V2 采用阶段化（Stage）流水线设计。支持 8 个精确顺序阶段：
`Preflight` → `RequestTransform` → `Security` → `TrafficControl` → `Authentication` → `PostAuth` → `Response` → `Upstream`。

```go
package mymiddleware

import (
	"net/http"

	"github.com/jamesleeon/LiteGate/pkg/plugin"
)

type traceMiddleware struct{}

func (m *traceMiddleware) Wrap(next http.Handler, site plugin.SiteConfig, name string, config plugin.MiddlewareConfig) http.Handler {
	var settings struct { HeaderName string `json:"header_name"` }
	if err := config.Decode(&settings); err != nil { panic(err) }
	headerName := settings.HeaderName
	if headerName == "" {
		headerName = "X-Request-Trace"
	}

	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		traceID := r.Header.Get(headerName)
		if traceID == "" {
			traceID = "trace-" + r.RemoteAddr
			r.Header.Set(headerName, traceID)
		}
		w.Header().Set(headerName, traceID)

		next.ServeHTTP(w, r)
	})
}

func init() {
	_ = plugin.RegisterMiddleware("my_trace", plugin.MiddlewareRegistration{
		Factory: func(deps *plugin.Dependencies) plugin.MiddlewareHandler {
			return &traceMiddleware{}
		},
		Descriptor: plugin.MiddlewareDescriptor{
			Phase:       plugin.PhasePreflight, // 放入安全阶段前
			Order:       10,                      // 相对排序权重
		},
		Validate: func(config plugin.MiddlewareConfig) error {
			// 加载期 fail-closed 检查
			var settings struct { HeaderName string `json:"header_name"` }
			return config.Decode(&settings)
		},
	})
}
```

---

### 3. LoadBalancer 插件 (自定义负载均衡算法)

实现自定义上游节点选择逻辑（如一致性哈希、加权最小响应时间等）：

```go
package mybalancer

import (
	"math/rand"

	"github.com/jamesleeon/LiteGate/pkg/plugin"
)

type randomBalancer struct{}

// Next 从可用端点列表中根据 key 选择一个 Endpoint。
func (b *randomBalancer) Next(endpoints []plugin.Endpoint, key string) plugin.Endpoint {
	if len(endpoints) == 0 {
		return nil
	}
	idx := rand.Intn(len(endpoints))
	return endpoints[idx]
}

// 可选: 实现 FeedbackBalancer 接收请求完成回调 (用于自适应延迟/最小活跃数算法)
func (b *randomBalancer) Done(ep plugin.Endpoint, result plugin.UpstreamResult) {
	// result 包含: Err, StatusCode, Duration, HeaderDuration, Canceled
}

func init() {
	_ = plugin.RegisterLoadBalancer("pure_random", func() plugin.LoadBalancer {
		return &randomBalancer{}
	})
}
```

---

### 4. Ingress 插件 (端口入口拦截)

Ingress 插件能够在 Site 路由与规范化之前判定是否接管该连接（如 HTTP CONNECT 正向代理、特定端口协议多路复用等）：

```go
package myingress

import (
	"context"
	"net/http"

	"github.com/jamesleeon/LiteGate/pkg/plugin"
)

type ingressConfig struct {
	MagicToken string `json:"magic_token"`
}

type ingressHandler struct {
	expectedToken string
}

// Claim 在进入常规路由前执行判定。返回非 nil 即表示由该 Handler 全权接管并终结该请求。
func (h *ingressHandler) Claim(r *http.Request, meta plugin.IngressRequest) http.Handler {
	if r.Header.Get("X-Magic-Bypass") == h.expectedToken {
		return http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte("Intercepted by Ingress Plugin on EntryPoint: " + meta.EntryPoint))
		})
	}
	return nil // 返回 nil 表示放弃接管，请求继续流向正常的 Site 路由
}

// 实现 IngressCloser 接口以支持平滑关机
func (h *ingressHandler) Close(ctx context.Context) error {
	return nil
}

func init() {
	_ = plugin.RegisterIngress("magic_bypass", plugin.IngressRegistration{
		Validate: func(cfg plugin.IngressConfig) error {
			var c ingressConfig
			return cfg.Decode(&c)
		},
		Factory: func(cfg plugin.IngressConfig, deps *plugin.Dependencies) (plugin.IngressHandler, error) {
			var c ingressConfig
			_ = cfg.Decode(&c)
			return &ingressHandler{expectedToken: c.MagicToken}, nil
		},
	})
}
```

---

### 5. Discovery Provider 插件 (服务发现源)

为动态路由和上游健康池提供外部注册中心发现能力：

```go
package mydiscovery

import (
	"context"

	"github.com/jamesleeon/LiteGate/pkg/plugin"
)

type memoryDiscovery struct{}

func (d *memoryDiscovery) Discover(ctx context.Context) ([]plugin.DiscoveredService, error) {
	return []plugin.DiscoveredService{
		{
			Name: "order-service",
			Endpoints: []plugin.DiscoveredEndpoint{
				{Address: "10.0.0.1:8080", Weight: 10, Tags: map[string]string{"env": "prod"}},
				{Address: "10.0.0.2:8080", Weight: 10, Tags: map[string]string{"env": "prod"}},
			},
		},
	}, nil
}

func (d *memoryDiscovery) Watch(ctx context.Context) (<-chan []plugin.DiscoveredService, error) {
	ch := make(chan []plugin.DiscoveredService)
	// 在后台根据需要推送变更
	return ch, nil
}

func init() {
	_ = plugin.RegisterDiscoveryProvider("in_memory", plugin.DiscoveryRegistration{
		Validate: func(raw map[string]any) error { return nil },
		Factory: func(raw map[string]any, deps *plugin.Dependencies) (plugin.DiscoveryProvider, error) {
			return &memoryDiscovery{}, nil
		},
	})
}
```

---

### 6. DNS Provider 插件 (DNS-01 证书质询与 DDNS)

```go
package mydns

import (
	"context"
	"time"

	"github.com/jamesleeon/LiteGate/pkg/plugin"
)

type customDNS struct{}

func (d *customDNS) Present(ctx context.Context, domain, keyAuth string) error {
	// 向权威 DNS API 写入 _acme-challenge TXT 记录
	return nil
}

func (d *customDNS) CleanUp(ctx context.Context, domain, keyAuth string) error {
	// 清理 TXT 记录
	return nil
}

func (d *customDNS) Timeout() (timeout, interval time.Duration) {
	return 120 * time.Second, 2 * time.Second
}

func init() {
	_ = plugin.RegisterDNSProviderV2("my_dns_provider", plugin.DNSProviderRegistration{
		Capabilities: []string{"dns-01"},
		Validate:     func(raw map[string]any) error { return nil },
		Factory: func(raw map[string]any, deps *plugin.Dependencies) (any, error) {
			return &customDNS{}, nil
		},
	})
}
```

---

### 7. IDS Provider 插件 (鉴权安全治理)

用于在请求到达 Action 前执行统一鉴权决策，并可动态返回路由金丝雀标签（Selector）：

```go
package myids

import (
	"context"
	"net/http"

	"github.com/jamesleeon/LiteGate/pkg/plugin"
)

type pathGuardIDS struct{}

func (g *pathGuardIDS) Evaluate(ctx context.Context, req *http.Request, opts plugin.IDSOptions) (*plugin.IDSResult, error) {
	if req.Header.Get("X-Block-Me") == "true" {
		return &plugin.IDSResult{
			Allowed:      false,
			StatusCode:   http.StatusForbidden,
			ErrorMessage: "Forbidden by PathGuard IDS Plugin",
		}, nil
	}

	return &plugin.IDSResult{
		Allowed: true,
		// 可选: 为下游 Proxy 注入选路金丝雀标签
		Selector: map[string]string{"canary": "true"},
	}, nil
}

func init() {
	_ = plugin.RegisterIDSProvider("path_guard", plugin.IDSProviderRegistration{
		Validate: func(raw map[string]any) error { return nil },
		Factory: func(raw map[string]any, deps *plugin.Dependencies) (plugin.IDSProvider, error) {
			return &pathGuardIDS{}, nil
		},
	})
}
```

---

### 8. KV Provider 插件 (动态内容流)

```go
package mykv

import (
	"context"

	"github.com/jamesleeon/LiteGate/pkg/plugin"
)

type staticKV struct{}

func (k *staticKV) Watch(ctx context.Context, key string) (<-chan []byte, error) {
	ch := make(chan []byte, 1)
	ch <- []byte("<h1>Hello from KV Provider Plugin</h1>")
	return ch, nil
}

func init() {
	_ = plugin.RegisterKVProvider("static_kv", func() plugin.KVProvider {
		return &staticKV{}
	})
}
```

---

### 9. Template Func 插件 (模板函数扩展)

```go
package myfuncs

import (
	"strings"

	"github.com/jamesleeon/LiteGate/pkg/plugin"
)

func init() {
	_ = plugin.RegisterTemplateFunc("maskPhone", func(phone string) string {
		if len(phone) < 7 {
			return phone
		}
		return phone[:3] + "****" + phone[len(phone)-4:]
	})
	_ = plugin.RegisterTemplateFunc("toUpper", strings.ToUpper)
}
```

---

## 三、注册统一元数据：`plugin.RegisterManifest`

为使插件能够被 `litegate plugins list`、`inspect`、`doctor` 以及 Web Dashboard 识别，强烈建议每个插件在 `init()` 中注册元数据：

```go
func init() {
	_ = plugin.RegisterManifest(plugin.Manifest{
		Kind:        "action",         // 支持 action, middleware, load_balancer, kv, dns, ids, discovery, ingress
		Name:        "my_greeting",    // 与 Register* 保持完全一致的小写名称
		Version:     "1.0.0",          // 语义化版本
		APIVersion:  plugin.APIVersion,// 当前公共契约规范版本 (即 "v1")
		DisplayName: "Greeting Response Action",
		Description: "Returns a friendly JSON greeting message with custom HTTP status code.",
		License:     "Apache-2.0",
		Capabilities: []string{"response", "json"},
		ConfigExample: `# Example Route Configuration:
routes:
  - name: greeting-route
    match:
      path: /hello
    action:
      type: my_greeting
      greeting: "Hello, World!"
      code: 200`,
	})
}
```

---

## 四、生产级健壮性与避坑指南

### 1. 单例与高并发状态隔离 (Thread Safety)
> [!CAUTION]
> **切勿在 Handler 结构体字段中存储每请求（Per-Request）的状态！**
> LiteGate 中注册的插件 Handler 实例是**全局共享单例**。成千上万个并发 goroutine 会同时调用 `Execute` 或 `Wrap`。
> 所有随请求变化的数据必须保存在局部变量或 `ctx.Req.Context()` 中。结构体内部如需维护共享缓存或连接池，必须使用 `sync.RWMutex` 或原子操作保护。

### 2. 加载期校验必须纯粹无副作用 (Fail-Closed)
- `Validate` 函数在网关启动或配置加载阶段执行。
- **严禁在 `Validate` 中发起真实的 TCP/网络连接、耗时 I/O 或开启后台 goroutine**。
- `Validate` 的职责是检查 YAML 字段拼写、非空限制、类型越界等静态语义。如果有问题直接返回 `error`，确保坏配置在上线前就被阻断。

### 3. 热重载与资源泄露防范 (Graceful Resource Lifecycle)
- 若插件在 `Provision` 中启动了后台心跳或同步 goroutine，必须监听 `deps.Context.Done()`。
- 实现 `CleanerUpper` 接口并在 `Cleanup()` 中安全关闭连接池、关闭管道通道。
- LiteGate 在热重载时会给旧实例保留 15 秒（或配置的优雅关机宽限期）的排空时间，超时后会强制调用 `Cleanup()`。

### 4. 全链路 Panic 自动隔离保护
LiteGate 在所有外部插件交互点（工厂创建、配置校验、请求执行、生命周期销毁）均内置了全方位的 `recover()` 兜底恢复机制。
如果第三方插件发生未捕获的 Panic：
- 校验期 Panic：自动捕获并转换为配置加载失败，不崩溃整个守护进程。
- 请求期 Panic：自动捕获并记录 Error 级别日志，向客户端返回 500 状态码，避免单个异常请求击垮网关集群。
- 尽管如此，插件自身仍应遵循防御性编程原则，主动处理空指针与类型断言。

---

## 五、单元测试与本地联调

在独立仓库中编写单测极为简单，可直接模拟 `plugin.Context` 或 `http.Handler` 进行断言：

```go
package myaction

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/jamesleeon/LiteGate/pkg/plugin"
)

func TestGreetingAction(t *testing.T) {
	h := &actionHandler{}
	w := httptest.NewRecorder()
	r := httptest.NewRequest("GET", "/hello", nil)

	ctx := &plugin.Context{W: w, Req: r}
	rawCfg := plugin.NewActionConfig(map[string]any{
		"greeting": "Hello Test",
		"code":     200,
	})

	err := h.Execute(ctx, rawCfg)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if w.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", w.Code)
	}
	if w.Body.String() != `{"message": "Hello Test"}` {
		t.Errorf("unexpected body: %s", w.Body.String())
	}
}
```

更多经过实战验证的各类型完整测试范例，可参考 LiteGate 源码目录中的 [`examples/plugins`](file:///d:/ecp_source/LiteGate/examples/plugins)。
