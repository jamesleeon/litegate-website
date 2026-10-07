# Proxy Cache (反向代理内容缓存)

`proxy_cache` 把上游响应缓存在网关本地，命中时直接由网关返回，不再回源。适合抗突发流量、给高 QPS 接口做微缓存、降低后端压力。对标 Nginx 的 `proxy_cache`。

> 配置在每条路由的 `action` 上，仅对 `proxy` 类型路由有意义。

---

## 1. 最小配置

```yaml
routes:
  - name: cached-api
    match:
      path_prefix: /api/list
    action:
      type: proxy
      upstream:
        - "127.0.0.1:8080"
      proxy_cache: true
      proxy_cache_ttl: 30      # 缓存 30 秒
```

命中情况会写入响应头 `X-LiteGate-Cache: HIT` / `MISS`，便于排查。

---

## 2. 字段参考

| 字段 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `proxy_cache` | bool | `false` | 开启该路由的内容缓存 |
| `proxy_cache_ttl` | int | `10` | 缓存时间（秒）。同时会尊重上游 `Cache-Control`，取**更短**的那个 |
| `proxy_cache_key` | string | `方法:Host:路由名:URI` | 自定义缓存 Key 模板，见下 |

全局上限（`config.yaml`）：

```yaml
cache:
  proxy_cache_max_entries: 10000   # 最大缓存条目数，超出按 LRU 淘汰，防内存溢出
```

---

## 3. 自定义缓存 Key

默认 Key 已包含方法、Host、路由名和完整 URI（含查询串）。需要更精细控制时用 `proxy_cache_key`，支持占位符：

- `{host}`、`{uri}`、`{path}`、`{method}`（`{uri}` 包含查询串，`{path}` 不包含）
- `{header.X}`：取请求头 `X` 的值

```yaml
action:
  type: proxy
  upstream: ["127.0.0.1:8080"]
  proxy_cache: true
  proxy_cache_ttl: 60
  proxy_cache_key: "{host}:{uri}:{header.Accept-Language}"   # 按语言分缓存
```

---

## 4. 自动绕过缓存的情况（防泄露 / 防错误）

为避免缓存私密数据或不可缓存内容，命中以下任一条件会**自动绕过缓存**：

- 请求带 `Authorization` 或 `Cookie` 头；
- 响应带 `Set-Cookie`；
- 响应 `Cache-Control` 含 `private` / `no-store` / `no-cache`，或 `max-age=0`；
- 响应的 `Vary` 包含 `Accept-Encoding`、`Origin` 之外的维度；
- 非 `GET` / `HEAD` 请求；
- WebSocket 升级、gRPC、SSE（`text/event-stream`）；
- `Range` 或条件请求（`If-None-Match` / `If-Modified-Since` / `If-Range`）；
- 路由启用了鉴权/身份注入，但缓存 Key 未包含身份维度（防跨用户串数据）。

只有 `200` / `203` / `300` / `301` 状态码会被缓存。

---

## 5. 与压缩的关系

`proxy_cache` 缓存的是**未压缩的原始响应体**，压缩在更外层按客户端 `Accept-Encoding` 实时进行。因此同一份缓存可同时服务支持/不支持压缩的客户端，不会发错编码。

---

## 6. 内存与安全保护

- **单对象上限 1MB**：响应体流式超过 1MB 即停止缓存（仍正常透传给客户端），不占内存。
- **全局条目上限**：超过 `proxy_cache_max_entries` 按 LRU 淘汰，防缓存洪泛打爆内存。
- **并发回源合并**：同一 Key 的并发 MISS 会被合并为一次回源（singleflight），避免缓存击穿。

---

## 最佳实践

1. **微缓存**：对读多写少、轻微过期可接受的接口设 `proxy_cache_ttl: 1~5`，即可大幅削峰。
2. **个性化接口别全局缓存**：带登录态的接口要么不开缓存，要么用 `proxy_cache_key` 把身份维度纳入 Key。
3. 配合 [限流](./rate-limit.md) 与 [并发连接限制](./rate-limit.md#5-并发连接限制-limit_conn) 一起保护后端。
