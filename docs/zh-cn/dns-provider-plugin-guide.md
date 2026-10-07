# DNS Provider 插件开发指南（证书 DNS-01、DDNS 与 ECH HTTPS 记录）

## 扩展 ECH：插件只负责 DNS 服务商 API

ECH 密钥生成、TLS 安装、轮换、旧密钥保留、文件/KV 加密持久化、Consul/LiteMesh 同步、发布租约、站点选组、重试和发布状态都由 LiteGate 内部负责。DNS 插件只读取并提交服务商的 HTTPS（类型 65）记录，不需要实现 KV，也不会收到 ECH 私钥或存储密钥。

实现公共接口并通过 `RegisterDNSProviderV2` 声明 `DNSCapabilityHTTPS`（字符串 `https_records`）：

```go
type HTTPSDNSProvider interface {
    DNSProvider // GetName() string
    PublishHTTPS(ctx context.Context, name, value string, owned []string) error
}
```

`name` 为隐藏网站的 DNS owner；`value` 为公开记录值，如 `1 . alpn="h2,h3" ech="..."`，不包含 owner/type/TTL，TTL 使用 600 秒。`owned` 是 LiteGate 根据当前/保留密钥及发布状态计算的可管理记录值列表。插件需要先读取现有 RRset，按 DNS 语义比较（不能只比较引号或参数顺序），拒绝覆盖不属于 owned 的记录；提交非空 value 时替换已拥有的记录，不能盲目覆盖整个 RRset。value 为空时只撤回 owned 中匹配的记录，保留其他记录；记录不存在时返回成功。不得改动 A/AAAA。尊重 ctx，保持幂等，返回 API 错误供核心重试；支持关闭资源时可实现 DNSCloser。

HTTPS 能力独立于 DDNS，无需实现 Sync。若希望同一个插件还负责公共名称/网站的 DNS-01 证书申请，应另实现 CertDNSProviderV2 并声明 DNSCapabilityCertDNS01；否则配置覆盖这些名称的其他证书提供商。lego DNS-01 适配器不会自动获得 HTTPS 发布能力。

只声明 `https_records` 的插件，其 `domains` 用于 ECH 发布范围；核心会在证书运行时副本中移除这些选择器，避免误当成 DNS-01 证书提供商。原始配置保持不变。每组 public_name 必须有证书覆盖：可使用另一个已启用的 DNS-01 证书提供商、旧版 `auto_cert.provider` + `auto_cert.domains`，或在 `tls.certs_dir` 中放入有效且覆盖该名称的 `.pem`/`.crt` 与同名 `.key` 文件。否则配置校验（包括 `-t`）直接失败。手动证书需要自行更新；校验与启动环境必须能读取它。使用独立证书提供商的示例：

```yaml
auto_cert:
  enabled: true
  dns_providers:
    - name: records
      type: mydns
      enabled: true
      domains: ["*.example.com"]
      config: {api_token: "env://MYDNS_TOKEN"}
    - name: certificates
      type: cloudflare
      enabled: true
      domains: ["*.example.com"]
      config: {api_token: "env://CF_API_TOKEN"}
ech:
  enabled: true
  public_name: ech.example.com
  dns_provider: records
  domains: [app.example.com]
```

`mydns` 必须已注册并编译进二进制。两个提供商操作同一权威 DNS 区域：前者管理 HTTPS，后者管理 ACME TXT；证书提供商也可以是自己实现的插件。

撤回时遇到其他记录应保留并返回成功，不应将所有权冲突作为撤回错误。新 value 不要求出现在 owned 中，owned 只决定哪些已有记录允许删除或替换。配置校验调用插件 Validate 前会解析 secret，并按 provider、auto_cert 的顺序补齐 secret_token；校验环境需能够读取对应 secret。

注册示意（factory 返回实现该接口的服务商对象，Validate 不应执行网络写操作）：

