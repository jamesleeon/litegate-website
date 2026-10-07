# LiteGate 消费 Kubernetes 服务实战指南

> **导读**：本文档详细指导如何在 Kubernetes 集群内或集群外部署 LiteGate，如何配置 LiteGate 消费 K8s 内部微服务，以及后端研发如何在 Kubernetes `Service` 上编写元数据实现**声明式自动路由发布（Magic Ingress）**与**直连 Pod 的高性能负载均衡**。

---

## 一、架构定位与工作原理

LiteGate 采用 **Zero client-go（纯标准库 REST + HTTP Streaming Watch）** 的原生架构，直接与 Kubernetes API Server 通信。

```
                                    外部流量 (HTTP / HTTPS / gRPC)
                                                 │
                                                 ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  LiteGate 网关节点 (单二进制)                                                           │
│                                                                                        │
│   ┌───────────────────────────────────┐    ┌──────────────────────────────────────┐   │
│   │ 模式 A: 显式站点配置               │    │ 模式 B: 声明式自动聚合 (Magic Ingress) │   │
│   │ sites/api.yaml (集中掌控)          │    │ CatalogLoader (监听 Service 注解)     │   │
│   └─────────────────┬─────────────────┘    └──────────────────┬───────────────────┘   │
│                     │                                         │                       │
│                     ▼                                         ▼                       │
│   ┌───────────────────────────────────────────────────────────────────────────────┐   │
│   │ K8sDiscovery 引擎                                                              │   │
│   │ ├── 流 1: Watch /api/v1/services (按 litegate.io/expose=true 过滤路由元数据)     │   │
│   │ └── 流 2: Watch /apis/discovery.k8s.io/v1/endpointslices (实时健康 Pod IP)      │   │
│   └───────────────────────────────────────┬───────────────────────────────────────┘   │
│                                           │                                           │
│   ┌───────────────────────────────────────▼───────────────────────────────────────┐   │
│   │ LiteGate 7层流量治理引擎 (P2C / LeastConn / 被动异常点自愈 / 灰度切流 / TLS)       │   │
│   └───────────────────────────────────────┬───────────────────────────────────────┘   │
└───────────────────────────────────────────┼────────────────────────────────────────────┘
                                            ▼  直连 Pod IP (绕过 kube-proxy 傻轮询与 iptables)
                  [ Pod: 10.244.1.10 ]   [ Pod: 10.244.2.20 ]   [ Pod: 10.244.3.30 ]
```

### 两种消费模式
1. **模式 A：显式掌控模式（手动配置 YAML）**
   * 网关所有路由、证书、WAF、IDS 在 LiteGate 的 `sites/*.yaml` 中集中定义；
   * 后端指向 `upstream_type: "k8s"`，LiteGate 实时同步该 Service 背后**所有存活且 Ready 的 Pod IP** 直接做 P2C 负载均衡。
2. **模式 B：声明式 Opt-In 自动路由（Magic Ingress）**
   * 业务研发在自己的 Kubernetes `Service` 上打上 `litegate.io/expose: "true"` 和相关注解；
   * LiteGate 自动感知并在毫秒内将其编译进内存路由表，零手工配置即可上线。

---

## 二、LiteGate 网关端配置

LiteGate 的主配置文件为 `config.yaml`。

### 1. 集群内部署（In-Cluster 模式，最推荐）
当 LiteGate 以 Pod 形式运行在 Kubernetes 集群内时，系统会**自动探测**并加载 ServiceAccount 凭证（`/var/run/secrets/kubernetes.io/serviceaccount/`），无需手动填写 API 地址与 Token。

```yaml
# config.yaml
server:
  http_port: 80
  https_port: 443
  dashboard_port: 9090

service_discovery:
  # 开启声明式自动聚合扫描
  catalogs:
    - provider: "k8s"
      enabled: true
      namespace: ""            # 空表示监听全集群; 也可指定具体 namespace 如 "prod"
      # 适用于 catalog k8s 的连接参数（集群外请保留；若不配则按 In-Cluster 检测）
      token_file: "/var/run/secrets/kubernetes.io/serviceaccount/token"
      insecure_skip_verify: false
      interval: 30s

  # 底层 Kubernetes Provider 配置
  providers:
    k8s:
      # 集群内运行时，base_url, token, ca_file 留空即可，自动探测加载
      namespace: ""
      # 仅暴露显式打了 Opt-In 标签的 Service (源头防污染)
      service_label_selector: "litegate.io/expose=true"
```

