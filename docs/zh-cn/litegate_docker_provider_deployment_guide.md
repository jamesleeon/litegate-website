# LiteGate Docker Provider 部署与配置官方指南

LiteGate 提供内置的高性能、零侵入式 **Docker 动态服务发现（Docker Provider）** 引擎。通过直接监听 Docker 守护进程（Docker Daemon）的实时事件流（Events Stream），LiteGate 能够秒级感应容器的启动、销毁和健康状态变更，动态调整其内部的反向代理 Upstream 负载均衡环，真正做到**业务上线即路由，业务下线即剥离**。

本指南将深入介绍 Docker Provider 的核心工作机制、网关参数配置、容器标签（Labels）定义规范、主流部署拓扑结构以及生产级最佳实践。

---

## 核心机制与优势

LiteGate 的 Docker 动态发现引擎具有以下核心设计优势：

1. **秒级感知，零延迟代理**：基于 Docker Socket 建立的事件管道，无需轮询。容器触发 `start` / `die` 事件时，路由在毫秒级自动同步。
2. **原生健康检查联动**：原生支持对接 Docker Container 自身的 HealthCheck。当容器健康检查状态变更为 `unhealthy` 时，LiteGate 会瞬时将该实例剔除出 Upstream 环；在状态恢复为 `healthy` 时自动恢复路由，保障服务高可用。
3. **防抖动同步（Debounced Swarm Sync）**：在 Docker Swarm 滚动升级或大规模服务扩缩容时，大量 Task 实例会在极短时间内频发启停。LiteGate 内建 **200ms 防抖同步器**，在事件洪峰平息后执行单次合并同步，避免高频重建路由环引发的内存抖动与性能开销。
4. **智能端口与网络识别**：支持从暴露端口（Exposed Ports）或端口发布映射（Port Bindings）中自动、智能地推断业务端口，并自动规避 Swarm Ingress 网络以防止流量环路。

---

## LiteGate 侧网关配置

要启用 Docker 服务发现，您需要在 LiteGate 的主配置文件（如 `config.yaml`）中，向 `service_discovery.catalogs` 配置列表中添加一个 `provider` 为 `"docker"` 的 Catalog 配置项：

```yaml
# HTTP 基础监听
http:
  port: 80
  https_port: 443

# 开启动态服务发现 Catalog 列表
service_discovery:
  catalogs:
    - enabled: true
      provider: "docker"
      socket_path: "/var/run/docker.sock"  # Unix 路径、tcp:// / https:// 地址；省略则读取 DOCKER_HOST
      network_mode: "internal"             # "internal" (直连容器) 或 "external" (宿主机映射)
      swarm_mode: false                    # 是否开启 Docker Swarm 模式支持
      swarm_auto_detect: false             # 可选；仅连接到 Manager 时自动启用 Swarm
      swarm_network: "litegate-net"        # 单机或 Swarm 模式下首选共享网络
      swarm_reconcile_interval: 5s          # Swarm Task 全量校准间隔
      namespace: "default"                 # 命名空间，多 Catalog 并存时用于路由安全隔离
```

### 配置参数解析

| YAML 配置字段 | 类型 | 默认值 | 描述说明 |
| :--- | :--- | :--- | :--- |
| `enabled` | `bool` | `false` | 是否启用该 Docker 发现 Catalog 实例。 |
| `provider` | `string` | - | 必须配置为 `"docker"` 以激活 Docker 发现适配器。 |
| `socket_path` | `string` | `"/var/run/docker.sock"` | Unix 套接字路径，或 `tcp://`、`http://`、`https://` Docker API 地址。留空时读取 `DOCKER_HOST`；支持标准 `DOCKER_TLS_VERIFY` 和 `DOCKER_CERT_PATH`（`ca.pem`、`cert.pem`、`key.pem`）。 |
| `network_mode` | `string` | `"internal"` | **通信路由模式**：<br>• `"internal"`：直连容器内部虚拟 IP 和端口。<br>• `"external"`：代理向宿主机暴露映射的公开 IP 和端口。 |
| `swarm_mode` | `bool` | `false` | 是否开启 Docker Swarm 集群发现模式。开启后，网关会通过 Swarm Service 和 Task API 发现跨节点容器，并支持事件防抖同步。 |
| `swarm_auto_detect` | `bool` | `false` | 是否自动识别 Swarm。仅当当前 Docker Daemon 是 Manager 且能提供集群 API 时才启用；Worker 不会误切换。 |
| `swarm_network`| `string` | - | 单机或 Swarm 模式下的首选共享网络；Swarm stack 添加的名称前缀会自动匹配。 |
| `swarm_reconcile_interval` | `duration` | `5s` | Swarm Task 权威全量校准的轮询间隔。 |
| `namespace` | `string` | `"default"` | **（多租户隔离可选）** 命名空间标识。多 Catalog 混合部署时，只发现和代理匹配命名空间的容器。 |

