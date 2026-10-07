# 在 Kubernetes 中使用 LiteGate(操作指南)

> **本文面向使用者**,按任务讲「怎么做」:部署 → 暴露服务(Ingress / 注解 / Gateway API)→ HTTPS → 金丝雀 → L4 → 流量治理(CRD)→ HA / 镜像 → 排错。所有 YAML 可直接复制。
>
> 想了解「LiteGate 在 k8s 支持到什么程度」,见 [litegate_kubernetes_capabilities.md](litegate_kubernetes_capabilities.md)。

---

## 0. 关键标识(记住这几个名字)

| 项 | 值 |
|---|---|
| IngressClass 名 | `litegate`(默认类,`is-default-class: true`) |
| Ingress controller | `litegate.io/ingress-controller` |
| GatewayClass 名 | `litegate` |
| Gateway controllerName | `litegate.io/gateway-controller` |
| 流量策略 CRD | `LiteGateTrafficPolicy`(group `litegate.io/v1alpha1`,namespaced) |

---

## 1. 部署 LiteGate

### 方式 A:Helm

```bash
helm install litegate ./deploy/helm/litegate -n litegate-system --create-namespace
```

### 方式 B:原生 manifests

```bash
kubectl apply -f deploy/k8s/crds/          # 先装 CRD
kubectl apply -f deploy/k8s/               # RBAC / Deployment / Service / GatewayClass / IngressClass
```

部署后 LiteGate 以 Pod 运行,自动 In-Cluster 认证(ServiceAccount Token),开始 watch 集群资源。对外入口由它自己的 `Service`(`type=LoadBalancer` 或 `NodePort`)暴露——**Ingress/Gateway 对象只决定"进来后怎么分流",让流量"进得来"靠这个 Service + DNS 指向它。**

> RBAC 已包含所需全部权限(endpointslices/services/secrets、ingresses、六类 Gateway Route、referencegrants、backendtlspolicies、litegatetrafficpolicies、leases)。某类无权限时对应能力自动降级关闭,不影响其余。

---

## 2. 暴露一个 HTTP 服务

假设你有 Service `my-app`(namespace `default`,端口 80)。三选一:

### 方式一:标准 Ingress(接住存量 YAML)

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-app
spec:
  ingressClassName: litegate            # 认领给 LiteGate;不写则因是默认类也会接管
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /api
        pathType: Prefix                # Exact / Prefix(元素级)/ ImplementationSpecific
        backend:
          service:
            name: my-app
            port: { number: 80 }
```

常用 NGINX 注解可直接复用(会被映射):`ssl-redirect`、`proxy-body-size`、`backend-protocol`、超时、CORS、`rewrite-target`。

### 方式二:Service 注解(Magic Ingress,最省事)

不写 Ingress 对象,直接在 Service 上打注解:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-app
  labels:
    litegate.io/expose: "true"          # 必须:声明纳入路由
  annotations:
    litegate.io/host: "app.example.com"
    litegate.io/prefix: "/api"          # 或 litegate.io/path 精确匹配
    litegate.io/strip-prefix: "true"    # 可选:转发前去掉前缀
    litegate.io/lb: "p2c"               # 可选:负载均衡策略
```

> 适合轻量场景;缺点是私有约定、无全局视图。规模大 / 要被生态工具看见 → 用 Ingress 或 Gateway API。

### 方式三:Gateway API(推荐,面向未来标准)

先建一个 Gateway(通常集群里建一次),再挂 HTTPRoute:

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: litegate-gw
spec:
  gatewayClassName: litegate
  listeners:
  - name: http
    protocol: HTTP
    port: 80
    allowedRoutes:
      namespaces: { from: Same }        # 默认 Same;跨 ns 用 All(并配 ReferenceGrant)
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: my-app
spec:
  parentRefs:
  - name: litegate-gw
  hostnames: ["app.example.com"]
  rules:
  - matches:
    - path: { type: PathPrefix, value: /api }
      headers:                          # 可选:支持 Exact 与 RegularExpression
      - name: x-canary
        type: RegularExpression
        value: "^v[0-9]+$"
    backendRefs:
    - name: my-app
      port: 80
```

---

## 3. HTTPS / TLS

把证书放进标准 `kubernetes.io/tls` Secret(cert-manager 生成的也行),Ingress 引用即可:

```yaml
spec:
  tls:
  - hosts: ["app.example.com"]
    secretName: app-tls
```

- LiteGate **watch Secret 事件、毫秒级拾取轮转**,cert-manager 续期后自动更新。
- Secret 证书**优先于内置 ACME**;证书临时不可用时会回退到未过期的旧证,不误伤在线站点。
- Gateway API 用 Listener 的 `certificateRefs` 引用 Secret,语义相同。

---

## 4. 金丝雀 / 加权流量切分

HTTPRoute 多 backendRef 带 `weight` 即可,**流量真正按比例落到各 Service**,权重按 pod 数自动归一化(比例精确):

```yaml
  rules:
  - backendRefs:
    - name: my-app-v1
      port: 80
      weight: 90
    - name: my-app-v2          # 金丝雀
      port: 80
      weight: 10               # weight: 0 可临时关闭某后端
```

---

## 5. gRPC 与 L4(TCP / UDP / TLS)

### gRPC(GRPCRoute)

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: GRPCRoute
metadata:
  name: my-grpc
spec:
  parentRefs: [{ name: litegate-gw }]
  hostnames: ["grpc.example.com"]
  rules:
  - matches:
    - method: { service: my.pkg.Greeter, method: SayHello }
    backendRefs: [{ name: greeter, port: 50051 }]
```

### TCP / UDP / TLS Route(L4)

