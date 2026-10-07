# WAF (Web 应用防火墙)

LiteGate 内置了一个轻量级 **Web 应用防火墙(WAF)**,在边缘层检查请求,在恶意流量到达后端之前拦截常见攻击。它**配置在路由的 `action` 上**。

---

## 1. 检测的攻击模式

WAF 默认扫描并可拦截以下模式:

- **SQL 注入(SQLi)**:`SELECT`、`UNION`、`DROP` 等数据库关键字或内联注释。
- **跨站脚本(XSS)**:`<script>`、`onerror`、`onload`、`javascript:` 伪协议等注入向量。
- **路径穿越**:`../`、`..\\` 或指向 `/etc/passwd` 的请求。
- **OS 命令注入**:`eval()`、`exec()`、`sh -c` 等 shell 关键字或重定向符。

---

## 2. 配置

在路由的 `action` 下加 `waf` 块:

```yaml
routes:
  - name: app
    match:
      path_prefix: /
    action:
      type: proxy
      upstream:
        - "localhost:8080"
      waf:
        enabled: true
        block_mode: true       # true = 拦截并返回 403;false = 仅记录日志/指标
        sensitivity: medium    # low | medium | high
```

| 字段 | 类型 | 作用 |
| --- | --- | --- |
| `enabled` | bool | 为该路由开启 WAF。 |
| `block_mode` | bool | `true` 拦截命中请求并返回 `403`;`false` 只记录日志/指标(审计模式)。 |
| `sensitivity` | string | 检测强度:`low`、`medium`、`high`。 |

---

## 3. 命中后的响应

当 `block_mode: true` 且检测到攻击时:

1. 客户端收到 HTTP **`403 Forbidden`**。
2. 网关在日志和指标中记录该检测,便于监控。

当 `block_mode: false` 时,请求不会被拦截——只记录检测结果,适合在正式拦截前做调优。

---

## 最佳实践

1. **先用审计模式上线**:先 `block_mode: false` 跑一段时间找出误报,再切到 `block_mode: true`。
2. **调节 sensitivity**:从 `medium` 起步;敏感接口提到 `high`,若正常流量被误伤就降到 `low`。
3. **结合限流**:配合[限流](./rate-limit.md),在边缘节流自动化扫描器。
