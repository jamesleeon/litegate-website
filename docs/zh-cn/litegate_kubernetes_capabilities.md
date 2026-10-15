# Kubernetes 当前能力与边界

以下是代码能力索引，不是标准认证报告或竞品替代承诺。

| 能力 | 当前实现 |
|---|---|
| Service/EndpointSlice | REST list/watch、重连、relist、就绪/终止过滤 |
| Ingress/IngressClass | 类认领、host/path/defaultBackend、Secret、状态回写 |
| GatewayClass/Gateway | controllerName 认领、listeners、AllowedRoutes、TLS 与 status |
| HTTPRoute/GRPCRoute | 路由翻译、parentRefs、匹配、加权 Service 后端、status |
| HTTP filters | 请求/响应头、重定向、URLRewrite、镜像等已实现子集 |
| ReferenceGrant | 跨 namespace 后端、证书和镜像引用校验 |
| BackendTLSPolicy | CA/系统信任、独立 SNI、DNS/URI subjectAltNames、CA ConfigMap 动态轮换、失败关闭 |
| TLSRoute | 同端口聚合，SNI 透传分流 |
| TCPRoute/UDPRoute | L4 转发，端口冲突按稳定优先级仲裁 |
| LiteGateTrafficPolicy | 附着策略、同 namespace ExtensionRef 复用、后端级过滤器、重试退避、限流/熔断/并发策略与 status |
| 标准规则治理 | request/backendRequest 超时、可重放请求体重试、Cookie/Header sessionPersistence |
| 认证资源 | Basic/JWT Secret、JWT JWKS、OIDC（PKCE/nonce）、ForwardAuth、凭据轮换与删除失败关闭 |
| 高可用部署 | Helm/原生清单、RBAC、Lease 选主 |

只支持部分 ingress-nginx 注解，不能无损兼容其完整策略。GRPCRoute、扩展 filters、非 Service 后端及版本支持以实际类型、校验和测试为准。仓库实现与单元测试不等于 Gateway API conformance；发布标准报告前不要宣称完整支持。

watch/namespace 可显式裁剪。启用的 Kubernetes 资源必须先完成首次 List 应用，Catalog 成功提交且应用完成监听与路由重载后，`/readyz` 才放行；启动时 403 不会被视为同步完成。缺少可选 CRD 的 404 可跳过。首次就绪后，临时 API/RBAC 故障会重试并保留现有配置，不因单个租户的坏配置撤下整个副本。大集群性能、API 配额、断流重建和 listener 暴露仍需在目标环境验证。TLSRoute 聚合已修复旧“首条生效”限制，不能继续引用旧审计作为现状。

Gateway API 的验证版本固定为 `v1.4.1 experimental`。实现按字段声明范围：HTTP 路径支持 Exact/PathPrefix；请求头及查询参数支持 Exact/RegularExpression；镜像支持 percent。未实现的路径正则、标准 CORS filter、镜像 fraction、非 Service 后端及无法识别的保留字段明确拒绝。自定义策略 CORS 与标准 CORS filter 的配置入口不同。API Server 已裁剪的未知字段应由 `kubectl --validate=strict` 检查。

不支持的匹配不生成替代路由，并撤销其对应的旧 Gateway 转发；同域名的其他有效路由继续生效。只有不支持匹配且没有其他站点时返回 `404 / site-not-found`；合法 HTTPS listener 可保留证书与显式 404 占位。已知匹配上的不支持过滤器使用失败动作，不能转发到旧后端。这与原生配置的 last-good 保留语义分别处理。

多副本认证需共享 Redis 和一致 session 加密密钥；各副本内存限流/熔断计数不会由 Lease 自动同步。状态写入由 leader 管理，数据面仍由每个副本独立发现并发布。状态更新保留其他控制器 parent 状态，并通过 UID/resourceVersion 防止同名重建资源被旧写入覆盖。

版本兼容、官方逐项结果、规模/持续运行数据和构建身份以[优化验收记录](litegate_k8s_optimization_report.md)为准。统一运行入口及原始数据口径见[验收说明](../../examples/k8s-acceptance/README.md)。

## 相关文档与代码

- [Usage](litegate_k8s_usage_guide.md)
- [Provider tests](../../internal/provider/k8s/provider_test.go)
- [Gateway translator](../../internal/loader/gateway_translator.go)
- [Gateway tests](../../internal/loader/gateway_translator_test.go)
