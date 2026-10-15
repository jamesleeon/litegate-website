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
site: example.com
compress: true # Activates automated algorithm negotiation
serve: "./dist"
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

Files and precompressed sidecars smaller than 32 KiB use an in-memory LRU and write their cached body directly. The content cache holds at most 1024 entries and 64 MiB in total; metadata has a 10-second TTL. Larger files lease independent descriptors on Linux, preserving sendfile. Windows opens files per request so deployments can replace files and directories.

With compression enabled, compressible static files from 256 B through 1 MiB cache their encoded bytes under the same content-cache budget. File-version changes and root invalidation regenerate these results. Larger files retain streaming compression.

Dynamic compression bypasses Range requests, 206 responses, existing content encodings, SSE, noncompressible Content-Type values, and responses whose known Content-Length is below 256 B. Unknown-length streams are not additionally buffered for the size threshold. gzip, br, and zstd append an encoding suffix to ETag while preserving W/ for weak validators. Vary retains existing values and includes Accept-Encoding.
