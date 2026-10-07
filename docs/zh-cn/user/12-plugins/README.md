# LiteGate 插件体系总览

LiteGate 采用 **编译期注册表（Compile-Time Registry）** 插件架构（类似 Caddy / Traefik 的静态集成模式）。
开发者、架构师与第三方团队无需 Fork 或修改 LiteGate 核心源码，即可在独立代码仓库中编写插件，并编译出专属于企业的定制网关二进制。

---

## 核心设计哲学

### 1. 为什么坚决采用编译期注册，而非动态加载 (`.so`)？

许多开发者会好奇为什么 LiteGate 不使用 Go 官方的 `plugin` 动态链接库（`.so`）：

| 维度 | Go `plugin` 动态加载 (`.so`) | LiteGate 编译期注册表 (Compile-Time) |
| :--- | :--- | :--- |
| **跨平台支持** | ❌ 仅支持 Linux/macOS，**完全不支持 Windows** | ✅ 完美跨平台（Linux、Windows、macOS、ARM、FreeBSD） |
| **依赖与 ABI 稳定性**| ❌ 极度脆弱：主程序与 `.so` 的 Go 版本、依赖包版本、编译参数必须 100% 字节级一致，否则运行时直接 SIGSEGV 崩溃 | ✅ 构建期 Go 静态链接，编译器保证类型与符号绝对安全，永不发生运行时 ABI 冲突 |
| **运行时性能** | ⚠️ CGO 跨边界调用与动态符号解析带来开销 | ✅ **零运行时性能开销**（Zero-Cost Abstraction），等同于原生调用 |
| **运维与交付** | ❌ 交付时需要携带一堆 `.so` 动态库文件，存在环境污染与加载缺失风险 | ✅ **单静态二进制交付**（Single Static Binary），复制即用，符合云原生标准容器化规范 |

> [!NOTE]
> 对于部分特殊安全治理场景（如轻量级规则脚本），LiteGate 额外提供了受限的 WASM ABI 选项（详见 [IDS WASM 说明](../../ids-wasm-plugin-guide.md)）；但通用数据流核心均采用编译期静态注册。

### 2. 两层契约与解耦设计

为了让第三方插件生态与核心解耦，LiteGate 严格划分了两层契约：

```
┌─────────────────────────────────────────────────────────────────┐
│                     LiteGate 核心运行时                         │
│  internal/action · internal/router · internal/middleware ...   │
│  (包含 heavy-weight 内部类型: loader.Site, proxy.Pool 等)       │
└──────────────────────────────▲──────────────────────────────────┘
                               │ 窄适配器层 (Narrow Adapters)
┌──────────────────────────────┴──────────────────────────────────┐
│              公共门面契约 (Public Contract API)                 │
│              github.com/jamesleeon/LiteGate/pkg/plugin          │
│  - 纯窄接口 (Context, ActionConfig, DiscoveryClient, etc.)     │
│  - 注入能力依赖: Dependencies (Logger, Discovery, Config)        │
│  - 统一元数据: Manifest (版本, 描述, 能力标记)                  │
└──────────────────────────────▲──────────────────────────────────┘
                               │ 静态注册 (Blank Import)
┌──────────────────────────────┴──────────────────────────────────┐
│              外部插件 / 企业私有定制包                          │
│  github.com/your-org/litegate-plugins (独立代码仓库)             │
└─────────────────────────────────────────────────────────────────┘
```

