# 路由优先级解析 (Routing Priority)

当一个域名下定义了多个路由（Routes）时，LiteGate 需要决定哪个路由最匹配当前的入站请求。

---

## 1. 核心原则：最长前缀匹配 (Longest Prefix First)

LiteGate 采用标准的 **最长前缀匹配** 策略。这意味着路径描述越具体（字符越长）的路由，优先级越高。

### 示例场景：
- **路由 A**: `path_prefix: /`
- **路由 B**: `path_prefix: /api`
- **路由 C**: `path_prefix: /api/v1`

**匹配结果**：
1. 请求访问 `/index.html` ➡️ 匹配 **路由 A**。
2. 请求访问 `/api/status` ➡️ 匹配 **路由 B**（比 A 更具体）。
3. 请求访问 `/api/v1/user` ➡️ 匹配 **路由 C**（比 B 更具体）。

---

## 2. 顺序匹配规则 (List Order)

如果两个路由的路径前缀完全相同，LiteGate 将按照配置文件中 **从上到下** 的声明顺序进行尝试。

```yaml
routes:
  - name: first-match
    match: { path_prefix: "/data" }
    
  - name: second-match
    match: { path_prefix: "/data" } # 这个路由永远不会被匹配，因为被上方拦截了
```

---

## 3. 过滤器冲突处理

如果路由使用了多种过滤器（如 `method` 加 `path_prefix`），网关会优先保障满足所有过滤条件的路由。

---

## 4. 最佳实践建议

1.  **分层定义**: 始终将最通用的路由（如 `/`）放在配置文件的最下方。
2.  **明确 Action**: 确保每个路由的 Action 逻辑清晰，避免因剥离前缀（strip_prefix）导致的转发路径错误。
3.  **命名规范**: 为每个路由设置有意义的 `name`，这在可观测性日志和 Dashboard 中非常有用。

---

## 下一步
如果你遇到了路由未生效的情况，可以查看 [调试指南](../11-troubleshooting/debugging.md)。
