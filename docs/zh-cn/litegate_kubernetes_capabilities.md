# LiteGate 如何支持 Kubernetes

> **一句话**:LiteGate 以一个 Pod、**零 client-go** 的纯 REST 方式接入 Kubernetes,同时充当 **Ingress Controller** 和 **Gateway API 实现**——从 L4(TCP/UDP/TLS)到 L7(HTTP/gRPC)的路由、TLS 证书、加权金丝雀、流量镜像、多副本选主全部打通。本文按代码逐层说明它到底做了什么、怎么配、需要什么权限。

本文基于源码核对(非规划文档),所有能力均可在代码中定位。

---

## 一、整体架构

```
                          Kubernetes API Server
                                  │  (纯 REST watch,零 client-go)
   ┌──────────────┬──────────────┼──────────────┬──────────────┐
   ▼              ▼              ▼              ▼              ▼
EndpointSlice  Service       Ingress+Class  Gateway/*Route   Secret
(Pod IP)      (注解元数据)   (L7 路由)      (L4/L7 路由)    (TLS 证书)
   │              │              │              │              │
   └──────────────┴──────┬───────┴──────────────┴──────────────┘
                         ▼
              统一内存路由表 / Stream 表 (CatalogLoader)
                         ▼
         ┌───────────────┴───────────────┐
         ▼                               ▼
   L7 数据面(HTTP/gRPC 代理)      L4 数据面(TCP/UDP/TLS Stream)
         │                               │
         └───────────────┬───────────────┘
                         ▼
                   后端 Pod(直连 Pod IP,绕过 kube-proxy)
```

**关键设计**:
- **零 client-go**:k8s API 本质是 HTTPS + JSON REST,用标准库 `net/http` + ServiceAccount Token 直接 watch,增重仅 ~150KB,保持单二进制。
- **直连 Pod IP**:从 EndpointSlice 拿到真实 Pod 地址直接转发,**绕过 kube-proxy**,让 LiteGate 自己的 LB(P2C / 最小连接 / 被动健康 / 灰度)全部生效。
- **多源统一**:Ingress、Gateway API、Service 注解三条输入源殊途同归,汇进同一张内存路由表,下游数据面不区分来源。

---

## 二、服务发现层(基础)

| 能力 | 说明 |
|---|---|
| **EndpointSlice watch** | 实时拿到每个 Service 背后的 Pod IP + ready 状态,直连转发 |
| **就绪判定遵循官方规范** | `conditions == nil` 或 `ready == nil` 时默认判定为 ready;`terminating`/`serving=false` 的 Pod 不接新流量 |
| **Service watch + 注解路由** | 「Magic Ingress」:在 Service 打 `litegate.io/*` 注解即可声明路由(host/path/lb/auth 等) |
| **In-Cluster 自动配置** | 自动探测 ServiceAccount Token(支持 projected token 轮转)、CA、namespace |
| **RBAC 缺失优雅降级** | 某类资源 403/401 时,该能力自动关闭、退回其余发现模式,不 crash |

多端口 Service:按 Ingress/Route 声明的 `ServicePort` / `PortName` 精确过滤 endpoint。

---

## 三、Ingress Controller 能力

LiteGate 直接消费标准 `networking.k8s.io/v1/Ingress` 对象,可接住存量集群。

### 路由

| 能力 | 说明 |
|---|---|
| **IngressClass 隔离** | watch IngressClass 资源,自动识别 `ingressclass.kubernetes.io/is-default-class: "true"`;只处理属于自己 class 的 Ingress,**不与现有 nginx-ingress 抢流量** |
| **rules → 路由** | host/path 映射为内部路由,backend service 经 EndpointSlice 解析成 Pod |
| **pathType 语义** | `Exact` / `Prefix`(**元素级**:`/foo` 匹配 `/foo/bar` 但不匹配 `/foobar`) / `ImplementationSpecific`;最长前缀优先 |
| **多 path fanout + defaultBackend** | 同 host 多路径生成多路由;defaultBackend 作兜底(含去重) |
| **NGINX 注解子集** | `ssl-redirect`、`proxy-body-size`、`backend-protocol`、超时、CORS、`rewrite-target` 等常见注解映射到内部能力 |

### TLS(from Secret)

| 能力 | 说明 |
|---|---|
| **Secret 证书** | `spec.tls[].secretName` 指向的 `kubernetes.io/tls` Secret 正确用于 SNI 握手,**优先于 ACME** |
| **事件驱动 + 轮转** | watch Secret 事件毫秒级拾取新证,TTL 兜底;cert-manager 轮转后自动更新 |
| **抖动降级** | API 出错时回退到「仍未过期的旧缓存证书」,不误伤在线站点 |

