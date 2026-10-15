# IDS：Go 与 WASM 选型

Go Provider 是稳定集成路径，可管理 DB、Redis、HTTP 和通知。WASM 为实验性可选构建，只做宿主提供输入上的计算，不提供通用网络/数据库 I/O。

WASM 需要 wasmids 构建标签；默认构建不会启用。宿主 ABI、加载与保护有合成模块测试，Rust 示例仍需真实工具链构建及端到端验收。外部依赖查询、复杂生命周期或生产交付优先使用 Go；受限纯计算可以评估 WASM，但不能承诺当前通用插件都可转成 WASM。

## 相关文档与代码

- [WASM guide](ids-wasm-plugin-guide.md)
- [Go authoring](ids-provider-plugin-guide.md)
