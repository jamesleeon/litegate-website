# Serve Action (静态文件服务)

`serve` 是 LiteGate 内置的高性能静态资源处理器。它支持现代前端（如 Vue, React, Next.js）的所有路由特性，并内置了智能压缩和缓存机制。

---

## 1. 基础配置 (Basic Static Hosting)

将域名根目录映射到文件夹：

```yaml
action:
  type: serve
  root: "./www/dist"      # 静态资源存放路径
  index: "index.html"      # 默认 index 文件
  compress: true           # 开启 Gzip/Brotli 压缩
```

---

## 2. 现代前端 SPA 支持 (Single Page App)

React 或 Vue 项目中的前端路由（如 `/user/profile`）在物理磁盘上并没有对应文件。通过 `spa` 参数，网关将所有 404 请求回退到入口，由前端路由接管。

```yaml
action:
  type: serve
  root: "./my-app/build"
  index: "index.html"
  spa: true                # 关键：开启单页应用 (SPA) 路由支持
```

---

## 3. 高级配置

### 缓存策略 (Caching)
控制浏览器端的缓存时间：
```yaml
  cache_control: "public, max-age=3600" # 设置标准 Cache-Control 响应头
```

### 智能压缩 (Compression)
设置 `compress: true` 后，LiteGate 会按照客户端的 `Accept-Encoding` 权重协商 Zstandard、Brotli 或 Gzip。若同目录存在较新的 `.zst`、`.br`、`.gz` 预压缩文件，会优先直接发送；否则使用动态压缩。`compress: false` 不会发送预压缩文件。

### 目录浏览

`serve` 默认不展示目录内容。确实需要下载目录时显式开启：

```yaml
action:
  type: serve
  root: "./downloads"
  browse: true
```

如需标题、隐藏文件控制等完整目录页面能力，建议使用独立的 `list` Action。

### 路径限制
`serve` 动作内置根目录隔离，禁止符号链接和路径遍历逃逸；隐藏文件及目录（例如 `.git`、`.env`）默认不可访问，但保留 ACME 所需的 `.well-known`。`index` 与 `not_found_file` 只能配置为根目录内的相对路径。

静态服务仅接受 `GET`、`HEAD` 和 `OPTIONS`；其他方法返回 `405 Method Not Allowed`。

---

## 4. 应用示例：静态博客
```yaml
domain: blog.example.com
routes:
  - name: blog-content
    match:
      path_prefix: /
    action:
      type: serve
      root: "/opt/hugo-output"
      index: "index.html"
      compress: true
```

---

## 5. try_files

`try_files` 按顺序尝试一组候选文件，命中第一个存在的物理文件；都不存在时，以最后一项作为**回退目标**做内部重定向。常用于 PHP 前端控制器（WordPress/Laravel 伪静态）和需要把未知路径导向入口脚本的场景。

```yaml
action:
  type: serve
  root: "/var/www/html"
  try_files:
    - "{path}"            # 先找请求路径对应的物理文件
    - "/index.php"        # 都没有 → 回退到入口（内部重定向）
```

- **占位符**：`{path}` / `{uri}` 展开为当前请求路径。
- 前面的候选项当作**普通物理文件**校验是否存在，目录不会被当作文件命中；**最后一项若以 `/` 开头**，作为回退 URI 做内部重定向（会重新经过路由匹配，可命中如 `/index.php` 的 FastCGI 路由）。内部重定向保留客户端原始 URI 与查询参数，适用于 WordPress、Laravel 等前端控制器。
- **环路保护**：内部重定向超过 5 次自动返回 `508 Loop Detected`，防止死循环。

> 纯前端 SPA 的简单回退用 `spa: true` 即可；`try_files` 适合更通用的"干净 URL → 入口脚本"模式。

---

## 延伸阅读
- [配置强制 HTTPS 跳转](../06-certificates/auto-cert.md)
- [使用 Markdown Action 展示文档](./markdown.md)
