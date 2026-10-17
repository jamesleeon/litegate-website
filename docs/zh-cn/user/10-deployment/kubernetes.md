# Kubernetes 部署手册

本文是在 Kubernetes 中部署和使用 LiteGate 的入口，按任务组织：先选用法，再安装，然后按场景配置。字段级细节与能力边界见文末链接。

LiteGate 在集群里既是 **Ingress / Gateway API 控制器**，也是一个完整的 **Web Server**。同一组 Pod 可以同时承担入口路由、前端静态站点、SPA、文件下载、Markdown 文档、WebDAV、状态页等工作，不需要另起一个 nginx 来托管前端。这是它和 Traefik 等纯代理型控制器最大的区别。

---

## 1. 选择用法

| 用法 | 适合 | 路由写在哪里 |
|---|---|---|
| Ingress 控制器 | 已有 Ingress 清单、从 ingress-nginx 迁移 | `Ingress`（`ingressClassName: litegate`） |
| Gateway API 控制器 | 新项目、多团队分权、L4（TCP/UDP/TLS） | `Gateway` + `HTTPRoute` / `GRPCRoute` / `TLSRoute` 等 |
| 网关 + Web Server 一体 | 前端 SPA + 后端 API、文档站、下载站 | 原生站点 YAML（挂载进 Pod）+ 上面任一种 API 路由 |
| Service 注解快捷路由 | 简单服务直接暴露 | Service 标签 `litegate.io/expose=true` + 注解 `litegate.io/domain` |

几种用法可以在同一个部署中并存。同一域名下，原生站点和 Kubernetes 路由会合并成一个站点，按路径最长匹配选路，所以原生站点的 `/` 不会遮住 HTTPRoute 的 `/api`。

---

## 2. 安装

### 2.1 前置：Gateway API CRD

只用 Ingress 可以跳过这一步。使用 Gateway API 时，先安装与验证版本一致的 CRD（当前验证版本为 v1.4.1 experimental）：

```bash
kubectl apply --server-side -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.4.1/experimental-install.yaml
```

### 2.2 Helm 安装

```bash
helm install litegate ./deploy/helm/litegate -n litegate-system --create-namespace
```

默认会创建：

- 2 副本 Deployment，启用 Lease 选主，由 leader 回写 status；
- `LoadBalancer` 类型的入口 Service（80/443）；
- 名为 `litegate` 的 IngressClass 和 GatewayClass，并把 `litegate` 设为默认 IngressClass；
- ClusterRole/ClusterRoleBinding，以及运行配置 Secret。

常用的 values：

| 值 | 默认 | 说明 |
|---|---|---|
| `controller.ingressClass` / `controller.gatewayClass` | `litegate` | 认领的类名；同集群装多套时每套要不同 |
| `controller.isDefaultIngressClass` | `true` | 是否接管未写 class 的 Ingress |
| `service.type` | `LoadBalancer` | 云上用 LB；裸机可改为 `NodePort` 或配合 MetalLB |
| `config.*` | 见 values.yaml | 原样写入 LiteGate 主配置 |
| `existingConfigSecret` | 空 | 由外部 Secret（键 `litegate.yaml`）提供完整配置 |
| `extraVolumes` / `extraVolumeMounts` | 空 | 挂载站点配置、前端文件等 |
| `initContainers` | 空 | 启动前准备文件，例如从前端镜像复制产物 |

没有 Helm 时，可以用 `deploy/k8s/` 下的原生清单，按 RBAC、IngressClass/GatewayClass、Deployment、Service 的顺序应用。

### 2.3 确认就绪

```bash
kubectl -n litegate-system get pods
kubectl -n litegate-system logs deploy/litegate | grep -i -E "error|forbidden"
```

只有当已启用的 Kubernetes 资源全部完成首次同步、路由也已发布后，`/readyz` 才返回 200。Pod 长时间未就绪，通常是 RBAC 不足或缺 CRD。应修复权限，或显式关闭不用的 watch（如 `disable_tcp_route_watch: true`），不要靠延长探针来掩盖。

### 2.4 在集群外运行（kubeconfig）

