# 路径改写与重定向中间件

这一组命名 middleware 都在 **RequestTransform** 阶段执行——也就是在 WAF、认证、限流**之前**，因此安全组件看到的是最终规范化后的路径。

先分清两类，别混用：

| 类别 | 中间件 | 行为 | 客户端可见吗 |
| :--- | :--- | :--- | :--- |
| **内部改写** | `strip_prefix`、`rewrite`、`replace_path_regex` | 修改转发给上游的路径/查询，客户端 URL 不变 | 否 |
| **对外重定向** | `redirect_scheme`、`redirect_regex` | 直接向客户端返回 `3xx`，让浏览器跳到新地址 | 是 |

---

## 1. `strip_prefix` —— 剥掉路径前缀

代理前去掉 `/api` 这类前缀，最常见的网关需求。

```yaml
middlewares:
  strip-api:
    type: strip_prefix
    config:
      prefixes: "/api,/v1"   # 逗号分隔，每个都必须以 / 开头

routes:
  - name: backend
    match:
      path_prefix: /api
    middlewares: [strip-api]
    action:
      type: proxy
      upstream: ["127.0.0.1:8080"]   # /api/users -> /users
```

- 命中**第一个**匹配的前缀就剥掉并停止；剥完为空则回退为 `/`。
- 每个前缀必须以 `/` 开头，否则加载失败。

---

## 2. `rewrite` —— 路径正则改写 + 查询参数编辑

`rewrite` 是功能最全的内部改写器，一个中间件同时处理路径和查询。

完整的内联配置、执行顺序、查询参数语义，以及从 Nginx `last` 迁移的示例，见 [Rewrite：路径与查询参数改写](../03-configuration/rewrite.md)。

```yaml
middlewares:
  api-rewrite:
    type: rewrite
    config:
      path_pattern: "^/api/(.*)$"       # 正则
      path_target: "/$1"                # 目标路径，必须以 / 开头
      query_set.version: "v2"           # 覆盖设置 ?version=v2
      query_add.trace: "1"              # 追加一个 ?trace=1
      query_rename.uid: "user_id"       # 把 ?uid= 改名成 ?user_id=
      query_remove: "debug,internal"    # 删除这些查询参数（逗号分隔）
```

| 字段 | 说明 |
| :--- | :--- |
| `path_pattern` / `path_target` | 成对出现。`path_pattern` 是正则，`path_target` 支持 `$1`、`$2` 反向引用，必须以 `/` 开头。 |
| `query_set.<name>` | 覆盖设置某个查询参数（存在则替换）。 |
| `query_add.<name>` | 追加一个查询参数（可与已有同名值并存）。 |
| `query_rename.<name>` | 把参数 `<name>` 改名为其值指定的目标名。 |
| `query_remove` | 逗号分隔的待删除参数名列表。 |

- 至少要配置一项路径或查询操作，否则加载失败。
- `path_pattern` 不匹配当前路径时，整条 rewrite（含查询操作）都不生效，保持原子性。
- `rewrite` 的 `AllowMultiple = false`：一个路由只能有一个有效 rewrite，且**不能同时用内联 `action.rewrite` 和命名 `rewrite`**，否则加载报错。

> 只需要“正则替换路径”而不动查询参数时，`replace_path_regex` 更轻。

---

## 3. `replace_path_regex` —— 纯路径正则替换

```yaml
middlewares:
  legacy-path:
    type: replace_path_regex
    config:
      regex: "^/old/(.*)$"
      replacement: "/new/$1"   # 必须以 / 开头
```

- 只对 `req.URL.Path` 生效，不碰查询串。
- 改写后会把原始路径写入 `X-Replaced-Path` 头，并保留原始 URI 供日志使用。
- `AllowMultiple = true`，可叠多条按声明顺序执行。

---

## 4. `redirect_scheme` —— 协议/端口重定向

强制 HTTP 跳 HTTPS 的标准做法。

```yaml
middlewares:
  force-https:
    type: redirect_scheme
    config:
      scheme: "https"        # http 或 https
      permanent: "true"      # true=301，false/省略=302
      # port: "8443"         # 可选，指定目标端口
```

- 当前协议（以及可选的端口）已经等于目标时，不重定向、直接放行。
- 判断协议时会识别 `req.TLS` 与 `X-Forwarded-Proto`，因此在反代/负载均衡后也能正确工作。

---

## 5. `redirect_regex` —— 基于完整 URL 的正则重定向

> **重点**：`redirect_regex` 的 `regex` 匹配的是**完整绝对 URL**（`scheme://host/path?query`），**不是只匹配路径**。

```yaml
middlewares:
  redirect-old-domain:
    type: redirect_regex
    config:
      regex: "^https?://old\\.example\\.com/(.*)$"
      replacement: "https://new.example.com/$1"
      permanent: "true"
```

- `replacement` 支持 `$1` 反向引用。
- 目标含换行等控制字符时返回 500（防注入）。
- `permanent: true` → 301，否则 302。
- `AllowMultiple = true`，可配多条规则。

---

## 6. 执行顺序小结

同在 RequestTransform 阶段，各中间件按注册的 `Order` 从外到内执行；同 `Order` 时按路由中的声明顺序。你可以用 MCP 的 `lookup_route` 查看 chain 展开后的 `Effective Pipeline (outer → inner)`，确认最终顺序。

因为整组都在**安全检查之前**执行，WAF 和认证看到的始终是改写后的最终路径——这一点对写路径白名单/签名策略很重要。

---

## 延伸阅读
- [Middleware Pipeline 与 Chain](./pipeline.md)
- [反向代理 Action](../04-actions/proxy.md)
- [Rate Limit 与并发连接限制](./rate-limit.md)