---

## 容器侧标签（Labels）定义规范

LiteGate 依靠非侵入式的 **Docker 容器标签（Labels）** 来解析路由行为。当您的业务容器被打上 `litegate.*` 相关的标签后，网关便会自动捕获并为该容器分配反向代理分流规则。

### 基础标签列表

| 容器 Label 标签 | 示例值 | 强制性 | 描述说明 |
| :--- | :--- | :--- | :--- |
| `litegate.enable` | `"true"` | 推荐 | 显式加入 LiteGate 服务发现。设为 `false` 时始终禁用；未设置时，其他 `litegate.` 标签仍会触发发现。 |
| `litegate.http.host` 或 `litegate.http.routers.<name>.*` | Host / Router 属性 | 推荐 | 快捷模式，或命名 Router 的 Host/路径规则；默认挂到 web 与 websecure。 |
| `litegate.http.services.<name>.discovery.name` | `"mqserver"` | 可选 | 声明 Docker 发现服务名；未设置时使用 Compose `<project>-<service>` 或容器名。 |
| `litegate.http.services.<name>.loadbalancer.server.port` | `"8080"` | 可选 | 声明容器内端口；单一暴露/映射端口可自动推断。 |

### 高级网络与路由标签

| 容器 Label 标签 | 示例值 | 描述说明 |
| :--- | :--- | :--- |
| `litegate.docker.usehostport` | `"true"` | Docker Provider 提示：强制使用宿主机映射端口。 |
| `litegate.docker.network` | `"custom-net"` | **首选通信网卡名称**。如果容器同时挂载了多个 Docker 虚拟网络，可用此标签显式指定 LiteGate 接入哪一块网卡 IP，避免因默认选取规则产生路由不通。 |

> [!TIP]
> **实例身份**：`version`、`sid`、`zone` 等应作为 Endpoint Metadata，由 Service 的 `discovery.selector.*` 或 IDS 返回的 selector 匹配。

---

## 典型部署拓扑架构

### 拓扑一：单机全容器化直连模式 (Flat Container Network)

**适用场景**：LiteGate 与您的微服务全部以容器方式跑在同一台 Docker 宿主机上。这是最轻量、最推荐的方案，流量直接在 Docker 虚拟网络内部流转，无宿主机端口映射开销，性能卓越。

```
                    ┌─────────────────────────┐
                    │      Docker Network     │
                    │     (litegate-net)      │
                    └────────────┬────────────┘
                                 │
         ┌───────────────────────┴───────────────────────┐
         ▼                                               ▼
┌──────────────────┐  Container IP 直连通信     ┌──────────────────┐
│  litegate-edge   ├──────────────────────────►│   saas-mqserver  │
│  (Container IP)  │                           │   (172.25.0.3)   │
└──────────────────┘                           └──────────────────┘
```

#### 部署步骤与文件

1. **创建公共桥接网络**：
   ```bash
   docker network create litegate-net
   ```

2. **编写 LiteGate 网关配置 `config.yaml`**：
   ```yaml
   http:
     port: 80
     https_port: 443

   service_discovery:
     catalogs:
       - enabled: true
         provider: "docker"
         socket_path: "/var/run/docker.sock"  # 挂载后在容器内读取
         network_mode: "internal"             # 直连模式
   ```

3. **使用 `docker-compose.yaml` 启动网关**：
   ```yaml
   version: '3.8'

   services:
     litegate:
       image: jamesleeon/litegate:latest
       container_name: litegate
       restart: always
       volumes:
         - ./config.yaml:/app/config.yaml
         - /var/run/docker.sock:/var/run/docker.sock  # 挂载宿主机 Docker 套接字
       group_add:
         - "${DOCKER_GID}"  # export DOCKER_GID=$(stat -c '%g' /var/run/docker.sock)
       ports:
         - "80:80"
         - "443:443"
       networks:
         - litegate-net

   networks:
     litegate-net:
       external: true
   ```
   执行命令启动网关：
   ```bash
   export DOCKER_GID=$(stat -c '%g' /var/run/docker.sock)
   docker compose up -d
   ```

