# Redirect Action (重定向处理)

`redirect` 动作允许 LiteGate 在网关层面直接执行 HTTP 状态码跳转。它常用于旧域名迁移、协议升级或内部路径重组。

---

## 1. 基础重定向示例

将旧域名 `old.com` 永久跳转到新域名。

```yaml
domain: old.example.com
routes:
  - name: domain-migration
    match:
      path_prefix: /
    action:
      type: redirect
      location: "https://new.example.com{path}" # {path} 会保留原始请求路径
      status: 301 # 永久移动
```

---

## 2. 协议强制升级 (HTTP -> HTTPS)

除非特别指定，LiteGate 的 `force_https: true` 会在底层自动创建一个 `redirect` 动作。

手动配置示例：

```yaml
domain: web.local
routes:
  - name: force-ssl
    match: { path_prefix: "/" }
    action:
      type: redirect
      location: "https://web.local{path}"
      status: 307 # 临时重定向
```

---

## 3. 参数说明

| 参数 | 类型 | 说明 |
| :--- | :--- | :--- |
| `location` | string | **必填**。重定向的目标 URL。支持 `{path}` 变量。 |
| `status` | int | **必填**。HTTP 状态码。常用：301, 302, 307, 308。 |

---

## 4. 常见场景

### 路径替换
将所有 `/old-api` 请求跳转到 `/api/v2`：
- **Target**: `https://{host}/api/v2{path}`
- **注意**: 确保 `path_prefix` 与 `target` 中的变量组合逻辑一致。

---

## 延伸阅读
- [配置反向代理 API](./proxy.md)
- [使用 Redirect 实现站点级全域跳转](../02-concepts/routing-priority.md)
