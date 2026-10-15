# Kubernetes 部署与使用

当前支持 EndpointSlice 服务发现、标准 Ingress、Gateway API 与状态回写。先安装所需 Gateway API CRD，再安装仓库 Helm 或原生清单。入口 Service/DNS 负责让流量到网关，Ingress/Gateway 对象负责进入后选路；二者缺一不可。

Ingress controller 为 litegate.io/ingress-controller；Gateway controllerName 为 litegate.io/gateway-controller；仓库默认类名 litegate。使用明确的 ingressClassName/parentRefs，不假设任意类都会被接管。配置 watch 开关、namespace 范围、RBAC 和 status 发布地址。

HTTPS 使用 Secret 或网关证书能力；跨 namespace 后端、TLS Secret 和镜像目标需 ReferenceGrant。BackendTLSPolicy 设置 CA/系统信任和 SNI；无效安全策略拒绝，不能默认降级明文。LiteGateTrafficPolicy 提供项目自定义重试、超时、限流、熔断、WAF、CORS 和并发策略。

同端口多个 TLSRoute 已聚合并按 SNI 分流；TCPRoute/UDPRoute 端口冲突使用稳定优先级仲裁，不是 TLSRoute 的旧首条限制。多副本可使用 Lease 选主；它协调控制器工作，不同步全部数据面内存状态。

排错检查资源 Accepted/ResolvedRefs、RBAC、watch 日志、EndpointSlice 就绪、入口 Service 端口、证书和实际请求。当前代码支持不代表已经通过全部 Gateway API conformance。

`/readyz` 在 Kubernetes 全部启用缓存首次同步、首次 Catalog 提交及监听/路由发布成功后返回 200。启动阶段持续 403 会保持未就绪，应修复 RBAC 或显式关闭不使用的 watch；不要通过延长探针初始等待来掩盖权限问题。滚动发布前端时，除 Helm 就绪状态外，还应核对每个就绪副本的文件版本及实际入口内容已经收敛，再验证浏览器加载和 API 行为。

```bash
helm install litegate ./deploy/helm/litegate -n litegate-system --create-namespace
```

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-app
spec:
  ingressClassName: litegate
  rules:
    - host: app.example.com
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: my-app
                port: {number: 80}
```

## 相关文档与代码

扩展策略、后端 filters、标准超时、会话保持、DNS/URI SAN 和认证资源的 YAML 示例见[矩阵验收与资源用法](../../examples/k8s-acceptance/README.md)。生产部署应先更新 TrafficPolicy CRD；Helm upgrade 不会自动更新 `crds/` 目录中已安装的 CRD。

Helm 现在用 Secret 保存运行配置，自动生成的共享 `sticky_key` 在升级时保留；也可用 `existingConfigSecret` 接管配置。WebServer/SPA 与 Kubernetes API 一体化示例包含不可变前端文件、多副本共享挂载、升级回滚和 `/api` 的 JSON 503 兜底，见[Chart 使用说明](../../deploy/helm/litegate/README.md)。

- [Capabilities](litegate_kubernetes_capabilities.md)
- [Helm](../../deploy/helm/litegate)
- [Native manifests](../../deploy/k8s)
- [Provider](../../internal/provider/k8s/provider.go)
