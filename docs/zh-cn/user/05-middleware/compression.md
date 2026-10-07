# Compression (智能压缩)

LiteGate 内置了高性能的响应压缩中间件，自动与客户端协商最优压缩算法，减少传输带宽。

---

## 1. 支持的算法

| 算法 | Content-Encoding | 压缩率 | CPU 消耗 |
| :--- | :--- | :--- | :--- |
| Brotli | `br` | ⭐⭐⭐⭐⭐ | 中等 |
| Zstd | `zstd` | ⭐⭐⭐⭐ | 低 |
| Gzip | `gzip` | ⭐⭐⭐ | 低 |

---

## 2. 启用方式

在 `serve` Action 中开启：

```yaml
action:
  type: serve
  root: "./dist"
  compress: true     # 开启自动压缩
```

---

## 3. 零 CPU 损耗的预压缩策略

LiteGate 优先使用"预压缩"模式，跳过实时压缩的 CPU 开销：

1. **检查磁盘**: 请求 `app.js` 时，优先查找 `app.js.br` (Brotli) 或 `app.js.zst` (Zstd)。
2. **直接透传**: 如果预压缩文件存在且客户端支持对应编码，直接发送。
3. **降级传输**: 仅在预压缩文件缺失时才传输原始文件。

> [!TIP]
> 使用前端构建工具 (Vite, Webpack) 生成 `.br` / `.gz` 预压缩文件，可以显著降低网关 CPU 消耗。

---

## 4. 内存热点缓存

对于小于 256KB 的热点文件，LiteGate 会自动缓存到内存 LRU 中（容量 1024 条），完全跳过磁盘 I/O。
