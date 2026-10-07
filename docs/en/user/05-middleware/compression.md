# Compression (Smart Compression)

LiteGate incorporates a high-performance response compression middleware that dynamically negotiates the optimal encoding algorithm with incoming clients to minimize transmission bandwidth and accelerate loading times.

---

## 1. Supported Encoding Formats

| Algorithm | Content-Encoding | Compression Ratio | CPU Resource Impact |
| :--- | :--- | :--- | :--- |
| **Brotli** | `br` | ⭐⭐⭐⭐⭐ | Moderate |
| **Zstd** | `zstd` | ⭐⭐⭐⭐ | Low |
| **Gzip** | `gzip` | ⭐⭐⭐ | Low |

---

## 2. Activation Method

Compression negotiation is activated inside static site `serve` Action configurations:

```yaml
action:
  type: serve
  root: "./dist"
  compress: true     # Activates automated algorithm negotiation
```

---

## 3. Zero-CPU Pre-Compression Strategy

To completely eliminate the real-time CPU overhead of dynamic compression, LiteGate prioritizes a **pre-compression** pipeline:

1. **Host Directory Audit**: When a client requests `app.js`, the gateway first checks the physical disk for pre-compiled assets `app.js.br` (Brotli) or `app.js.zst` (Zstd).
2. **Immediate Passthrough**: If a matching pre-compressed file exists and the client's `Accept-Encoding` header supports the format, LiteGate streams the pre-compressed asset directly with the correct encoding headers.
3. **Graceful Fallback**: LiteGate falls back to compiling and serving the raw file only if no pre-compressed disk assets are found.

> [!TIP]
> Use frontend build utilities (such as Vite, Webpack, or Rollup plugins) to output pre-compiled `.br` or `.gz` assets during packaging to significantly reduce gateway CPU usage.

---

## 4. Hot LRU Asset Caching

For highly accessed static assets smaller than **256KB**, LiteGate automatically caches the compressed byte blocks in a localized memory LRU cache (with a capacity limit of **1024 entries**), completely bypassing disk I/O bottlenecks.