```go
plugin.RegisterDNSProviderV2("mydns", plugin.DNSProviderRegistration{
    Factory: factory,
    Validate: validateConfig,
    Info: plugin.DNSProviderInfo{
        Capabilities: []plugin.DNSProviderCapability{plugin.DNSCapabilityHTTPS},
    },
})
```

通过 `litegate build --with your-module/mydns -o litegate` 编入插件后，`auto_cert.dns_providers[].type` 填注册名（如 mydns），ECH 的 dns_provider 填该配置项的 name。沿用普通 ECH 配置，KV/storage 仍配置在主 ech 块，不传给插件。未声明能力或声明后未实现接口都会被拒绝。

可编译示例见 [memory DNS 插件](https://github.com/jamesleeon/LiteGate/blob/master/examples/plugins/dns/memory/memory.go)，展示所有权检查、更新与撤回；该示例仅内存存储，不会修改权威 DNS，不适用于生产发布。部署与客户端验证见 [ECH 配置指南](user/06-certificates/ech.md)。

> 本文教你如何为 LiteGate 编写自定义 **DNS Provider** 插件——接管两件事：**ACME 证书签发的 DNS-01 质询**（增删 TXT 记录）与 **动态 DNS（DDNS）同步**（把本机 IP 写到 A/AAAA 记录）。
>
> 适合场景：你用的 DNS 服务商不在内置清单里（内置：阿里云 / Cloudflare / 腾讯云 / 华为云），或你想用自己的 DNS API / 内部 IPAM / 私有 DNS 服务来完成证书校验与 DDNS。
>
> 契约已开放到公共包 [`github.com/jamesleeon/LiteGate/pkg/plugin`](https://github.com/jamesleeon/LiteGate/blob/master/pkg/plugin)，**第三方可在独立仓库编写并编译进去**。通用插件（Action / Middleware / LoadBalancer）见 [plugin-authoring-guide.md](plugin-authoring-guide.md)；IDS 鉴权插件见 [ids-provider-plugin-guide.md](ids-provider-plugin-guide.md)；DDNS 本身的使用见 [user/06-certificates/ddns.md](user/06-certificates/ddns.md)。

---

## 一、核心思想：一个名字、两种能力

LiteGate 把 DNS 操作抽象成一个**带名字的 Provider**。你的插件注册一个名字（如 `"mydns"`），用户在 `auto_cert.dns_providers[].type` 里引用它。一个 Provider 可以提供两种能力，**按需各自实现，互不强制**：

| 能力 | 接口 | 干什么 | 何时被调用 |
|---|---|---|---|
| **证书 DNS-01**（读写 TXT） | `plugin.CertDNSProviderV2` | ACME 质询时增删已经由宿主计算好的 TXT 记录 | 证书签发 / 续期时 |
| **DDNS 同步**（写 A/AAAA） | `plugin.DDNSProvider` | 确保最新 IP 存在于域名的 A / AAAA RRset | DDNS 周期同步 / IP 变化时 |

两者都建立在一个 **marker 接口** `plugin.DNSProvider`（只有 `GetName()`）之上。新证书插件应实现 `CertDNSProviderV2`；旧的 `CertDNSProvider` 保持兼容。核心会在配置加载期根据 V2 注册元数据检查用途与能力。

> DNS Provider 解决的是“如何调用不同域名服务商的 DNS API”。证书签发仍由 LiteGate 的 ACME 客户端负责。Let's Encrypt、ZeroSSL、Google 或其它标准 ACME CA 可通过内置选项或 `ca_provider: custom + acme_url` 使用；非 ACME 的私有签发 API 不属于 DNS Provider，当前也没有开放 Certificate Issuer 插件接口。

> 内置 provider 使用内部注册表，第三方插件使用公共注册表；两者最终汇入相同的证书/DDNS 能力适配路径，名称冲突会被统一阻止。

---

## 二、接口契约（`pkg/plugin/dns.go`）

全部定义在 [pkg/plugin/dns.go](https://github.com/jamesleeon/LiteGate/blob/master/pkg/plugin/dns.go)：

```go
// marker：所有 DNS 插件的基接口
type DNSProvider interface {
	GetName() string // provider 的唯一标识
}

// 推荐的 ACME DNS-01 V2 契约。FQDN 和 Value 已由宿主按 ACME 标准推导；
// 插件只负责调用服务商 API，不能把 KeyAuthorization 原文写进 TXT。
type CertDNSProviderV2 interface {
	DNSProvider
	PresentDNS01(ctx context.Context, challenge DNS01Challenge) error
	CleanupDNS01(ctx context.Context, challenge DNS01Challenge) error
}

type DNS01Challenge struct {
	Domain           string
	FQDN             string // 如 _acme-challenge.example.com.
	Value            string // 应写入 TXT 的 SHA-256/Base64URL 结果
	Token            string
	KeyAuthorization string // 仅供少数高级场景，不要直接写入 TXT
}

// 能力二：动态 DNS（A/AAAA 同步）
type DDNSProvider interface {
	DNSProvider
	Sync(ctx context.Context, domain string, ip string) error // 幂等追加 RRset 成员，不覆盖其它节点
}
```

外加三个**可选接口**（实现才生效，核心用类型断言探测）：

```go
// 自定义 DNS-01 传播等待逻辑（不实现则用 lego 默认的权威 NS 轮询）
type DNSPropagationChecker interface {
	WaitForPropagation(ctx context.Context, domain, value string) error
}

// 自定义 DNS-01 传播超时（不实现则默认 总时长 2min / 轮询间隔 10s）
type DNSOptionalTimeout interface {
	GetTimeout() (totalTime, checkInterval time.Duration)
}

// 自定义记录同步路由（DDNS 写记录时优先于 DDNSProvider.Sync 被调用，可直接控制 recordType）
type DNSSyncRecordRouter interface {
	SyncRecord(ctx context.Context, domain, recordType, value string) error
}

// 提前校验 provider 自定义配置；老插件可以不实现
type DNSConfigValidator interface {
	ValidateConfig(config map[string]string) error
}

// 描述能力和配置字段，供文档、Dashboard、预检工具使用
type DNSProviderDescriptor interface {
	Describe() DNSProviderInfo
}

// 可选的 API 连通性 / 凭证健康检查；当前由显式预检工具调用，
// 普通启动校验不会主动联网
type DNSHealthChecker interface {
	CheckHealth(ctx context.Context) error
}

// 释放 SDK Client、Transport、后台任务等长生命周期资源
type DNSCloser interface {
	Close(ctx context.Context) error
}
```

**推荐的 V2 注册函数**：

```go
func RegisterDNSProviderV2(name string, registration DNSProviderRegistration) error

type DNSProviderRegistration struct {
	Factory  DNSProviderFactoryWithDependencies
	Validate func(config map[string]string) error // 加载期纯校验，不创建运行实例
	Info     DNSProviderInfo                      // 必须声明支持的能力
}
```

`RegisterDNSProvider` 和 `RegisterDNSProviderWithDependencies` 继续兼容。旧注册无法在不创建临时实例的情况下判断能力，宿主会在配置预检时创建并随即关闭临时实例；新插件应使用 V2。

---

## 三、写一个 DNS Provider 插件

### 捷径：服务商已在 lego 里（推荐）

[lego](https://go-acme.github.io/lego/dns/) 已内置 180 多家 DNS 服务商（VegaDNS、DNSPod、Route 53、GoDaddy……）。如果你的服务商在里面，用 [`pkg/plugin/legodns`](https://github.com/jamesleeon/LiteGate/blob/master/pkg/plugin/legodns) 一次注册即可，不用自己调 API、算 TXT 记录：

```go
package vegadns

import (
	"github.com/go-acme/lego/v5/providers/dns/vegadns"
	"github.com/jamesleeon/LiteGate/pkg/plugin/legodns"
)

func init() {
	legodns.MustRegister("vegadns", legodns.Registration{
		Required: []string{"url", "api_key", "api_secret"}, // 配置加载期（litegate -t）就校验
		New: func(cfg map[string]string) (legodns.ChallengeProvider, error) {
			c := vegadns.NewDefaultConfig()
			c.BaseURL, c.APIKey, c.APISecret = cfg["url"], cfg["api_key"], cfg["api_secret"]
			return vegadns.NewDNSProviderConfig(c)
		},
	})
}
```

`legodns` 自动完成：能力声明（`cert_dns01`）与 Manifest、必填项校验、把 lego 的 `Timeout()` 透传为传播超时（VegaDNS 默认 12 分钟，若不透传会被 2 分钟默认值截断）、构造错误归类为 `invalid_config`。它按方法集结构化匹配、**不 import lego**，插件自己选 lego 版本。完整示例见 [examples/plugins/dns/vegadns](https://github.com/jamesleeon/LiteGate/blob/master/examples/plugins/dns/vegadns)。

服务商不在 lego 里、或要同时支持 DDNS 时，按下面的步骤直接实现接口。

### 第 1 步：实现接口 + 注册

下面是一个**同时实现证书 DNS-01 与 DDNS** 的最小骨架。只需要其中一种能力时，删掉另一组方法即可。

```go
package mydns

import (
	"context"
	"fmt"

	"github.com/jamesleeon/LiteGate/pkg/plugin"
	"github.com/rs/zerolog/log"
)

// providerName 是用户写在 YAML dns_providers[].type 里的名字，不能与内置名重名。
const providerName = "mydns"

type provider struct {
	apiKey    string
	apiSecret string
}

// GetName 实现 marker 接口 plugin.DNSProvider
func (p *provider) GetName() string { return providerName }

// --- 能力一：证书 DNS-01（实现 plugin.CertDNSProviderV2）---

func (p *provider) PresentDNS01(ctx context.Context, challenge plugin.DNS01Challenge) error {
	return p.upsertTXT(ctx, challenge.FQDN, challenge.Value)
}

func (p *provider) CleanupDNS01(ctx context.Context, challenge plugin.DNS01Challenge) error {
	return p.removeTXT(ctx, challenge.FQDN, challenge.Value)
}

// --- 能力二：DDNS（实现 plugin.DDNSProvider）---

func (p *provider) Sync(ctx context.Context, domain string, ip string) error {
	// 确保 ip 已存在于 domain 的 A/AAAA RRset；不能覆盖其它节点的地址。
	// 记录类型由 ip 是 IPv4 还是 IPv6 决定，重复调用必须幂等。
	return p.ensureAddrMember(ctx, domain, ip)
}

// init：包被导入时自动注册
func init() {
	err := plugin.RegisterDNSProviderV2(providerName, plugin.DNSProviderRegistration{
		Factory: func(config map[string]string, deps *plugin.Dependencies) (plugin.DNSProvider, error) {
			return &provider{apiKey: config["api_key"], apiSecret: config["api_secret"]}, nil
		},
		Validate: func(config map[string]string) error {
			if config["api_key"] == "" || config["api_secret"] == "" {
				return fmt.Errorf("api_key and api_secret are required")
			}
			return nil
		},
		Info: plugin.DNSProviderInfo{
			DisplayName: "My DNS",
			Capabilities: []plugin.DNSProviderCapability{
				plugin.DNSCapabilityCertDNS01, plugin.DNSCapabilityDDNS,
			},
		},
	})
	if err != nil {
		log.Error().Err(err).Str("plugin", providerName).Msg("register DNS provider failed")
	}
}

// 下面是示意，替换成你的 DNS API 调用
func (p *provider) upsertTXT(ctx context.Context, fqdn, value string) error  { /* ... */ return nil }
func (p *provider) removeTXT(ctx context.Context, fqdn, value string) error  { /* ... */ return nil }
func (p *provider) ensureAddrMember(ctx context.Context, domain, ip string) error { /* ... */ return nil }
```

### 第 2 步：配置 —— 在 `auto_cert.dns_providers` 里引用

```yaml
auto_cert:
  enabled: true
  email: admin@example.com
  dns_providers:
    - name: my-cloud              # 逻辑名（被 domains 路由引用，可与 type 不同）
      type: mydns                 # ← 你注册的插件名 plugin.RegisterDNSProviderV2("mydns", …)
      enabled: true
      domains: ["*.example.com"]  # 该 provider 负责签发证书的域名（DNS-01）
      config:                     # ← 整个 map 原样传给工厂的 config 参数
        api_key: "AKxxxx"
        api_secret: "yyyy"
        propagation_wait: "60s"   # 可选：DNS-01 传播等待（见 §四）
      ddns:                       # 可选：开启 DDNS 同步
        enabled: true
        sync_a: true
        domains: ["home.example.com"]
```

- **证书 DNS-01**：当某域名匹配 `dns_providers[].domains` 时，核心用对应 provider 走 DNS-01 质询（新插件实现 `CertDNSProviderV2`，V1 仍兼容）。
- **DDNS**：当 `ddns.enabled: true` 时，周期 DDNS 任务会对 `ddns.domains` 调 `Sync`（要求实现 `DDNSProvider`）。`DNSSyncRecordRouter` 只作用于下文说明的证书管理器记录同步路径。
- `config` 这一整个 `map[string]string` 原样进你的工厂——所有自定义参数都放这里。

---

## 四、可选能力详解

### 4.1 自定义传播等待 / 超时（证书 DNS-01）

默认行为：lego 会向权威 NS 轮询，确认 TXT 记录已传播后再让 CA 校验；总时长默认 2 分钟、间隔 10 秒。你可以两种方式干预：

- **配置级**（无需写代码）：在 `config` 里设 `propagation_wait: "60s"`、`skip_propagation_check: "true"`、`disable_complete_propagation: "true"`、`recursive_nameservers: "1.1.1.1,8.8.8.8"`（核心在 [internal/cert/interface.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/cert/interface.go) 的 `buildDNSChallengeOptions` 里解析）。
- **代码级**：实现 `DNSPropagationChecker` 完全接管等待逻辑；实现 `DNSOptionalTimeout` 改总时长/间隔。

> 所有方法收到的 `ctx` 就是这次 ACME 订单的 context：进程关闭或集群里失去证书锁时会被取消，请把它传给服务商 SDK 的 HTTP 调用。删除记录时宿主会换成一个不随订单取消的 context，保证 TXT 记录被清理。
>
> `auto_cert.propagation_dns` 是进程级的递归解析器（lego v5 起全局共享）；某个 provider 的 `recursive_nameservers` 由 LiteGate 针对该 provider 单独校验。

```go
func (p *provider) GetTimeout() (time.Duration, time.Duration) {
	return 5 * time.Minute, 15 * time.Second // 慢速 DNS 可调大
}
```

### 4.2 自定义记录同步路由（`DNSSyncRecordRouter`）

LiteGate 有两条写 A/AAAA 记录的路径，对你的接口要求不同：

- **独立的 DDNS 周期任务**（`auto_cert.dns_providers[].ddns`）：走 [internal/ddns/provider.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/ddns/provider.go) 的 `NewProvider`，**直接调 `DDNSProvider.Sync(ctx, domain, ip)`**，记录类型由 `ip` 是 IPv4/IPv6 决定。这条路径只认 `DDNSProvider`。
- **证书管理器的记录同步**（如服务 Host 自动同步等，经 `CertificateManager.SyncRecordWithProvider`）：经 `externalCertProviderAdapter.SyncRecord` 桥接，此处**优先**找 `DNSSyncRecordRouter.SyncRecord`（你能拿到明确的 `recordType`），找不到再回退到 `DDNSProvider.Sync`。

需要在第二条路径上精细控制记录类型时，实现 `DNSSyncRecordRouter`：

```go
func (p *provider) SyncRecord(ctx context.Context, domain, recordType, value string) error {
	// recordType 已由核心算好（IPv4→"A"，IPv6→"AAAA"）
	return p.api.SetRecord(ctx, domain, recordType, value)
}
```

---

## 五、编译进二进制（用户拥有 main）

和其它插件一样，走「用户拥有 main」——在你**自己的仓库**里建一个 `main`，空导入插件包再调 `litegate.Run()`：

```go
// main.go
package main

import (
	"log"

	"github.com/jamesleeon/LiteGate/pkg/litegate"

    _ "your-module/mydns" // ← init() 里 RegisterDNSProviderV2
)

func main() {
	if err := litegate.Run(); err != nil {
		log.Fatalf("litegate exited: %v", err)
	}
}
```

`go build` 即得带插件的网关。也可用一键构建：

```bash
# 已发布版本
litegate build --with your-module/mydns@v1.2.3 -o litegate

# 本地开发；右侧目录是插件 go.mod 所在目录
litegate build --with your-module/mydns=../your-module -o litegate
```

最小复制模板见 [examples/plugin-template](https://github.com/jamesleeon/LiteGate/blob/master/examples/plugin-template)，覆盖 DNS Provider V2 的可编译内存实现见 [examples/plugins/dns/memory](https://github.com/jamesleeon/LiteGate/blob/master/examples/plugins/dns/memory)。内存实现不会修改权威 DNS，只用于学习与测试。

> 也可以在本仓库内 in-tree 开发（把包放仓库里、在 [cmd/litegate/plugins.go](https://github.com/jamesleeon/LiteGate/blob/master/cmd/litegate/plugins.go) 空导入），但**独立仓库 + 用户拥有 main 是推荐方式**。

---

## 六、必须注意的事（踩坑清单）

1. **能力按需实现，但必须如实声明**。V2 的 `Info.Capabilities` 会在加载期与证书/DDNS 用途核对；运行实例仍必须实现相应接口。

2. **新插件使用 `RegisterDNSProviderV2`**。工厂拿到配置副本与 `*plugin.Dependencies`；纯配置检查放 `Registration.Validate`，不要在校验函数中联网、启动 goroutine 或修改全局状态。

3. **不能覆盖内置名**。`RegisterDNSProvider("aliyun", …)` 等会返回 error。内置名：`aliyun` / `cloudflare` / `tencent` / `tencentcloud` / `huawei` / `huaweicloud`。取个不冲突的名字。

4. **尊重 `ctx` 取消**。`AddTXTRecord` / `DeleteTXTRecord` / `Sync` 拿到的 `ctx` 会在网关关机或质询超时时取消——你的 HTTP 调用要带上它，别用 `context.Background()`，否则关机时会卡住或泄露。

5. **TXT 必须使用 `challenge.Value`**。它不是 `KeyAuthorization` 原文。删除时按 FQDN 和 Value 精确清理，避免误删并发质询的其它 TXT。

6. **DDNS 周期任务只调 `Sync`**。`auto_cert.dns_providers[].ddns` 驱动的周期同步只会调 `DDNSProvider.Sync(ctx, domain, ip)`，记录类型由 `ip` 是 IPv4/IPv6 决定——这条路径上实现 `DNSSyncRecordRouter` **不会**被调用。`DNSSyncRecordRouter.SyncRecord`（拿到现成 `recordType`）仅作用于证书管理器的记录同步路径（见 §4.2）。

7. **`config` 值都是 string，且是副本**。时长写 `"60s"` 自己 `time.ParseDuration`，开关写 `"true"` 自己判断。修改该 map 不会改变宿主配置，但也不应把秘密写入日志。

8. **DNS-01 通配符证书必须用 DNS Provider**。`*.example.com` 这类通配符证书无法用 HTTP-01，必须有一个实现了 `CertDNSProviderV2`（或兼容 V1）的 provider 负责该域名。

---

## 七、生命周期与分发（机制说明）

```
程序启动
  └─ 插件包 init() → plugin.RegisterDNSProviderV2("mydns", registration)
     （RegisterDNSProvider / WithDependencies 作为 V1 兼容）
配置加载
  └─ 检查逻辑名/域名冲突 → V2 Validate → 校验声明能力
     （V1 创建并关闭临时实例完成兼容预检；litegate -t 同样执行）
证书签发/续期（某域名匹配 dns_providers[].domains）
  └─ cert.GetCertProvider(type, config)
       ├─ 内置注册表命中？→ 用内置
       └─ 否 → 公共注册表 factory(config, deps) → 断言 CertDNSProviderV2/V1 → 适配为内部 CertProvider
            └─ lego 调 AddTXTRecord → 等待传播 → CA 校验 → DeleteTXTRecord
DDNS 周期同步（ddns.enabled，周期/IP 变化）
  └─ ddns.NewProvider(type, config) → 断言 DDNSProvider → Sync(ctx, domain, ip)
证书管理器记录同步（如服务 Host 自动同步，SyncRecordWithProvider）
  └─ cert.GetSyncProvider → 适配器优先 DNSSyncRecordRouter.SyncRecord，回退 DDNSProvider.Sync
停止 / 重载退出
  └─ 等待在途任务 → DNSCloser.Close(ctx)
```

- 内置 provider 通过内部 `RegisterProvider` 注册时，会**先反查公共注册表防重名，再把名字保留进公共注册表**（见 [internal/cert/interface.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/cert/interface.go) 与 [internal/ddns/registerprovider.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/ddns/registerprovider.go)）。
- 第三方 provider 经 `externalCertProviderAdapter`（[internal/cert/interface.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/cert/interface.go)）桥接到内部 `CertProvider`：`WaitForPropagation` 探测 `DNSPropagationChecker`、`SyncRecord` 优先 `DNSSyncRecordRouter` 再回退 `DDNSProvider.Sync`、`GetTimeout` 探测 `DNSOptionalTimeout`（缺省 2min/10s）。

---

## 速查表

| 我要… | 做法 |
|---|---|
| 给新 DNS 服务商加证书签发 | 实现 `plugin.CertDNSProviderV2`，用 `plugin.RegisterDNSProviderV2` 注册，配 `dns_providers[].type` + `domains` |
| 给新 DNS 服务商加 DDNS | 实现 `plugin.DDNSProvider`，用 `plugin.RegisterDNSProviderV2` 注册并声明 `DNSCapabilityDDNS` |
| 同时支持证书 + DDNS | 一个 provider 同时实现两组接口，并在 `Info.Capabilities` 声明两项 |
| 自定义传播等待 | 实现 `plugin.DNSPropagationChecker`，或在 `config` 配 `propagation_wait` 等 |
| 自定义传播超时 | 实现 `plugin.DNSOptionalTimeout` |
| 证书管理器记录同步精确控制记录类型 | 实现 `plugin.DNSSyncRecordRouter`（拿到现成 `recordType`，见 §4.2） |
| 配置错误提前失败 | 在 `DNSProviderRegistration.Validate` 校验；`litegate -t` 与启动都会调用 |
| 暴露插件元数据 | 实现 `plugin.DNSProviderDescriptor`，供文档/UI/预检工具使用 |
| 支持资源释放 | 实现 `plugin.DNSCloser` |
| 读插件配置 | 工厂参数 `config map[string]string`（值均为 string） |
| 编进二进制 | 自建 `main`，空导入插件包 + `litegate.Run()`，`go build`，或 `litegate build --with` |
