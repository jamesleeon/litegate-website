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
site: example.com
compress: true # 开启自动压缩
serve: "./dist"
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

小于 32 KiB 的文件内容和预压缩 sidecar 使用内存 LRU，命中后一次写出正文。内容缓存上限为 1024 条、合计 64 MiB；元数据有效期为 10 秒。较大文件在 Linux 上复用独立文件描述符，保留 sendfile 路径；Windows 按请求打开，以允许部署时替换文件和目录。

启用压缩后，256 B 至 1 MiB 的可压缩静态文件会缓存各编码的压缩结果，与原始内容共享上述缓存预算。文件版本或根目录缓存失效后重新生成；更大的文件继续流式压缩。

动态压缩跳过带 Range 的请求、206 响应、已压缩响应、SSE、不适合压缩的 Content-Type，以及已知 Content-Length 小于 256 B 的响应。未知长度的流式响应不为大小阈值额外缓冲。gzip、br、zstd 的 ETag 加入编码后缀，并保留弱 ETag 的 W/ 前缀；Vary 保留原值并包含 Accept-Encoding。
