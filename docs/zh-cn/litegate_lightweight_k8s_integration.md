# LiteGate 轻量级支持 Kubernetes 实现方案（Zero client-go）

> **一句话**：LiteGate 部署成一个 Pod，用**纯 REST API**（`net/http` + Service Account Token）watch Kubernetes 的 **EndpointSlice**，拿到每个服务背后的实时 pod IP 列表，喂给现有的负载均衡直接转发。**不引入 client-go，保持单二进制、轻量。**

---

## 一、目标与定位

### 要解决的问题
让 LiteGate 能在 Kubernetes 里跑，并**原生发现 k8s 服务的 pod 端点**，从而用自己的负载均衡（P2C / 最小连接 / 被动异常点检测 / 灰度）转发流量——而不是退化成 kube-proxy 的傻轮询。

### 硬约束（产品定位）
- **单二进制与默认内置**：k8s 能力默认直接编进 LiteGate 单二进制，部署即用，不需要额外编译参数，不需要额外 companion。
- **零 client-go**：拒绝 `k8s.io/client-go` / `api` / `apimachinery`（它们会给二进制增加 ~15–20MB 和一大棵依赖树）。k8s API 本质是 HTTPS + JSON 的 REST 接口，直接标准库裸调，增重仅 ~150KB，非 k8s 场景不启用时零运行时开销。

### 明确的范围边界
本方案**只做「端点发现（Endpoint Discovery）」这一层**。这是 LiteGate 现有服务发现模型的自然延伸——k8s 只是「又一个发现源」，和 consul/docker/litemesh 平级。

**路由仍然由 LiteGate 自己的配置 / 发现系统提供**，不依赖 k8s 的 Ingress/Gateway CRD。对以「二进制 + 服务发现」为核心模式的部署来说，这就是**完整方案**——因为我们只缺「服务背后有哪些活着的 pod」，路由本来就自己配。

---

## 二、核心认识（为什么 REST 就够了）

### 1. k8s API = 一个 HTTPS + JSON 的 REST 服务器
client-go 只是它的胖封装。任何语言用 HTTP 客户端都能直接调它：
```
GET https://kubernetes.default.svc/apis/discovery.k8s.io/v1/namespaces/{ns}/endpointslices?labelSelector=kubernetes.io/service-name={svc}
Authorization: Bearer <ServiceAccount Token>
```
返回 JSON：每个 pod 的 IP + 是否 ready + 端口。加 `&watch=1` 就变成**持续推送变化的长连接**。

### 2. pod IP 在集群内可直连
k8s 是扁平网络，任意 pod 都能直接拨通任意 pod 的 IP。**拿到 pod IP 后直接 dial 即可**，不经过 kube-proxy、不需要 NAT。这正是「自己做 LB」优于「代理到 Service ClusterIP」的原因。

### 3. 拿 pod IP 有「轻重三档」
| 档 | 做法 | 代码量 | 代价 |
|---|---|---|---|
| 最省 | 代理到 **Service DNS**（`svc.ns.svc.cluster.local`）| 零 | kube-proxy 傻轮询，**用不上你的 LB** |
| 很省 | 代理到 **headless Service** DNS → 返回全部 pod IP，定期重解析 | 零/极少 | 靠 DNS TTL，更新有延迟，无 ready 状态 |
| **正规（本方案）** | **REST watch EndpointSlice** | 几百行 | 实时 + ready 状态，**你的 LB 全生效** |

> 建议先用「headless Service + DNS」零代码验证能跑通，再上 EndpointSlice watch 拿实时性与自有 LB。

---

## 三、整体架构