### 2. 集群外部署（External 模式）
若 LiteGate 运行在独立虚机或外部网关机房，需配置远程 API Server 访问地址：

```yaml
service_discovery:
  providers:
    k8s:
      base_url: "https://k8s-api.example.com:6443"
      token: "eyJhbGciOiJSUzI1NiIsImtpZCI6..."     # ServiceAccount Bearer Token
      ca_file: "/etc/litegate/certs/k8s-ca.crt"    # 集群 CA 证书路径
      insecure_skip_verify: false
      namespace: "prod"
```

---

## 三、模式 A：显式路由手动消费示例

在 `sites/` 目录下创建站点路由规则，将后端指向 Kubernetes 服务：

```yaml
# sites/api.example.com.yaml
api.example.com:
  entrypoint: ":443"
  routes:
    # 场景 1: 普通代理 (指向 default 命名空间的 user-service)
    - match:
        path_prefix: "/api/users"
      action:
        type: proxy
        upstream_type: "k8s"
        service_name: "user-service"               # 或 "default/user-service"
        load_balancer: "p2c"                       # 支持 p2c, least_conn, round_robin
        timeout: 10s
        retry: 2

    # 场景 2: 金丝雀灰度发布 (根据 Pod 标签切流)
    - match:
        path_prefix: "/api/orders"
        headers:
          X-Canary: "true"
      action:
        type: proxy
        upstream_type: "k8s"
        service_name: "prod/order-service"
        route_tags: ["version=v2"]                 # 仅打到带 version=v2 标签的 Pod
        load_balancer: "p2c"

    # 场景 3: 默认走生产稳定版
    - match:
        path_prefix: "/api/orders"
      action:
        type: proxy
        upstream_type: "k8s"
        service_name: "prod/order-service"
        route_tags: ["version=v1"]
        load_balancer: "p2c"
```

---

## 四、模式 B：Kubernetes Service 元数据打标规范（Magic Ingress）

后端业务团队在编写微服务 `Service` YAML 时，只需打上标准元数据即可自动发布：

### 1. 最简 Service 示例

```yaml
apiVersion: v1
kind: Service
metadata:
  name: billing-service
  namespace: prod
  labels:
    # 【必须】Opt-In 开关，避免无关服务被发布
    litegate.io/expose: "true"
  annotations:
    # 域名，逗号分隔多个
    litegate.io/host: "billing.example.com,pay.example.com"
    # 路径前缀；精确路径用 litegate.io/path
    litegate.io/prefix: "/api/billing"
    # 转发前剥离匹配的路径
    litegate.io/strip-path: "true"
spec:
  selector:
    app: billing-api
  ports:
    - name: http
      port: 8080
      targetPort: 8080
```

这组简写注解等价于快捷模式，在 80 与 443 上生效。

### 2. 需要策略时：直接写 `litegate.*` 注解

负载均衡、超时、重试、中间件、IDS 等没有简写，直接写服务标签(与 Consul / Docker 完全相同)：

```yaml
  annotations:
    litegate.http.routers.billing.match.hosts: "billing.example.com"
    litegate.http.routers.billing.match.path_prefix: "/api/billing"
    litegate.http.services.billing.loadbalancer.strategy: "p2c"
    litegate.http.services.billing.timeout: "30s"
```

简写注解属于快捷模式，不能与命名资源注解混用。

### 3. 注解映射表

| 注解 | 对应标签 | 说明 |
| :--- | :--- | :--- |
| `litegate.io/expose`(label) | `litegate.enable=true` | **必填**：设为 `"true"` 才会被发布 |
| `litegate.io/host` 或 `litegate.io/domain` | `litegate.http.host` | 域名 |
| `litegate.io/path` | `litegate.http.path` | 精确路径 |
| `litegate.io/prefix` 或 `litegate.io/path-prefix` | `litegate.http.path_prefix` | 路径前缀 |
| `litegate.io/strip-path` 或 `litegate.io/strip-prefix` | `litegate.http.strip_path` | 只接受 `true` / `false` |
| 任意 `litegate.*` | 原样透传 | 命名资源与实例标签，见[服务标签参考](user/03-configuration/tag-reference.md) |