本地调试或在集群外部署时，LiteGate 像 kubectl 一样读取 kubeconfig。不在集群内、又没有配置 `api_server_url` 时，会依次查找 `$KUBECONFIG` 和 `~/.kube/config`：

```yaml
service_discovery:
  providers:
    k8s:
      kubeconfig: /home/ops/.kube/config   # 可省略；支持 $KUBECONFIG 那样的路径列表
      kube_context: prod-eks                # 可省略，默认 current-context
```

- 支持 token、tokenFile、客户端证书（文件或 `-data`）和 **exec 凭据插件**，例如 EKS 的 `aws eks get-token`、GKE 的 `gke-gcloud-auth-plugin`、AKS 的 `kubelogin`。插件返回的凭据会缓存到过期前 30 秒；API 返回 401 时立即重新获取。
- 旧式 `auth-provider` 插件和用户名密码认证会直接报错，不会退化成匿名访问。
- 在 LiteGate 配置里显式写的 `token`、`token_file`、`client_cert_file`/`client_key_file`、`ca_file`，优先于 kubeconfig 里的对应字段。
- `api_server_url` 可以带路径前缀，例如 Rancher 的 `https://rancher.example.com/k8s/clusters/c-xxxxx`，前缀会保留。
- 与 API Server 的连接默认使用 HTTP/2，所有 watch 共用一条连接，并用 ping 检测连接是否失效。代理不支持 HTTP/2 时，设置 `disable_http2: true`。

---

## 3. 场景一：Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: shop
  namespace: shop
spec:
  ingressClassName: litegate
  tls:
    - hosts: [shop.example.com]
      secretName: shop-tls
  rules:
    - host: shop.example.com
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: shop-api
                port: {number: 80}
```

- 证书来自 `kubernetes.io/tls` Secret，更新 Secret 后自动轮换；也可以交给 cert-manager 维护。
- 支持一部分 ingress-nginx 注解：ssl-redirect、proxy-body-size、backend-protocol、超时、CORS、rewrite-target 等，但不是完整兼容。迁移时逐条核对。

## 4. 场景二：Gateway API

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: public
  namespace: litegate-system
spec:
  gatewayClassName: litegate
  listeners:
    - name: https
      port: 443
      protocol: HTTPS
      hostname: "*.example.com"
      tls:
        certificateRefs:
          - name: wildcard-example-com
      allowedRoutes:
        namespaces: {from: All}
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: shop-api
  namespace: shop
spec:
  parentRefs:
    - name: public
      namespace: litegate-system
  hostnames: [shop.example.com]
  rules:
    - matches:
        - path: {type: PathPrefix, value: /api}
      backendRefs:
        - name: shop-api
          port: 80
```

- 跨 namespace 引用后端、证书或镜像目标时，需要在目标 namespace 建 `ReferenceGrant`。
- 后端走 HTTPS 时用 `BackendTLSPolicy` 指定 CA 和 SNI。CA 只接受核心组的 ConfigMap/Secret；校验失败时拒绝请求，不会降级成明文。
- 重试、限流、熔断、WAF、CORS 等治理能力，通过自定义资源 `LiteGateTrafficPolicy` 附着到路由上。
- 非 HTTP 端口（TCPRoute/UDPRoute/TLSRoute）需要同时在 `service.extraPorts` 里开放对应端口。

排错时先看资源 status：`kubectl get httproute shop-api -n shop -o yaml`，检查 `Accepted` 和 `ResolvedRefs`。

---

## 5. 场景三：网关 + Web Server 一体（LiteGate 特有）

在 Traefik 体系里，前端静态文件一般要单独部署一个 nginx Pod，再由网关转发过去。LiteGate 可以在网关 Pod 里直接提供这些内容：

| 能力 | 原生站点写法 | 说明 |
|---|---|---|
| 静态站点 / SPA | `serve:` / `spa:` | 前端路由回退到 index、压缩、缓存头、try_files |
| 文件下载站 | `list:` | 带页面的目录浏览 |
| Markdown 文档站 | `markdown:` | 直接渲染 .md 目录 |
| WebDAV | `webdav:` | 共享目录读写 |
| 模板 / 固定响应 | `template` / `respond` | 维护页、错误兜底、JSON 占位 |
| 状态页 | `status:` | 基于实际流量的状态看板 |
| PHP | FastCGI | 对接 php-fpm |