```
        外部流量
           │
           ▼  (k8s Service: LoadBalancer / NodePort，纯 k8s 网络，无需 LiteGate 代码)
┌──────────────────────────────────────────────┐
│  LiteGate Pod（单二进制，默认内置）           │
│                                                │
│   ┌────────────────────────────────────────┐  │
│   │ provider/k8s（raw REST，零 client-go）  │  │
│   │  Start(): watch EndpointSlice 事件循环   │  │
│   │  cache: service → []pod endpoint         │  │
│   └───────────────┬────────────────────────┘  │
│                   │ 喂入现有 discovery.Client   │
│                   ▼                            │
│   现有 LB（P2C / LeastConn / 异常点检测 / 灰度）│
│                   │                            │
└───────────────────┼────────────────────────────┘
                    ▼  直连 pod IP（集群内可路由）
        [ pod ]  [ pod ]  [ pod ]  ...
```

- **入站**：在 LiteGate 前面放一个普通的 k8s Service（LoadBalancer/NodePort）把流量导进来——这是纯 k8s 网络配置，**LiteGate 不写任何代码**。
- **出站/发现**：provider/k8s 用 REST watch 拿 pod IP，喂给现有 LB，直连 pod。**这是唯一要写的代码。**

---

## 四、与现有代码的对接（关键：完全复用现有抽象）

### 1. 复用 `discovery.Client` 接口
现有接口（`internal/discovery/types.go`）：
```go
type Client interface {
    GetInstances(ctx context.Context, req *DiscoveryRequest) ([]*ServiceEndpoint, error)
    Snapshot(req *DiscoveryRequest) ([]*ServiceEndpoint, bool)
    SetInstances(req *DiscoveryRequest, endpoints []*ServiceEndpoint)
}
```

### 2. 新增 `internal/provider/k8s`，**镜像 `provider/docker` 的形态**
`DockerDiscovery` 的结构直接照抄，只把「事件源」从 docker events 换成 k8s EndpointSlice watch：

| provider/docker | provider/k8s（新增） |
|---|---|
| `cache map[service][]*ServiceEndpoint` | 一样 |
| `Start()` 起 docker 事件循环 → 重建 cache → `notifyWatchers()` | `Start()` 起 **EndpointSlice raw-REST watch 循环** → 重建 cache → `notifyWatchers()` |
| `GetInstances(req)` 返回 `CloneEndpoints(cache[svc])` | 一样 |
| `WatchServices(cb)` 注册 reload 回调 | 一样 |

**也就是说：LB、健康、灰度、reload 通知，全部零改动复用。k8s provider 只负责把 pod IP 填进 cache。**

### 3. 零编译负担，默认全量内置
- 纯标准库实现，增重仅 ~150KB，**默认 `go build` 直接内置**。
- 用户无需在编译时指定 `-tags k8s`，同一份通用二进制在裸金属、Docker、Kubernetes 等所有场景开箱即用。

---

## 五、关键技术点（可行性核对清单）

### 1. 集群内认证（In-Cluster，零配置）
LiteGate Pod 自动挂载：
- **Token**：`/var/run/secrets/kubernetes.io/serviceaccount/token`（会轮转，**每次请求前重读文件**，不要缓存内容）
- **CA 证书**：`/var/run/secrets/kubernetes.io/serviceaccount/ca.crt`（用它校验 API server TLS）
- **命名空间**：`/var/run/secrets/kubernetes.io/serviceaccount/namespace`
- **API 地址**：`https://kubernetes.default.svc`（或环境变量 `KUBERNETES_SERVICE_HOST` / `KUBERNETES_SERVICE_PORT`）

不需要 kubeconfig、不需要外部凭据。

