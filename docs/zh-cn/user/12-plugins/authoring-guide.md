# 插件开发契约

在独立 Go module 中依赖 pkg/plugin。注册时处理返回错误，选择不冲突的名称，通过 Manifest 声明版本与说明。不要覆盖内置保留类型，不依赖 internal 实现细节。

结构化 Config.Decode 使用 json 标签，拒绝未知字段；时长可使用 plugin.Duration。中间件实现 Wrap 并用 MiddlewareRegistration 声明 Descriptor 与必选 Validate，可选 Active/InlineConfig；校验与内联转换必须确定、无副作用且可并发。不要编写旧 Stage/Priority 注册接口。

使用 Dependencies 注入日志、发现与配置能力；实例可能并发调用，避免共享可变请求数据。按相应扩展点的 Start/Close 等可选生命周期接口释放资源，遵守 context 取消，不把业务拒绝当系统故障。

从 examples/plugin-template 和 examples/plugins 开始，完成注册、自定义二进制构建、配置预检和真实请求验证。Ingress、Discovery、IDS、DNS 有专门契约；WASM 仅为实验性 IDS 选项。

## 相关文档与代码

- [Public SDK](../../../../pkg/plugin)
- [Plugin template](../../../../examples/plugin-template/README.md)
- [Plugin examples](../../../../examples/plugins/README.md)
