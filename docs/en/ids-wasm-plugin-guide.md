# Experimental IDS WASM

WASM is excluded from default builds. With the wasmids tag, ids_wasm.enabled/dir/watch controls loading. Binaries without the tag ignore enablement and warn. Only kind: ids manifests are scanned; ABI is litegate.ids/v1 and module paths stay within the manifest directory/subdirectories.

Manifests explicitly select request headers/query/body. Query/Body are excluded by default. Bound max_body_bytes, input/output sizes, timeout_ms and memory_pages (64 KiB per page). The host offers no general external I/O; WASM is not a Go Provider with arbitrary network access.

Synthetic modules currently cover ABI/hot-loading tests. examples/wasm-ids-rust is not a promise of validated real Rust release artifacts. Production evaluation requires the actual toolchain and checks for exports, memory bounds, cancellation, invalid outputs and hot replacement.

```bash
go build -tags wasmids ./cmd/litegate
```

```yaml
ids_wasm:
  enabled: true
  dir: plugins/ids
  watch: true
```

## Related documentation and code

- [Rust example](../../examples/wasm-ids-rust/README.md)
- [Host](../../internal/wasmids)
- [Selection](ids-go-vs-wasm.md)