4. **运行业务容器**（带上服务发现标签）：
   ```bash
   docker run -d \
     --name business-api \
     --network litegate-net \
     -l litegate.enable=true \
     -l litegate.http.routers.business.match.hosts=api.example.com \
     -l litegate.http.services.business.discovery.name=business-service \
     -l litegate.http.services.business.loadbalancer.server.port=8080 \
     my-business-app:latest
   ```

---

### 拓扑二：独立网关进程外部代理模式 (External Host Mode)

**适用场景**：LiteGate 直接以二进制程序跑在宿主机（虚拟机/裸金属）上，而业务服务均跑在 Docker 容器内部。网关与容器通过宿主机映射出来的端口（Host Port）进行反代理通信。

```
┌────────────────────────────────────────────────────────┐
│                      Host OS                           │
│                                                        │
│   ┌─────────────────┐             ┌─────────────────┐  │
│   │    LiteGate     │ 反代转发流量  │  saas-mqserver  │  │
│   │  (Host Binary)  ├────────────►│   (Container)   │  │
│   │   (Port 80)     │ 宿主机:8080  │   (Port 8080)   │  │
│   └─────────────────┘             └────────┬────────┘  │
└────────────────────────────────────────────┼───────────┘
                                             ▼
                                     通过 -p 8080:8080 暴露
```

#### 部署步骤与文件

1. **编写 LiteGate 网关配置 `config.yaml`**：
   ```yaml
   http:
     port: 80
     https_port: 443

   service_discovery:
     catalogs:
       - enabled: true
         provider: "docker"
         socket_path: "/var/run/docker.sock"  # 本地套接字
         network_mode: "external"             # 外部映射模式
   ```

2. **启动 LiteGate 二进制程序**：
   ```bash
   ./litegate -c ./config.yaml
   ```

3. **运行并向宿主机暴露端口的业务容器**：
   ```bash
   docker run -d \
     --name business-api \
     -p 8080:8080 \
     -l litegate.enable=true \
     -l litegate.http.routers.business.match.hosts=api.example.com \
     -l litegate.http.services.business.discovery.name=business-service \
     -l litegate.http.services.business.loadbalancer.server.port=8080 \
     my-business-app:latest
   ```
   网关监听到容器启动后，将自动查询其绑定到宿主机的端口（例如 `127.0.0.1:8080`），并加入反向代理。

> [!NOTE]
> **关于 `LITEGATE_DOCKER_HOST` 宿主机 IP 自动回退机制**：
> 当 LiteGate 本身运行在容器中，但是配置了 `network_mode: external` 代理外部映射端口时，因为容器内直接提取 Port Bindings 的 HostIP 往往为 `0.0.0.0` 或 `::`，网关若直接代理该 IP 将导致访问失败。
> 为此，LiteGate 提供了业界领先的**回退解析机制**：
> 1. 首先尝试读取系统环境变量 `LITEGATE_DOCKER_HOST` 或 `DOCKER_HOST_IP` 作为宿主机通信 IP。
> 2. 若无配置，且检测到运行在容器内，将自动解析 `/proc/net/route` 提取默认网关的 IP 作为宿主机真实 IP 进行接入。

---

### 拓扑三：Docker Swarm 生产高可用扁平化网络

**适用场景**：企业级生产环境，LiteGate 和微服务全部以副本集（Replica Sets）的形式在 Docker Swarm 滚动编排。网关通过 Swarm Overlay 扁平虚拟网络，直接负载均衡给跨节点运行的各个物理 Task 实例。

```
                  ┌─────────────────────────────────┐
                  │       Swarm Overlay Network     │
                  │          (litegate-net)         │
                  └────────────────┬────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  litegate.1.task ├─────►│  mqserver.1.task ├─────►│  mqserver.2.task ├─────► ...
│    (Overlay IP)  │      │   (10.0.15.5)    │      │   (10.0.15.12)   │
└──────────────────┘      └──────────────────┘      └──────────────────┘
```

#### 部署步骤与文件

1. **在 Swarm Manager 节点创建可挂载的 Overlay 共享网络**：
   ```bash
   docker network create --driver overlay --attachable litegate-net
   ```

