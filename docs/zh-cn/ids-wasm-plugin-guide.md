# 实验性 IDS WASM

默认不编译 WASM；使用 wasmids 标签构建后，ids_wasm.enabled/dir/watch 控制加载。未带标签的二进制忽略启用配置并告警。仅扫描 kind: ids 的 manifest；ABI 为 litegate.ids/v1，模块路径限定同目录或子目录。

manifest 显式选择请求 headers/query/body，Query/Body 默认不传递，设置 max_body_bytes、输入输出大小、timeout_ms 与 memory_pages（每页 64 KiB）。宿主不提供通用外部 I/O；不要把 WASM 当作网络沙箱中可任意访问资源的 Go Provider。

ABI/热加载当前由合成模块测试覆盖。examples/wasm-ids-rust 不是已经完成真实 Rust 产物发布验收的承诺。生产评估需要用实际工具链验证导出函数、内存边界、取消、无效输出与热替换。

```bash
go build -tags wasmids ./cmd/litegate
```

```yaml
ids_wasm:
  enabled: true
  dir: plugins/ids
  watch: true
```

## 相关文档与代码

- [Rust example](../../examples/wasm-ids-rust/README.md)
- [Host](../../internal/wasmids)
- [Selection](ids-go-vs-wasm.md)