做法分三步：

1. 把**站点 YAML** 放进 ConfigMap，挂到 Pod 里，并在 `config.sites_dir` 指向挂载目录；
2. 用下面任一种方式把**站点文件**送进 Pod；
3. 动态 API 仍然用 Ingress/HTTPRoute 声明。同一域名会自动合并：证书沿用 Gateway/Ingress 引用的 Secret，按路径最长匹配选路。

### 5.1 站点 YAML

```yaml
site: shop.example.com
https: false
routes:
  # API 路由暂时缺失时返回 JSON 503，不会落进 SPA 返回 HTML
  - name: api-unavailable
    priority: 1
    match: {path_prefix: /api}
    action:
      type: respond
      status: 503
      content_type: application/json
      body: '{"error":"api-route-unavailable"}'
/:
  spa: /frontend
```

`https: false` 表示由 Kubernetes Secret 提供证书，站点本身不固定证书。如果站点 YAML 显式固定了证书文件，而文件不可用，会拒绝服务（fail closed），不会退回到 Gateway 的证书。

### 5.2 前端文件放进 Pod 的四种方式

| 方式 | 容量 | 发布 / 回滚 | 适合 |
|---|---|---|---|
| 不可变 ConfigMap | ≤ 1 MiB | 换 ConfigMap 名字后 `helm upgrade`；`helm rollback` 回滚 | 演示、很小的页面 |
| **前端镜像 + initContainer**（推荐） | 不限（emptyDir） | 改镜像 tag 后 `helm upgrade`；`helm rollback` 回滚 | 生产 SPA，版本跟镜像走 |
| 共享卷（RWX PVC，如 NFS） | 不限 | 外部写入，即时生效 | 下载站、WebDAV 这类内容需要在线修改的场景 |
| Serve KV 模式 | 不限 | 更新 KV 指针，各 Pod 自动下载 ZIP、校验 SHA256 并原子切换，不用滚动发布 | 前端发布频繁、希望与 Pod 发布解耦 |

**推荐做法：前端镜像 + initContainer。** 前端 CI 把构建产物打进一个小镜像，比如 `FROM busybox` 再 `COPY dist /dist`。Pod 启动时由 initContainer 把产物复制到 emptyDir，LiteGate 再以只读方式挂载提供服务：

```yaml
# values-web.yaml
config:
  sites_dir: /app/sites
frontendImage:
  repository: registry.example.com/shop/frontend
  tag: "1.4.2"
initContainers:
  - name: frontend
    image: "{{ .Values.frontendImage.repository }}:{{ .Values.frontendImage.tag }}"
    command: ["sh", "-c", "cp -R /dist/. /frontend/"]
    volumeMounts:
      - name: frontend
        mountPath: /frontend
extraVolumes:
  - name: frontend
    emptyDir: {sizeLimit: 512Mi}
  - name: sites
    configMap:
      name: shop-sites
extraVolumeMounts:
  - name: frontend
    mountPath: /frontend
    readOnly: true
  - name: sites
    mountPath: /app/sites
    readOnly: true
```

```bash
kubectl -n litegate-system create configmap shop-sites --from-file=shop.yaml
helm upgrade --install litegate ./deploy/helm/litegate -n litegate-system -f values-web.yaml
# 发布新前端
helm upgrade litegate ./deploy/helm/litegate -n litegate-system -f values-web.yaml --set frontendImage.tag=1.4.3
```

`initContainers` 会经过 `tpl` 渲染，所以可以引用自己定义的 `frontendImage` 值。滚动发布时，新 Pod 一定拿到同一个 tag 的完整产物，不会出现新旧文件混在一起的情况。完整示例见 `deploy/helm/litegate/examples/webstack-image-values.yaml`，ConfigMap 版本见同目录的 `webstack-values.yaml`。

**Serve KV 模式**：在 K8s 里需要给 `root` 挂一个可写的 emptyDir，`kv_provider` 可以用 `litemesh`、`consul` 或 `http`。不部署 litemesh 时，可以用 `http` 指向一个返回版本 JSON 的地址。字段说明见 [Serve KV 模式](../../serve_kv_mode.md)。

