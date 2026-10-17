# IDS WASM Plugin Development Guide

> **Experimental, optional feature:** the WASM host, ABI and hot reload have unit tests with synthetic modules, but the repository's Rust example has not entered end-to-end smoke testing as a real Rust build artifact. It is therefore not part of the current stable delivery promise; build and accept it with a real Rust/WASM toolchain before production use. Default builds don't include it.

LiteGate lets IDS Providers be written in Rust or any language that compiles to WebAssembly. WASM plugins are loaded and hot-reloaded as separate files without recompiling LiteGate. Native Go IDS Providers stay supported.

> **Prerequisite: WASM support is compiled on demand.** To keep the binary small, the wazero runtime (about +4 MB) is **not** compiled in by default. Build with the `wasmids` build tag:
>
> ```bash
> go build -tags wasmids ./cmd/litegate
> # or via the Makefile: make all-wasm / make linux-wasm / make windows-wasm ...
> ```
>
> A binary without the tag ignores `ids_wasm.enabled: true` and logs a warning. For the WASM capability boundary (**computation only, no I/O**) see [Choosing Go vs WASM](ids-go-vs-wasm.md).

## Enabling

```yaml
ids_wasm:
  enabled: true
  dir: plugins/ids
  watch: true
```

Each YAML manifest in the directory registers one IDS Provider. LiteGate only scans `kind: ids` and does not turn other plugin types into WASM.

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

`memory_pages` are 64 KiB each. The module must be in the manifest's directory or a subdirectory. Only request headers the manifest declares are passed; query and body are not passed by default.

## ABI v1

The module must export:

```text
alloc(len: i32) -> i32
evaluate(input_ptr: i32, input_len: i32) -> i64
```

`evaluate` returns the output address in the high 32 bits and the output length in the low 32 bits. Input and output are UTF-8 JSON.

Input:

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

Forward output:

```json
{
  "abi_version": "litegate.ids/v1",
  "action": "forward",
  "headers": {"X-Identity-Ref": ["subject-1"]},
  "discovery": {"selector": {"match": {"tenant": "acme"}}},
  "rate_limit": {"key": "subject-1", "requests_per_second": 20}
}
```

Respond output:

```json
{
  "abi_version": "litegate.ids/v1",
  "action": "respond",
  "response": {"status": 401}
}
```

The response body is a JSON byte array field, so it uses Base64 under standard JSON `[]byte` rules. Decisions returned by WASM still go through LiteGate's header allow list, status code, routing and rate-limit validation.

## Host API

Modules can import from `litegate_ids`:

```text
config_version() -> i64
config_get(key_ptr: i32, key_len: i32, out_ptr: i32, out_cap: i32) -> i32
log(level: i32, ptr: i32, len: i32)
```

`config_get` can only read keys authorized by the manifest's `config_prefixes` and returns the actual length; `-1` means not found, `-2` not permitted, `-3` output buffer too small, `-4` invalid memory range. Plugins cannot enumerate configuration, read the host environment, access the file system or open network connections.

When the shared configuration file changes, `config_version` increases and the next `config_get` reads the new snapshot immediately. Plugins that cache configuration or connections should compare versions and rebuild.

## Hot reload

LiteGate watches manifests and `.wasm` files. On change it:

1. debounces and reads the new version;
2. validates the manifest, ABI and paths;
3. compiles the new module;
4. switches atomically after a successful compile;
5. lets requests already started finish on the old module;
6. releases the old module when nothing references it.

An invalid new module never replaces the working version. Deleting a manifest disables its WASM Provider.

The Rust example source is in [`examples/wasm-ids-rust`](../../examples/wasm-ids-rust). It illustrates the ABI and is not currently an artifact verified end to end by the release pipeline.
