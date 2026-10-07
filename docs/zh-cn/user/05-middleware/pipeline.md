# Middleware Pipeline 与 Chain

LiteGate 会在路由发布前把内联治理字段、命名 middleware 和 Proxy 上游策略编译成一份只读 PipelinePlan。配置写法可以不同，但运行时顺序只有一套。

## 执行阶段

请求按以下阶段从外向内执行：

```text
Preflight
  → RequestTransform
  → Security
  → TrafficControl
  → Authentication
  → PostAuth
  → Response
  → Action / Upstream
```

- `Preflight`：CORS 预检与响应信封。
- `RequestTransform`：Rewrite、Headers、StripPrefix、路径重写和重定向。
- `Security`：IP Restriction、WAF。
- `TrafficControl`：RateLimit、LimitConn。
- `Authentication`：JWT、API Key、内联 Auth、OIDC/RemoteAuth。
- `PostAuth`：只处理已经通过认证的流量，例如 Mirror。
- `Response`：Compression、Proxy Cache。
- `Upstream`：IDS、Retry、Circuit Breaker；这类节点需要理解后端实例和单次尝试，不是普通 HTTP Handler。

旧插件的 `Stage/Priority` 接口继续兼容，Router 会把它转换到新 Phase。新内置 middleware 使用明确的 Descriptor。

## 使用 Chain 复用标准策略

`chain` 是编译期 middleware，不会在请求热路径增加一层空 Handler。它支持嵌套，并在加载时检查循环和未定义成员。

```yaml
middlewares:
  security-headers:
    type: headers
    config:
      response.X-Frame-Options: DENY
      response.X-Content-Type-Options: nosniff

  api-jwt:
    type: jwt_auth
    config:
      jwks_url: https://id.example.com/.well-known/jwks.json
      issuer: https://id.example.com/

  shared-limit:
    type: ratelimit
    config:
      qps: "500"

  standard-api-security:
    type: chain
    config:
      middlewares: security-headers, api-jwt, shared-limit

routes:
  - name: orders
    match:
      path_prefix: /orders
    middlewares: [standard-api-security]
    action:
      type: proxy
      upstream: [127.0.0.1:8080]
```

同一路由不能重复引用同一个最终 middleware，即使重复来自不同 chain；否则加载失败。

## 已正式支持的命名类型

| 类型 | Phase | 关键字段 |
|---|---|---|
| `cors` | Preflight | `enabled`、`allowed_origins`、`allowed_methods` |
| `headers` | RequestTransform | `request.<Header>`、`response.<Header>` |
| `rewrite` | RequestTransform | `path_pattern`、`path_target`、`query_set.<name>`、`query_add.<name>`、`query_rename.<name>`、`query_remove` |
| `redirect_scheme` | RequestTransform | `scheme=http|https`、`port`、`permanent` |
| `redirect_regex` | RequestTransform | `regex`、`replacement`、`permanent` |
| `replace_path_regex` | RequestTransform | `regex`、`replacement` |
| `strip_prefix` | RequestTransform | `prefixes` |
| `ratelimit` | TrafficControl | `qps` |
| `limit_conn` | TrafficControl | `limit`、`key=global|ip` |
| `jwt_auth` | Authentication | `jwks_url`、`issuer`、`audience`、`inject_claims` |
| `api_key` | Authentication | `keys`、`extract_from`、`quotas`、`default_quota` |
| `basic_auth` | Authentication | `users`、`realm`、`remove_header` |
| `remote_auth` | Authentication | `provider`、`enabled`、`enforce`、`inject_claims`、`fail_policy` |
| `mirror` | PostAuth | `target`、`percent` |
| `compress` | Response | `enabled` |
| `retry`（已弃用） | Upstream | `attempts` |
| `circuit_breaker`（已弃用） | Upstream | `enabled`、`timeout`、`max_requests`、`trip_threshold` |
| `chain` | 编译期 | `middlewares` |

`retry` 和 `circuit_breaker` 只允许用于 `proxy` Action。它们会被编译到 Action 的强类型副本，并继续使用成熟的 Proxy 重试预算、幂等检查、实例级熔断和指标逻辑。这两个类型已弃用（仍可用，加载时提示），请改用 Service 的 `retry` / `circuitbreaker`，见 [命名 Service 与配置分层](../03-configuration/services.md)。

`rewrite`、`compress`、`remote_auth` 的命名定义与对应的 action 内联字段完全等价，执行位置也相同。

`redirect_regex` 的 `regex` 匹配完整绝对 URL（协议、Host、路径和查询参数），而不是只匹配路径。例如，将 `http://example.com/old/42` 跳转到新地址可以写成：

```yaml
redirect-old:
  type: redirect_regex
  config:
    regex: "^http://example\\.com/old/(.*)$"
    replacement: "https://example.com/new/$1"
    permanent: "true"
```

## 内联与命名配置规则

- CORS、Compress、Rewrite、RemoteAuth、Retry、CircuitBreaker、RedirectScheme 默认只允许一个有效实例。
- 同一能力同时使用内联和命名配置时，加载器会报错，并列出冲突来源。
- RateLimit 和 LimitConn 可以按作用域分层：内联配置是路由局部桶，命名配置按 middleware 名在同站点共享。
- 显式 `enabled: false` 的定义不会进入运行时 PipelinePlan，也不会与有效实例发生冲突。
- middleware 注册时发布的 `Descriptor.AllowMultiple` 会在加载期统一执行；不允许多实例的类型同时出现两个有效定义时，配置会直接失败，而不是依赖 wrapper 覆盖顺序。

使用 MCP 的 `lookup_route` 可以查看 chain 展开后的 `Effective Pipeline (outer → inner)`；配置非法时，`validate_site_config` 会在保存前返回具体 middleware、路由和冲突来源。

## 尚未完成

`buffering` 仍在设计流式安全实现。它必须正确处理内存上限、临时文件、SSE、WebSocket、`Flush`、Trailer 和取消清理，因此不会用简单的全响应内存缓存实现。DigestAuth、PassTLSClientCert、ContentType、EncodedCharacters 和完整 GrpcWeb 转换属于后续低优先级能力。
