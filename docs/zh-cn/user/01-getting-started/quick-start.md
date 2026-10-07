# 快速开始

本指南将帮助你在 5 分钟内启动 LiteGate 并配置第一个站点。

## 前置条件

- 已安装 LiteGate ([安装指南](installation.md))。
- 一个可用的域名（用于 HTTPS 测试，本地测试可使用 `localhost`）。

---

## 步骤 1：零配置启动

LiteGate 支持即插即用。在终端直接运行：

```bash
litegate
```

你将看到类似如下的输出：
- `INFO: HTTP Server listening on :80`
- `INFO: Loaded 0 sites from ./sites`

> Dashboard **默认关闭**。要开启,在 `config.yaml` 里设置 `dashboard.enabled: true`(默认端口 `9999`)。

---

## 步骤 2：创建第一个站点 (Hello World)

在当前目录下创建 `sites` 文件夹，并新建 `hello.yaml`：

```bash
mkdir -p sites
cat > sites/hello.yaml << 'EOF'
domain: localhost
routes:
  - name: welcome
    match:
      path_prefix: /
    action:
      type: respond
      status: 200
      body: "Hello, LiteGate! 您的网关已就绪。"
      headers:
        Content-Type: text/plain; charset=utf-8
EOF
```

**LiteGate 会自动检测文件变动并实时加载，无需重启。**

---

## 步骤 3：测试访问

使用 `curl` 或浏览器访问：

```bash
curl http://localhost/
# 预期输出: Hello, LiteGate! 您的网关已就绪。
```

---

## 步骤 4：配置静态文件服务 (SPA)

假设你有一个前端项目在 `dist` 目录：

```yaml
# sites/web.yaml
domain: web.local
routes:
  - name: frontend
    match:
      path_prefix: /
    action:
      type: serve
      root: ./dist
      index: index.html
      spa: true            # 支持单页应用 (SPA) 路由
      compress: true       # 开启 Gzip/Brotli 压缩
```

---

## 步骤 5：反向代理到后端服务

将请求转发到运行在 `8080` 端口的 Go 或 Java 服务：

```yaml
# sites/api.yaml
domain: api.example.com
routes:
  - name: user-service
    match:
      path_prefix: /api/v1
    action:
      type: proxy
      upstream: ["localhost:8080"]
      strip_prefix: true # 转发时移除 /api/v1 前缀
```

---

## 步骤 6：启用自动化 HTTPS

只要你的机器具备公网 IP 且域名解析已指向本机，只需一行配置：

```yaml
domain: example.com
force_https: true # 开启自动申请证书并强制跳转 HTTPS
routes:
  - name: secure-app
    match:
      path_prefix: /
    action:
      type: proxy
      upstream: ["localhost:3000"]
```

---

## 下一步建议

- 了解 [Sites 与 Routes 的深度关系](../02-concepts/sites-and-routes.md)。
- 探索 [多种 Action 类型](../README.md#4-action)（如 WebDAV, Markdown 渲染）。
- 为你的 API [添加认证保护](../05-middleware/authentication.md)。