### 2. RBAC（最小权限）
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: litegate-endpoint-reader
rules:
  - apiGroups: ["discovery.k8s.io"]
    resources: ["endpointslices"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: litegate-endpoint-reader
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: litegate-endpoint-reader
subjects:
  - kind: ServiceAccount
    name: litegate
    namespace: default
```
> 只读 `endpointslices` 就够——服务名通过 slice 上的 `kubernetes.io/service-name` 标签识别，连 `services` 都不用读。

### 3. Watch 机制（复用 litemeshsdk 的骨架）
你 `internal/litemeshsdk/watch.go` 里已有 resourceVersion + 退避重连的成熟骨架，k8s watch 是同一套：
1. **List** 一次：`GET .../endpointslices?labelSelector=...`，从返回体 `metadata.resourceVersion` 拿到起点 `rv`，并初始化全量 cache。
2. **Watch**：`GET .../endpointslices?watch=1&resourceVersion={rv}&allowWatchBookmarks=true`，服务端以换行分隔的 JSON 流持续推送：
   ```json
   {"type":"ADDED","object":{...EndpointSlice...}}
   {"type":"MODIFIED","object":{...}}
   {"type":"DELETED","object":{...}}
   {"type":"BOOKMARK","object":{"metadata":{"resourceVersion":"12345"}}}
   ```
   每收到事件更新 cache + `notifyWatchers()`；BOOKMARK 用于推进本地 `rv`。
3. **`410 Gone`**（rv 过期）→ 丢弃 rv，回到步骤 1 **relist**。
4. **断线** → 指数退避重连（litemeshsdk 现成）。

### 4. 只解析需要的字段（最小 struct，零 k8s 类型依赖）
不引入 `k8s.io/api`，自己定义需要的那几个字段即可：
```go
type endpointSlice struct {
    Metadata struct {
        ResourceVersion string            `json:"resourceVersion"`
        Labels          map[string]string `json:"labels"`  // kubernetes.io/service-name
    } `json:"metadata"`
    AddressType string `json:"addressType"` // IPv4 / IPv6 / FQDN
    Endpoints   []struct {
        Addresses  []string `json:"addresses"`
        Conditions struct {
            Ready       *bool `json:"ready"`
            Terminating *bool `json:"terminating"`
        } `json:"conditions"`
    } `json:"endpoints"`
    Ports []struct {
        Name     string `json:"name"`
        Port     int    `json:"port"`
        Protocol string `json:"protocol"`
    } `json:"ports"`
}
```

### 5. ready 过滤
只把 `conditions.ready == true`（且非 `terminating`）的地址纳入 endpoint 列表，避免把流量打给未就绪 / 正在下线的 pod。

### 6. 降级安全（重要）
API server 不可达 / watch 断开时，**保留 last-known cache 继续服务**，只是不更新，绝不清空。恢复后 relist 补齐。这样 k8s 控制面抖动不影响数据面转发。

---

## 六、明确不做（保持轻量的边界）

| 不做 | 原因 |
|---|---|
| **client-go / apimachinery / api** | 重量来源，本方案的核心就是绕开它 |
| **Ingress / Gateway API Controller** | 路由由 LiteGate 自己的配置系统给，不需要读 k8s CRD |
| **Gateway API `.status` 写回 / conformance** | 那是真正的 controller 活（多 CRD、condition、冲突处理），逻辑重；本方案不追求「当集群标准 ingress」 |
| **CPU/调度相关** | 与网关无关 |

> 若未来确有「读 Ingress 自动配路由」的需求，可用**同一套 raw REST** 补一个 Ingress 只读 watch（依然零 client-go）；Gateway API 全套 conformance 若真要，再单独议一个可选 companion——但不塞进数据面。

---

## 七、部署形态（示意）

```yaml
apiVersion: apps/v1
kind: Deployment
metadata: { name: litegate }
spec:
  replicas: 2
  template:
    spec:
      serviceAccountName: litegate          # 绑定上面的 RBAC
      containers:
        - name: litegate
          image: litegate:latest            # 标准通用单二进制镜像
          ports: [{ containerPort: 80 }, { containerPort: 443 }]
---
apiVersion: v1
kind: Service                               # 入站流量入口（纯 k8s 网络）
metadata: { name: litegate }
spec:
  type: LoadBalancer
  selector: { app: litegate }
  ports: [{ port: 80, targetPort: 80 }, { port: 443, targetPort: 443 }]
```

---

## 八、验证路径（先跑通再接入，降低风险）

1. **零代码验证连通性**：把某条上游指向一个 **headless Service** 的 DNS，确认 LiteGate 能解析到 pod IP 并转发。证明「不写 k8s 代码也能在集群里转发」。
2. **独立 REST watch demo**：几十行独立程序，在集群里 watch 一个服务的 EndpointSlice，打印 pod IP 的实时增删。**亲眼确认「REST 就够，无需 client-go」。**
3. **接入 provider**：把 watch 循环包进 `internal/provider/k8s`，实现 `Start()/GetInstances()`，跑通端到端。

---

## 九、工作量与风险

| 项 | 评估 |
|---|---|
| 代码量 | provider/k8s 约 **400–600 行**（含纯 Go struct + watch 循环 + cache 重建 + Service 注解映射） |
| 依赖增量 | **0 个新第三方依赖**（纯标准库 `net/http`/`encoding/json`/`crypto/tls`） |
| 二进制增量 | 增重仅 **~150KB**，默认全量内置，无需 `-tags` 参数，不启用时零运行时开销 |
| 主要风险点 | watch 的 `410 relist` / 断线重连正确性；ready/terminating 状态过滤；token 轮转需每次重读 |
| 不确定性 | 低——k8s EndpointSlice & Service API 稳定，字段简单 |

---

## 十、里程碑与演进路线

1. **M1 端点发现（已完工）**：`provider/k8s` raw-REST watch EndpointSlice → 现有 LB 直连 Pod IP。保持零 client-go，支持 P2C 负载均衡与被动异常点自愈。
2. **M1.5 声明式 Opt-In 自动路由（已完工）**：
   - 增加纯 REST 的 **Service Metadata Watch**（带 `labelSelector=litegate.io/expose=true` 服务端过滤，彻底避免系统服务污染）；
   - 自动解析 Service 上的 Annotations（`litegate.io/domain`, `litegate.io/path`, `litegate.io/lb` 等）并与 EndpointSlice 实时 Pod IP 双流聚合；
   - 接入 `CatalogLoader`（Magic Ingress），实现无需手写网关配置即可自动声明式发布 K8s 业务路由。
3. **M2（可选）Ingress 只读**：同套 raw REST 读 Ingress v1 生成基础路由。
4. **M3（可选、按需）Gateway API**：只在真有集群标准 ingress 需求时评估，倾向单独 companion，不入数据面。

---

## 十一、M1.5 声明式 Annotation 配置规范

业务团队只需在自己的 K8s Service 上打上 `labels` 和 `annotations`，LiteGate 就会在毫秒内自动为其生成路由并挂载 Pod 负载均衡：

```yaml
apiVersion: v1
kind: Service
metadata:
  name: order-service
  namespace: prod
  labels:
    litegate.io/expose: "true"                 # <--- 必须: Opt-In 开关，避免系统服务污染
  annotations:
    litegate.io/domain: "order.example.com"    # <--- 绑定的外网域名 (支持逗号分隔多个域名)
    litegate.io/path: "/api/orders"            # <--- 路由前缀匹配
    litegate.io/lb: "p2c"                      # <--- 负载均衡策略 (p2c, least_conn, round_robin)
    litegate.io/strip-path: "false"            # <--- 是否剥离路由前缀
    litegate.io/auth: "auto"                   # <--- 自动挂载全局身份认证
spec:
  selector: { app: order-api }
  ports:
    - name: http
      port: 8080
```

---

## 结论

**可行，而且对 LiteGate 的定位是最优解**：用纯 REST 双流汇聚（EndpointSlice + Service）把 k8s 变成原生发现源与声明式路由源，**单二进制 + 零 client-go + 轻量 + 零系统服务污染**四者兼得，既保住产品身份，又能理直气壮地说「支持 Kubernetes 原生声明式路由」。
