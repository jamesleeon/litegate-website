# Actions 详解：请求处理模型

在 LiteGate 中，当路由匹配成功后，必须指定一个 **Action (动作)** 及其关联的处理器。Action 定义了网关如何响应请求、转发流量或渲染内容。

---

## 核心 Action 类型

### 1. Proxy (反向代理)
最常用的动作。将 HTTP/HTTPS/WebSocket 请求转发到后端。
- **支持**: 负载均衡 (RR/LC)、健康检查、连接池复用。
- **适用**: 微服务、传统 Web 应用、gRPC-Web。

### 2. Serve (静态服务)
内置的高性能静态文件服务器。
- **特性**: 智能压缩 (Brotli/Gzip)、缓存控制、SPA 路由回退。
- **适用**: Vue/React/Next.js 入口、公共资源托管。

### 3. Respond (直接响应)
网关直接返回固定内容，不经过任何后端。
- **特性**: 自定义状态码、Header 和 Body。
- **适用**: 健康检查端点、系统维护页、Mock 测试。

### 4. Redirect (重定向)
执行 HTTP 301/302/307 重定向。
- **特性**: 自动补全协议 (HTTP -> HTTPS)、路径重组。
- **适用**: 域名更换、旧路径重定向。

### 5. WebDAV (文件管理)
内置 WebDAV 文件驱动。
- **特性**: 跨平台挂载、文件读写、权限校验。
- **适用**: 私有网盘入口、自动化备份节点。

### 6. Markdown (文档渲染)
将目录下的 `.md` 文件实时渲染为美观的 HTML 预览页面。
- **特性**: 集成 Mermaid 图表、暗黑模式支持、锚点导航。
- **适用**: 项目在线文档展示。

---

## 如何选择 Action？

| 业务需求 | 推荐 Action |
| :--- | :--- |
| **转发流量到应用服务器** | `proxy` |
| **显示前端静态网页** | `serve` |
| **直接返回 JSON/文本** | `respond` |
| **路径强制跳转** | `redirect` |
| **挂载到电脑成为网盘** | `webdav` |
| **展示 Readme.md 文档** | `markdown` |

---

## 下一步
深入了解每个 Action 的参数详情，请参考：[站点配置参考](../03-configuration/site-config.md)。


- [NATS 实时事件订阅](../04-actions/nats-sse.md): `type: nats` / `mode: subscribe`.