### 控制面回写

`status.loadBalancer` 回写为 LiteGate 的对外地址(**幂等**:已是目标地址则跳过,避免写-事件-写反馈环;自动区分 IP / Hostname)。多副本下由 **leader 唯一回写**(见第六节)。

---

## 四、Gateway API 能力(L4 + L7)

LiteGate 是一个较完整的 Gateway API 实现,覆盖 `gateway.networking.k8s.io/v1` 的 Gateway、HTTPRoute、GRPCRoute,以及 L4 的 TCPRoute / UDPRoute / TLSRoute。

### 通用绑定与安全

| 能力 | 说明 |
|---|---|
| **GatewayClass 认领** | 按 name 认领(默认 `litegate`) |
| **parentRef 绑定** | 支持 Group / Kind / SectionName / Port 全维度校验与协议过滤 |
| **AllowedRoutes 命名空间策略** | 严格符合规范:未配置默认 `Same`(同 namespace),显式 `All` 才允许跨 ns |
| **hostname 严格交集** | listener × route 求交集;通配符严格单层子域(`*.a.com` 不匹配裸域 `a.com`);无交集则不生成路由 |
| **ReferenceGrant 授权校验** | watch + 缓存;**跨命名空间的 backendRef 和 TLS Secret 引用,无匹配 grant 一律拒绝**(真拦截,非仅告警) |

### HTTPRoute / GRPCRoute(L7)

| 能力 | 说明 |
|---|---|
| **match** | path(Exact / PathPrefix)+ method + header 匹配(header `RegularExpression` 暂按 exact 处理) |
| **加权金丝雀 / 流量切分** | 多 backendRef → 复合上游池 `multi:` + `wrr`,流量真正落到各 Service;**权重按 pod 数 LCM 归一化,比例精确**;支持 `weight: 0` 关闭某后端 |
| **Filter** | `RequestHeaderModifier`(set/add/remove → 请求头改写)、`URLRewrite`、`RequestRedirect`;path modifier 按 v1 规范 `replaceFullPath` / `replacePrefixMatch` 解析 |
| **Listener TLS** | `certificateRefs` → Secret 证书,复用 Ingress 的证书体系(含轮转) |

### L4 Route(TCPRoute / UDPRoute / TLSRoute)

| 能力 | 说明 |
|---|---|
| **TCPRoute / UDPRoute** | 由 k8s 对象驱动,接入 Stream 动态发布链路,直连后端 Pod |
| **TLSRoute** | **SNI Passthrough**:在 listener 端口 peek ClientHello 的 SNI,匹配 `hostnames` 后透传到后端(不解密) |
| **加权 / ReferenceGrant** | L4 后端同样支持 `weight`(`weight:0` 跳过)与跨 ns ReferenceGrant 校验 |

> **已知限制**:L4 监听器按 `protocol:port` 唯一,**同一端口只保留第一个 route**(有 warn 日志)。因此「多个 TLSRoute/TCPRoute 对象共用同一 Gateway listener 端口、靠 SNI 在同端口分流」暂不支持;单个 TLSRoute 带多个 hostname 则正常。

---

## 五、L7 数据面能力(与 k8s 正交,Ingress / Gateway API 路由均可用)

这些是 LiteGate 网关自身的能力,任意来源的路由都能挂载:

gRPC、mTLS、粘性会话、重试、熔断、灰度、OAuth2/OIDC 认证、限流、header 重写、status 页、ACME 自动证书、多 LB 策略(P2C / 最小连接 / 轮询 / 被动异常点检测)。

---

## 六、生产特性

### 多副本 HA(Lease 选主)

- 基于 `coordination.k8s.io/v1` **Lease** 的轻量选主,**零 client-go**。
- **无脑裂**:renew/acquire 走 `resourceVersion` 乐观锁 PUT,两个节点同时抢过期 lease 时后写者拿 409 Conflict、不会当选。
- **仅 leader 写 status**:Ingress status 回写前检查 `IsLeader()`,多副本不互相覆盖。

### 流量镜像(mirror 中间件)

- 按百分比异步镜像请求到影子服务(`X-Forwarded-Shadow: true` 标记)。
- **并发安全**:同步克隆 header + 快照 method/URI/host 后再起 goroutine(杜绝请求头并发读写)。
- **自我保护**:信号量限流(默认 2048)、4MB body 上限、剥离 hop-by-hop 头。

---

## 七、配置示例