- **内部层 (`internal/...`)**：供网关内部模块高速调度。
- **公共契约层 ([`pkg/plugin`](file:///d:/ecp_source/LiteGate/pkg/plugin))**：面向所有外部开发者开放。只暴露精简的窄接口与结构体，核心内部重构永不破坏外部插件的 API 签名兼容性。

---

## 9 大插件扩展点全景矩阵

LiteGate 在请求生命周期的关键接缝处开放了 9 大扩展点，涵盖 L4 到 L7、控制面与数据面：

| # | 插件扩展类型 | 关键行为接口 | 核心注册函数 | 适用场景 |
|---|---|---|---|---|
| 1 | **Ingress** (入口拦截) | `IngressHandler` | `plugin.RegisterIngress` / `RegisterTypedIngress` | 在 Site 路由与规范化之前接管端口流量（如正向代理 HTTP CONNECT、特定协议隧道等） |
| 2 | **Middleware** (中间件) | `MiddlewareHandler` | `plugin.RegisterMiddleware` | 请求链上穿透加工（安全认证、请求改写、自定义审计、跨域控制等），支持 8 阶段精准编排 |
| 3 | **Action** (执行动作) | `Handler` | `plugin.RegisterAction` | 终结型请求处理与响应生成（如 NATS 消息发布、自定义渲染引擎、AI LLM 代理等） |
| 4 | **LoadBalancer** (负载均衡) | `LoadBalancer` | `plugin.RegisterLoadBalancer` | 自定义上游节点选择策略（如加权最小连接、一致性哈希、金丝雀权重分发等） |
| 5 | **Discovery Provider** (服务发现) | `DiscoveryProvider` | `plugin.RegisterDiscoveryProvider` | 接入非内置注册中心（如 Nacos、Eureka、Zookeeper、自研 CMDB），自动生成服务目录与路由 |
| 6 | **DNS Provider** (DNS 协议) | `CertDNSProviderV2` / `DDNSProvider` / `HTTPSDNSProvider` | `plugin.RegisterDNSProviderV2` | 自动化 ACME DNS-01 证书质询、动态公网 DDNS 域名解析、ECH 加密 ClientHello 的 HTTPS 记录发布 |
| 7 | **IDS Provider** (鉴权与治理) | `IDSProvider` | `plugin.RegisterIDSProvider` | 动作前跨 Action 统一安全治理（签名校验、Session 鉴权、机器人拦截、流量选择标签注入） |
| 8 | **KV Provider** (内容提供源) | `KVProvider` | `plugin.RegisterKVProvider` | 为 `serve` / `template` 动作提供动态数据流监听（如 Redis/etcd/S3 资产热推送） |
| 9 | **Template Func** (模板函数) | `template.FuncMap` | `plugin.RegisterTemplateFunc` / `RegisterTemplateFuncs` | 为网关内置 `template` 模板动作扩展业务专有函数（脱敏、加密、时间格式化等） |

---

## 内置标准插件

LiteGate 官方发行二进制默认编入了以下参考插件，它们均采用与第三方相同的公共 API 注册机制：

1. **`nats` (Action)**: 支持 HTTP 请求直接发布到 NATS JetStream 消息队列并等待应答（开箱即用）。
2. **`openapi_md5` (IDS)**: 兼容传统企业 API MD5 Body 签名防篡改验证。
3. **`forward_proxy` (Ingress)**: 企业级正向代理插件，支持 HTTP CONNECT、mTLS 客户端限制、Bcrypt 鉴权与目标 ACL。

---

## 查看二进制中的已编译插件

你可以在终端运行以下 CLI 命令，快速诊断当前 LiteGate 二进制中已编译并注册的插件：

```bash
# 1. 列出所有已编入的插件清单（含类型、名称、版本、API 契约）
litegate plugins list

# 2. 查看某个具体插件的元数据详情与标准配置示例
litegate plugins inspect ingress/forward_proxy
litegate plugins inspect action/nats

# 3. 运行插件健康度诊断，检查是否存在 Manifest 缺失或 API 版本漂移
litegate plugins doctor
```

此外，在 LiteGate 的 Web 可观测性 **Dashboard** 中，打开 **Compiled Plugins** 选项卡亦可直观查看已编译插件卡片，并一键复制其 YAML 配置示例。

---

## 本章导航

- **[构建与 CLI 工具](build-and-cli.md)**：掌握 `litegate build --with` 定制编译、`main.go` 源码空导入、`plugins` 诊断排错与 CI 自动化流水线。
- **[用户配置指南](configuration.md)**：学习如何在 `config.yaml` 全局配置与 `sites/*.yaml` 站点配置中优雅启用并调试各类插件。
- **[插件开发说明](authoring-guide.md)**：从零开始编写你的第一个 LiteGate 插件，包含 9 大扩展点的完整接口骨架、生命周期管理、配置校验、Panic 容错与并发避坑指南。