`litegate.io/lb`、`litegate.io/auth` 已移除，带有它们的 Service 会被拒绝；负载均衡请用 `litegate.http.services.<name>.loadbalancer.strategy`，认证请用中间件。

---

## 五、Kubernetes RBAC 最小权限清单

在 Kubernetes 中部署 LiteGate 时，只需赋予 **`endpointslices`** 和 **`services`** 的只读权限：

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: litegate-sa
  namespace: litegate-system
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: litegate-role
rules:
  # 1. 读取 EndpointSlice 获取健康 Pod IP
  - apiGroups: ["discovery.k8s.io"]
    resources: ["endpointslices"]
    verbs: ["get", "list", "watch"]
  # 2. 读取 Service 获取 Opt-In 元数据与 Annotations
  - apiGroups: [""]
    resources: ["services"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: litegate-role-binding
subjects:
  - kind: ServiceAccount
    name: litegate-sa
    namespace: litegate-system
roleRef:
  kind: ClusterRole
  name: litegate-role
  apiGroup: rbac.authorization.k8s.io
```

---

## 六、生产实践与关键注意事项

### 1. Pod 滚动发布与优雅停机（Zero 502）
* LiteGate 内部对 EndpointSlice 进行了严格的条件过滤：
  ```go
  // 仅保留 ready == true 且 terminating == false 的 Pod
  if !ep.Conditions.Ready || ep.Conditions.Terminating {
      // 自动从负载均衡池剔除
  }
  ```
* 当 Pod 发生滚动升级或扩缩容时，K8s 会将即将销毁的 Pod 标为 `terminating`，LiteGate 会在 **毫秒级内** 将其从活跃池移除，彻底消除发往关闭中 Pod 的 502/504 错误。

### 2. API Server 断线自愈与 Token Projected 轮转
* **410 Gone 自愈**：当长连接 Watch 流因为集群网络抖动或超时断开时，系统会自动复用最新 `resourceVersion` 快速续连；若版本过期（410 Gone），则自动触发全量 Relist 恢复。
* **网络分区降级**：若 API Server 短暂失联，LiteGate 会保持内存中已有的 Pod 实例快照正常转发，并在后台自动退避重试，绝不中断现有业务流量。
* **安全 Token 轮转**：LiteGate 每次 HTTP 请求动态读取内存挂载的 Projected Token，完全支持 Kubernetes 1.21+ 的 ServiceAccount Token 自动轮转机制。

### 3. 生产防抖与性能保护
* **事件合并**：在高频扩缩容（如一次性拉起 100 个 Pod）场景下，LiteGate 内置 `100ms Debounce` 防抖合并器，杜绝路由高频重载风暴。
* **命名空间隔离**：大型集群（>5000 Pods）建议在配置中指定目标 `namespace`，避免监听无相关的系统命名空间。

---

## 七、当前边界与暂不支持的特性（Limitations）

为保持 **单二进制、轻量、极简高性能** 的核心产品定位，当前版本具有以下明确的范围边界：

| 特性 | 当前状态 | 说明与替代方案 |
| :--- | :--- | :--- |
| **Ingress CRD (networking.k8s.io/v1)** | 暂不支持 | 无需定义复杂的 Ingress 资源，直接通过 Service Annotations 声明 |
| **Gateway API (HTTPRoute / GatewayClass)** | 暂不支持 | 属于重量级 Controller 规范，当前采用轻量级原生 Service 模型 |
| **API Server `.status` 回写** | 不支持 | LiteGate 不会向 K8s 写入 `LoadBalancer.Ingress.IP`，状态由 Dashboard 呈现 |
| **动态多集群切换** | 单实例单集群 | 每个 LiteGate 进程连接一个 K8s API Server；跨集群可通过多部署或 Litemesh 级联 |
| **Headless Service StatefulSet 序号路由** | 仅按池负载均衡 | 将 StatefulSet 的 Pod 作为通用对等端点进行 P2C 负载均衡 |

---

## 八、总结

通过这套方案，LiteGate 既保留了**单二进制、零重型 SDK、内存极省**的纯粹性，又为 Kubernetes 提供了**声明式自动化路由发布**与**直连 Pod 的企业级 7 层流量治理能力**。后端业务团队只需打上简单的 Annotations，即可享受现代云原生网关的高性能体验！