在 Gateway 上加对应协议的 listener,再挂 Route。TLSRoute 走 **SNI Passthrough**(按 SNI 透传、不解密):

```yaml
apiVersion: gateway.networking.k8s.io/v1alpha2
kind: TLSRoute
metadata:
  name: my-tls
spec:
  parentRefs: [{ name: litegate-gw, sectionName: tls }]
  hostnames: ["secure.example.com"]
  rules:
  - backendRefs: [{ name: backend-svc, port: 8443 }]
```

> **限制**:同一 `protocol:port` 只生效第一个 route;多个 TLSRoute 靠 SNI 在同一端口分流暂不支持(单个 TLSRoute 带多个 hostname 正常)。

---

## 6. 流量治理:LiteGateTrafficPolicy(CRD)

对某个 HTTPRoute 或 Gateway 附加重试 / 超时 / 限流 / 熔断 / WAF / CORS / 并发限制,无需改路由本身:

```yaml
apiVersion: litegate.io/v1alpha1
kind: LiteGateTrafficPolicy
metadata:
  name: api-policy
spec:
  targetRef:                       # 直接附着到某个 Route(最具体者胜)
    group: gateway.networking.k8s.io
    kind: HTTPRoute
    name: my-app
  retry: 2
  timeout: 10                      # 秒
  rateLimit: { qps: 200, policy: adaptive }
  circuitBreaker: { tripThreshold: 5, timeout: 30s, maxRequests: 10 }
  cors:
    enabled: true
    allowedOrigins: ["https://foo.com"]
  limitConn: { maxConcurrent: 1000, maxPerIP: 20 }   # 全局并发 / 每客户端 IP 并发
  waf: { enabled: true, blockSuspicious: true }
```

**附着优先级**:直接 targeting HTTPRoute > targeting 父 Gateway;同级冲突按 **创建时间最旧者胜**、并列按 namespace/name 字典序(符合 Gateway API 规范)。

> `limitConn` 支持 `maxConcurrent`(按路由全局并发)与 `maxPerIP`(按客户端 IP 并发,支持本地 + Redis 分布式计数)。同时设置时 **`maxPerIP` 优先生效**。

### BackendTLSPolicy(到后端的 TLS)

标准 Gateway API `BackendTLSPolicy` 也支持,用于给到后端的连接配置 CA / SNI 校验(仅限同 namespace 目标)。

---

## 7. 多副本高可用

直接把 Deployment 副本数调大即可。LiteGate 用 Kubernetes **Lease 选主**(`resourceVersion` 乐观锁,无脑裂):

- 所有副本都转发流量(数据面全活)。
- 只有 **leader 回写 Ingress `status.loadBalancer`**,多副本不互相覆盖。

需要把对外地址回写到 Ingress status,配置 `publish_status_address`:

```yaml
service_discovery:
  providers:
    k8s:
      publish_status_address: "203.0.113.10"   # LB 的对外 IP 或域名
```

---

## 8. 流量镜像(灰度验证 / 影子测试)

给站点挂 `mirror` 中间件,按比例把请求**异步**复制到影子服务(不影响主链路):

```yaml
middlewares:
  mirror:
    target: "shadow-svc.default.svc.cluster.local:80"
    percent: "10"        # 镜像 10% 流量
```

镜像请求带 `X-Forwarded-Shadow: true`;内部有并发限流(默认 2048)与 4MB body 上限保护。

---

## 9. 排错清单

| 现象 | 排查 |
|---|---|
| 路由不生效 | ① Ingress 的 `ingressClassName` 是否 `litegate`;② Service 注解方式是否有 `litegate.io/expose: "true"`;③ 看 LiteGate 日志有无「识别到 Ingress/Route」 |
| 外网访问不到 | Ingress 只管分流。检查 LiteGate 自身 Service 是否 `LoadBalancer`/`NodePort` 暴露 + **DNS 是否指向它** |
| 后端 502 / no backend | backend Service 是否有 ready 的 Pod;多端口时 `port` 是否写对(按 ServicePort/PortName 过滤) |
| TLS 握手失败 | Secret 是否 `kubernetes.io/tls` 类型、`tls.crt`/`tls.key` 是否齐全;跨 ns 引用是否配了 ReferenceGrant |
| 跨 namespace backendRef 被拒 | Gateway API 要求 `ReferenceGrant`;无匹配 grant 会被**拒绝**(日志有 `rejected`) |
| TrafficPolicy 没生效 | `targetRef` 的 kind/name/namespace 是否匹配目标;`kubectl get litegatetrafficpolicy -o yaml` 看 status conditions |
| 金丝雀比例不对 | 确认用的是 HTTPRoute 多 backendRef weight(比例已按 pod 数归一化) |
| L4 同端口多路由只有一个生效 | 已知限制,见第 5 节;换不同端口或合并到一个 route |

**通用**:
```bash
kubectl get ingress,httproute,grpcroute,tlsroute,gateway -A     # 看资源被识别
kubectl get litegatetrafficpolicy -A -o wide                    # 看策略 status
kubectl logs -n litegate-system deploy/litegate -f              # 看识别/拒绝日志
```

---

## 附:选型速查

| 场景 | 用什么 |
|---|---|
| 接住存量 Ingress YAML | 标准 **Ingress** |
| 单服务、图省事 | **Service 注解**(Magic Ingress) |
| 新集群、复杂路由、面向未来 | **Gateway API**(HTTPRoute/GRPCRoute) |
| 金丝雀 / 加权 | HTTPRoute 多 backendRef weight |
| TCP/UDP/TLS 透传 | Gateway API **L4 Route** |
| 重试/限流/熔断/WAF | **LiteGateTrafficPolicy** CRD |