```yaml
service_discovery:
  providers:
    k8s:
      # 连接:In-Cluster 时可全部留空,自动探测
      # base_url: https://kubernetes.default.svc
      namespace: ""                          # 空 = 全集群
      # Ingress
      ingress_class: litegate                # 认领的 IngressClass(默认 litegate)
      is_default_ingress_class: false        # 也可靠 watch IngressClass 资源自动判定
      # Gateway API
      gateway_class: litegate
      # watch 开关(默认全开;按需关闭以精简 RBAC)
      # disable_service_watch: false
      # disable_ingress_watch: false
      # disable_gateway_watch: false
      # disable_httproute_watch: false
      # 控制面回写
      publish_status_address: "203.0.113.10" # 回写到 Ingress status 的对外 IP/域名
```

**Service 注解方式(Magic Ingress,轻量场景可替代 Ingress 对象)**:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-app
  labels: { litegate.io/expose: "true" }
  annotations:
    litegate.io/host: "app.example.com"
    litegate.io/prefix: "/api"
```

---

## 八、RBAC 最小权限

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: litegate-k8s
rules:
  # 服务发现
  - apiGroups: ["discovery.k8s.io"]
    resources: ["endpointslices"]
    verbs: ["list", "watch"]
  - apiGroups: [""]
    resources: ["services"]
    verbs: ["list", "watch"]
  # Ingress
  - apiGroups: ["networking.k8s.io"]
    resources: ["ingresses", "ingressclasses"]
    verbs: ["list", "watch"]
  - apiGroups: ["networking.k8s.io"]
    resources: ["ingresses/status"]
    verbs: ["update"]                 # status 回写
  # Gateway API
  - apiGroups: ["gateway.networking.k8s.io"]
    resources: ["gateways", "httproutes", "grpcroutes", "tcproutes", "udproutes", "tlsroutes", "referencegrants"]
    verbs: ["list", "watch"]
  # TLS Secret(建议限定 namespace)
  - apiGroups: [""]
    resources: ["secrets"]
    verbs: ["get", "list", "watch"]
  # 多副本选主
  - apiGroups: ["coordination.k8s.io"]
    resources: ["leases"]
    verbs: ["get", "create", "update"]
```

> 任一资源无权限时,对应能力自动降级关闭、不影响其余功能。

---

## 九、能力总览

| 层 | 能力 | 状态 |
|---|---|---|
| 发现 | EndpointSlice / Service watch、直连 Pod IP、多端口过滤 | ✅ |
| Ingress | IngressClass(资源 watch + 默认类)、pathType 元素级、fanout、defaultBackend、status 回写、注解子集 | ✅ |
| Ingress TLS | Secret 证书 + 事件驱动轮转 + 抖动降级 | ✅ |
| Gateway L7 | Gateway/HTTPRoute/GRPCRoute、AllowedRoutes、hostname 交集、加权金丝雀(LCM 精确)、Filter、Listener TLS | ✅ |
| Gateway L4 | TCPRoute/UDPRoute/TLSRoute(SNI Passthrough) | ✅(同端口单 route) |
| 安全 | ReferenceGrant 跨 ns 授权(backendRef + TLS)强制校验 | ✅ |
| 生产 | Lease 选主(无脑裂)、流量镜像 | ✅ |

### 尚未实现 / 已知限制

- **CRD 配置模型**:无 Traefik 式 `IngressRoute`/`Middleware`/`TLSOption` CRD 与可复用中间件编排。
- **L4 同端口多 route**:同一 `protocol:port` 只生效第一个 route(见第四节)。
- **Gateway API status conditions**:Ingress status 已回写,Gateway/HTTPRoute 的 `Accepted`/`Programmed` 等 conditions 回写仍在完善。
- **nginx 注解覆盖**:仅常见 ~7 类,冷门注解会被忽略。
- **cert-manager 深度协同**:消费其生成的 Secret,但无 per-Ingress ACME / challenge 协同。
- **header `RegularExpression` 匹配**:暂按 exact 处理。

---

## 附:相关文档

- Ingress 实现方案:[litegate_ingress_controller_implementation.md](https://github.com/jamesleeon/LiteGate/blob/master/docs/zh-cn/litegate_ingress_controller_implementation.md)
- Gateway API 实现方案:[litegate_gateway_api_implementation.md](https://github.com/jamesleeon/LiteGate/blob/master/docs/zh-cn/litegate_gateway_api_implementation.md)
- 轻量 k8s 集成:[litegate_lightweight_k8s_integration.md](litegate_lightweight_k8s_integration.md)
