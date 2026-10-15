# IDS: choosing Go or WASM

Go Providers are the stable integration path for DB, Redis, HTTP and notification clients. WASM is an experimental optional build, limited to computation on host-provided inputs without general network/database I/O.

WASM requires the wasmids build tag and is inactive in default builds. Synthetic modules test host ABI, loading and protection; Rust examples still require real-toolchain builds and end-to-end acceptance. Prefer Go for external dependencies, complex lifecycles and production delivery. Evaluate WASM for constrained computation without promising all plugin types can use it.

## Related documentation and code

- [WASM guide](ids-wasm-plugin-guide.md)
- [Go authoring](ids-provider-plugin-guide.md)
