# IDS WASM 插件开发指南

> **实验性、可选功能：** 当前 WASM 宿主、ABI 和热加载有合成模块单元测试，但仓库中的 Rust 示例尚未作为真实 Rust 编译产物进入端到端冒烟测试。因此它不属于当前稳定交付承诺；生产环境使用前必须用实际 Rust/WASM 工具链完成构建和验收。默认构建不包含此功能。

LiteGate 允许 IDS Provider 使用 Rust 或其他可编译到 WebAssembly 的语言开发。WASM 插件作为独立文件加载和热更新，不需要重新编译 LiteGate。原生 Go IDS Provider 保持兼容。

> **前提：WASM 支持需按需编译。** 为控制体积，wazero 运行时（约 +4MB）默认**不**编入二进制。需要用 `wasmids` build tag 构建：
>
> ```bash
> go build -tags wasmids ./cmd/litegate
> # 或用 Makefile：make all-wasm / make linux-wasm / make windows-wasm ...
> ```
>
> 未带该 tag 的二进制即使配置了 `ids_wasm.enabled: true` 也会忽略并打印一条 warn 日志。WASM 能力边界（**仅计算、无 I/O**）见 [Go vs WASM 选型](ids-go-vs-wasm.md)。

## 启用

```yaml
ids_wasm:
  enabled: true
  dir: plugins/ids
  watch: true
```

目录中的每个 YAML manifest 注册一个 IDS Provider。LiteGate 只扫描 `kind: ids`，不会把其他插件类型 WASM 化。

```yaml
name: company-ids
kind: ids
abi: litegate.ids/v1
module: company-ids.wasm

request:
  headers: [Authorization, X-App-ID, X-Signature]
  query: false
  body: false
  max_body_bytes: 65536

config_prefixes:
  - shared.identity
  - providers.company-ids

limits:
  timeout_ms: 100
  memory_pages: 512
  max_input_bytes: 1048576
  max_output_bytes: 262144
```

`memory_pages` 每页为 64 KiB。模块必须与 manifest 位于同一目录或其子目录。请求 Header 只传递 manifest 明确声明的字段；Query 和 Body 默认不传递。

## ABI v1

模块必须导出：

```text
alloc(len: i32) -> i32
evaluate(input_ptr: i32, input_len: i32) -> i64
```

`evaluate` 的返回值高 32 位为输出地址，低 32 位为输出长度。输入和输出均为 UTF-8 JSON。

输入：

```json
{
  "abi_version": "litegate.ids/v1",
  "request": {
    "method": "GET",
    "scheme": "https",
    "host": "api.example.com",
    "path": "/orders",
    "headers": {"Authorization": ["Bearer token"]}
  },
  "options": {"policy": "orders.read"},
  "config_version": 12
}
```

Forward 输出：

```json
{
  "abi_version": "litegate.ids/v1",
  "action": "forward",
  "headers": {"X-Identity-Ref": ["subject-1"]},
  "route": {"selector": {"tenant": "acme"}},
  "rate_limit": {"key": "subject-1", "requests_per_second": 20}
}
```

Respond 输出：

```json
{
  "abi_version": "litegate.ids/v1",
  "action": "respond",
  "response": {"status": 401}
}
```

响应 Body 是 JSON 字节数组字段，因此按标准 JSON `[]byte` 规则使用 Base64。WASM 返回的 Decision 仍经过 LiteGate 原有的 Header 白名单、状态码、路由和限流校验。

## Host API

模块可从 `litegate_ids` 导入：

```text
config_version() -> i64
config_get(key_ptr: i32, key_len: i32, out_ptr: i32, out_cap: i32) -> i32
log(level: i32, ptr: i32, len: i32)
```

`config_get` 只能读取 manifest `config_prefixes` 授权的键，返回值为实际长度；`-1` 表示不存在，`-2` 表示无权限，`-3` 表示输出缓冲区不足，`-4` 表示内存范围无效。插件不能枚举配置、读取宿主环境、访问文件系统或直接打开网络连接。

共享配置文件更新后，`config_version` 会增加，下一次 `config_get` 立即读取新快照。插件如果缓存了配置或连接，应自行比较版本并重建资源。

## 热加载

LiteGate 监听 manifest 和 `.wasm` 文件，变更后：

1. 防抖并读取新版本；
2. 校验 manifest、ABI 和路径；
3. 编译新模块；
4. 编译成功后原子切换；
5. 已开始的请求继续使用旧模块；
6. 旧模块没有引用后释放。

新模块无效时不会替换当前可用版本。删除 manifest 会停用对应 WASM Provider。

Rust 示例源码见 [`examples/wasm-ids-rust`](https://github.com/jamesleeon/LiteGate/blob/master/examples/wasm-ids-rust)。它用于说明 ABI，当前不是经过发布流水线端到端验证的制品。
