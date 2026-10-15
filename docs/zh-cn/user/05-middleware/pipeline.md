# Middleware Pipeline 与 Chain

路由发布前，内联字段、命名 middleware 和上游策略会编译为只读 PipelinePlan。顺序为 Preflight → RequestTransform → Security → TrafficControl → Authentication → PostAuth → Response → Action/Upstream。

CORS 位于 Preflight；rewrite、headers、strip_prefix、重定向位于 RequestTransform；IP/WAF 位于 Security；限流/并发限制位于 TrafficControl；身份校验位于 Authentication；mirror 位于 PostAuth；压缩/代理缓存位于 Response。IDS 与代理内部重试、熔断需要遵守各自运行契约。

`chain` 在编译期展开，支持嵌套。未定义成员、循环或展开后重复引用同一 middleware 都会加载失败。中间件插件统一使用 MiddlewareRegistration 的 Descriptor/Validate/Active 与 Wrap；当前公共接口不再提供 Stage/Priority 双轨注册。

命名 rewrite、compress、remote_auth 与对应内联字段在同一位置生效。命名 retry/circuit_breaker 已弃用，仍兼容且仅允许 proxy；新配置将上游策略写在 Service。

```yaml
site: api.example.com
middlewares:
  safe-headers:
    type: headers
    config: {response.X-Content-Type-Options: nosniff}
  api-policy:
    type: chain
    config: {middlewares: safe-headers}
routes:
  - match: {path_prefix: /api}
    use: [api-policy]
    proxy: ['127.0.0.1:8080']
```

## 相关文档与代码

- [Services](../03-configuration/services.md)
- [Public contract](../../../../pkg/plugin/middleware.go)
- [Runtime](../../../../internal/router/pipeline_plan.go)
