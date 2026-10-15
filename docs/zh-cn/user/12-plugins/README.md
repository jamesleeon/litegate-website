# 插件体系总览

LiteGate 插件是普通 Go 包，通过编译期注册接入，不使用动态 .so。第三方仓库依赖 pkg/plugin 公共契约与 pkg/litegate 运行入口，无需访问 internal 或 fork 网关。构建仍受所用依赖的操作系统、CGO 和 Go 版本约束，不能宣称任意插件都完全跨平台。

扩展点包括 Action、Middleware、KV、LoadBalancer、DNS、IDS、Discovery、Ingress 和 Template Func。Manifest 提供版本、能力和配置示例；CLI 的注册清单不能替代运行时健康检查。

中间件统一注册 Descriptor、Validate、Active 与 Factory，运行实现 Wrap；结构化配置严格 Decode，使用 JSON 字段标签。IDS 的 WASM 是独立实验性选项，默认不编译，不能把所有插件说成可热加载二进制。

## 相关文档与代码

- [Build and CLI](build-and-cli.md)
- [Configuration](configuration.md)
- [Authoring](authoring-guide.md)