2. **使用仓库中维护的 `deploy/swarm/stack.yml` 示例。** 它会在带标签的边缘节点上以 global 模式运行 LiteGate、用 host 模式发布端口，并通过 Manager 上的只读 Socket Proxy 访问 Docker API。LiteGate 和 proxy 单独共享内部 `docker-api` overlay；业务容器只加入 `litegate-net`，无法访问 Docker API。Docker catalog 的 `socket_path` 应留空，使 `DOCKER_HOST=tcp://docker-socket-proxy:2375` 生效。

   Proxy 只开放当前 Swarm 配置需要的 `EVENTS`、`INFO`、`SERVICES` 和 `TASKS`，关闭 `CONTAINERS`、`NETWORKS` 以及所有 POST 请求。只读**不等于不含敏感数据**：服务和任务响应仍可能暴露集群拓扑、服务配置乃至环境变量，因此不要让不可信业务加入 `docker-api`。

3. **使用 Stack 命令一键部署整个集群**：
   ```bash
   docker stack deploy -c deploy/swarm/stack.yml saas-app
   ```

> [!IMPORTANT]
> **Swarm 核心安全规避：屏蔽 Ingress 网络**：
> Swarm Task 实例启动时，为了将端口发布出去，会被强制挂载一个名为 `ingress` 的全局路由网卡，此外还会挂载我们自定义的 `litegate-net` Overlay 网卡。
> 如果网关不加区分地提取 IP，一旦提取到 `ingress` 网卡分配的 `10.255.x.x` 地址，流量在跨节点通信时将因为 Swarm 路由环路直接陷入死锁或打到错误物理机上。
> LiteGate 根据 Docker API 的 `Network.Spec.Ingress` 字段识别并屏蔽 ingress 网络（兼容旧 API 时仅精确匹配名称 `ingress`），再从用户 Overlay 网络中选择 Task IP；不会误排除 `my-ingress-net` 这类普通网络。
> Swarm 模式只读取 `deploy.labels`，不会读取容器级 `labels`。多个 LiteGate 实例申请 ACME 证书时，应在 Consul 或 Litemesh 配置中启用 `roles.cert_storage: true`，把证书状态存入共享控制面；它是布尔角色开关，不是文件路径。

---

## 故障排查指南

### 1. 日志中出现 Permission Denied 无法读取套接字
**原因**：宿主机的 `/var/run/docker.sock` 默认只允许 `root` 用户或 `docker` 用户组成员读写，LiteGate 容器在普通用户下运行时权限不足。
**解决方案**：优先把 socket 的组 GID 以附加组传给容器：
```bash
export DOCKER_GID=$(stat -c '%g' /var/run/docker.sock)
docker compose up -d
```
生产环境更推荐把受限 Docker Socket Proxy 放在只有 LiteGate 能加入的专用网络。只读 Docker 元数据仍可能包含敏感信息，不能暴露给业务容器。不要把 socket 改成全局可读写的 `0666`；直接挂载 Docker socket 本身等同于授予宿主机级高权限。

### 2. 容器启动了但是网关日志没有任何反应
**检查步骤**：
1. 确认宿主机套接字已挂载给网关容器，且宿主机与网关容器内的 `/var/run/docker.sock` 软连接和实体文件是否对应一致。
2. 确认业务容器已经成功打上了以 `litegate.` 开头的 Labels 标签。可以通过 `docker inspect <container-id>` 确认。
3. Docker catalog 的 `namespace` 用于隔离发现请求，容器本身没有 namespace 标签。配置多个 Docker catalog 时，应为 catalog 使用不同 namespace，并让消费方请求对应 namespace。

### 3. 多网卡容器下出现路由访问不通或偶发超时
**原因**：业务容器同时挂载多个网络，但并非每个网络都与 LiteGate 互通。
**解决方案**：
* 在您的业务容器的 Labels 中，显式添加网卡优选指令：
  ```bash
  -l litegate.docker.network=litegate-net
  ```
  网关检测到后会优先采用 `litegate-net`。也可以在 catalog 设置 `swarm_network`；虽然保留了旧名称，它同样适用于单机 Docker。LiteGate 自身运行在容器中时会自动优先双方共享的网络，最终兜底会按网络名排序，保证结果稳定。

未设置 Service 的 `discovery.name` 时，Compose 容器会按 `<project>-<service>` 聚合；缺少 Compose 标签时回退到容器名。

镜像健康检查默认读取本地 `web` entrypoint。网关从 Consul 或 Litemesh 获取远程配置时，应把 `LITEGATE_HEALTH_ADDR` 设置为实际监听地址（例如 `127.0.0.1:8080`）。`litegate healthcheck --addr ...` 的优先级高于该环境变量，显式 `--config` 的优先级高于 `LITEGATE_CONFIG`。