### 5.3 发布前端时的检查

Helm 显示就绪，不代表每个副本都拿到了新文件。发布后还应确认：每个就绪 Pod 上的文件版本一致；浏览器实际加载的是新版本；`/api` 能正常返回，失败时返回的是 JSON 503，而不是 HTML。

---

## 6. 多副本与高可用

- 每个副本都独立 watch 并提供流量；Lease 选主只决定由谁回写 status。Lease 默认放在 LiteGate 所在的 namespace；租约是否过期按本节点观测判断，不受节点间时钟偏差影响；leader 正常退出时会主动释放 Lease，接任者无需等待租约过期。
- 认证会话需要共享 Redis，并且各副本使用相同的 session 密钥。限流、熔断计数在各副本内存里，不跨副本同步。
- Chart 默认提供 PDB、拓扑打散和优雅退出：先摘除就绪 5 秒，再给请求和连接 30 秒排空，整体 45 秒终止宽限期。
- 升级 Chart 不会更新 `crds/` 里已安装的 CRD，需要先手动 `kubectl apply` 新版 `LiteGateTrafficPolicy` CRD。

## 7. 常见问题

| 现象 | 排查 |
|---|---|
| Pod 一直未就绪 | 看日志里的 403/404：补 RBAC，或关闭用不到的 watch |
| Ingress 不生效 | `ingressClassName` 是否和 `controller.ingressClass` 一致；同集群是否装了多套 |
| HTTPRoute `Accepted=False` | parentRefs、Gateway 的 `allowedRoutes`、listener 的 hostname 是否匹配 |
| `ResolvedRefs=False` | 后端 Service/端口是否存在；跨 namespace 引用是否缺 ReferenceGrant |
| 后端 TLS 报错 | BackendTLSPolicy 的 CA ConfigMap/Secret 是否存在、是否为核心组、hostname 是否和证书一致 |
| 前端 404 或返回旧页面 | `sites_dir` 挂载是否正确；`spa` 指向的目录；每个 Pod 上的文件版本 |
| `/api` 返回了 HTML | 给 `/api` 加 JSON 兜底路由（见 5.1） |

## 8. 版本支持

| 项目 | 已验证 | 说明 |
|---|---|---|
| Kubernetes | K3s v1.34.5、v1.35.5、v1.36.5 | 其他发行版（EKS/GKE/AKS/kind/OpenShift）尚未验证 |
| Gateway API CRD | v1.4.1 experimental | 用官方测试套件验证：HTTP/GRPC/TLS 核心用例全部通过（自测，未提交上游） |
| Ingress | networking.k8s.io/v1 | |
| EndpointSlice | discovery.k8s.io/v1 | |
| Lease | coordination.k8s.io/v1 | |

部分 Gateway API 资源的版本由 **API discovery 自动选择**：优先使用已验证的版本；集群不再提供该版本时，自动切换到下一个可解码的版本，并在日志中记录实际使用的版本。

| 资源 | 首选（已验证） | 备选 |
|---|---|---|
| BackendTLSPolicy | v1alpha3 | v1 |
| ReferenceGrant | v1beta1 | v1 |
| TLSRoute | v1alpha2 | v1alpha3、v1 |
| TCPRoute / UDPRoute | v1alpha2 | v1 |

GatewayClass、Gateway、HTTPRoute、GRPCRoute 固定使用 v1。如果某个资源的 API 返回 404，相应功能会被关闭，并打出 Warn 日志，写明资源和版本。升级 Gateway API 后，应检查日志里是否出现这类提示。

## 延伸阅读

- [Kubernetes 部署与使用（专题）](../../litegate_k8s_usage_guide.md)
- [Kubernetes 当前能力与边界](../../litegate_kubernetes_capabilities.md)
- [Serve Action](../04-actions/serve.md) · [List](../04-actions/list.md) · [Markdown](../04-actions/markdown.md) · [WebDAV](../04-actions/webdav.md) · [Status](../04-actions/status.md) · [FastCGI](../../fastcgi_config.md)
- [多副本状态与故障隔离](ha-state.md)
- [Helm Chart 说明](../../../../deploy/helm/litegate/README.md)
