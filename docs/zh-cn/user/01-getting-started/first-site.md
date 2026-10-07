# 第一个站点配置示例 (First Site)

本示例为一个应用建立网关入口，先用最短写法跑起来，再在同一个文件里逐步加功能。

## 场景描述
我们要为 `api.example.com` 建立一个网关入口：
1.  **`/api/v1` 路径**：路由到后端微服务。
2.  **根路径 `/`**：挂载一个 React 单页应用 (SPA)。
3.  **HTTPS**：开启 HTTP → HTTPS 强制跳转。

---

## 最短写法

创建文件 `sites/api.example.com.yaml`：

```yaml
site: https://api.example.com
/api/v1: 10.0.0.5:8080
spa: /var/www/my-app/dist
```

- `site: https://...` 表示开启 HTTP → HTTPS 跳转；写成 `site: api.example.com` 则只做 HTTP 转发，不跳转。
- `/api/v1: 地址` 是路径前缀路由的简写，等价于在该路径下写 `proxy: 地址`。
- `spa:` 写在站点层，作为其他所有路径的兜底：托管静态文件，未知路由回退到 `index.html`。

---

## 按需增加功能

需要多个后端轮询、转发时去掉路径前缀时，把路径键改成映射形式，其余部分不变：

```yaml
site: https://api.example.com
/api/v1:
  proxy: 10.0.0.5:8080, 10.0.0.6:8080   # 多个地址，默认轮询
  strip_prefix: true                    # 转发时去掉 /api/v1 前缀
spa: /var/www/my-app/dist
```

鉴权、限流、跨域、缓存、命名服务复用等写法，见 [站点配置](../03-configuration/site-config.md) 和 [常用场景案例](../cookbook/README.md)。

---

## 如何应用此配置？

1.  将上述内容保存为 `sites/api.example.com.yaml`。
2.  LiteGate 运行后会自动检测到该文件并热加载。
3.  可以先用 `litegate -t` 检查配置是否正确。
4.  **检查控制台输出**：
    -   站点加载成功的日志
    -   域名已解析到本机时，会出现申请 `api.example.com` 证书的日志

---

## 验证步骤

1.  **测试 API 转发**：
    `curl https://api.example.com/api/v1/health`
    应返回后端服务的响应。
2.  **测试前端静态页**：
    在浏览器访问 `https://api.example.com/`，应能看到你的 React 应用。
3.  **测试 HTTPS 强制跳转**：
    `curl -I http://api.example.com/` 应返回跳转到 `https://` 的响应。

> 旧的 `domain:` 标准格式和 `.lite.yaml` 文件仍然可以正常加载，无需迁移；新配置请使用 `site:` 格式。

---

## 下一步
接下来，你可以深入了解 [Sites 和 Routes 的详细工作原理](../02-concepts/sites-and-routes.md)。
