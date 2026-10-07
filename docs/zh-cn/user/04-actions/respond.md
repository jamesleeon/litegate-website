# Respond Action (直接响应)

`respond` 动作允许 LiteGate 在不依赖任何后端服务的情况下，直接向客户端返回预定义的内容。它非常适合用于健康检查、Mock 测试、维护页面或返回简单的元数据。

---

## 1. 基础配置示例

创建一个简单的健康检查接口：

```yaml
routes:
  - name: health-check
    match:
      path_prefix: /status
    action:
      type: respond
      status: 200
      body: "OK"
      headers:
        Content-Type: text/plain
```

---

## 2. 返回 JSON 内容

```yaml
routes:
  - name: mock-api
    match: { path_prefix: "/api/mock" }
    action:
      type: respond
      status: 201
      body: '{"message": "Mock Response Success", "code": 0}'
      headers:
        Content-Type: application/json
```

---

## 3. 参数说明

| 参数 | 类型 | 说明 |
| :--- | :--- | :--- |
| `status` | int | **必选**。HTTP 状态码。例如 200, 403, 503 等。 |
| `body` | string | **可选**。返回的响应体内容。 |
| `headers` | map | **可选**。需要注入的 HTTP 响应头。 |

---

## 4. 常见场景

- **系统维护页**: 当后端由于维护下线时，可以临时将路由改为 `respond`，返回 503 和一段说明文字。
- **自定义 404**: 在所有路由的最下方配置一个 `/` 的 `respond` 路由，返回友好的错误提示。
- **域名验证**: 在配置某些第三方服务（如微信）时，需要返回特定的文本文件或字符串。

---

## 延伸阅读
- [配置反向代理 API](./proxy.md)
- [使用 Redirect 实现自动跳转](./redirect.md)
