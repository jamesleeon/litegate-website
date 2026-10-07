# LiteGate + Litemesh 集成指南

**LiteGate + Litemesh** 是一套高性能、轻量化且完全云原生化的微服务 API 网关解决方案。通过引入 Litemesh，LiteGate 能够完全摆脱对 Consul 等重型外部服务治理集群的强依赖，提供包括服务发现注册、动态配置热更新和分布式证书集中式存储在内的完整分布式系统控制能力。

---

## 1. 为什么选择 Litemesh？

通过使用 Litemesh 代理替代传统的 Consul 部署，LiteGate 获得了以下核心竞争优势：

- **极简架构**：无需单独维护、部署和监控沉重的 Consul 键值对集群，开箱即用。
- **协议深度优化**：Litemesh Agent 与网关内核在底层网络传输协议上进行了专属生态对齐，获得更出色的极高吞吐性能。
- **一站式统一管控**：将服务注册发现、全量站点配置、SSL 证书集中在单一渠道进行分布式治理。
- **完美的云原生体验**：支持无本地磁盘依赖启动（Stateless / Diskless Mode），支持一键实现云端配置同步。

---

## 2. 网关配置 (`config.yaml`)

要全面开启 Litemesh 驱动并禁用 Consul 发现，请确保您的网关 `config.yaml` 包含了如下配置：

```yaml
# 1. 禁用 Consul 服务发现
consul:
  enabled: false

# 2. 启用 Litemesh 分布式引擎
litemesh:
  enabled: true
  address: "127.0.0.1:8787" # 您的本地 Litemesh Agent 物理通信地址
  roles:
    config_watch: true       # 开启配置热重载 (动态监听 KV)
    cert_storage: true       # 开启分布式证书集中存储 (ACME 证书多节点共享)
    service_register: true   # 开启自注册与 HTTP 节点健康检查
  keys:
    config_prefix: "litegate/config/sites/"
    stream_prefix: "litegate/config/streams/"
    cert_prefix: "litegate/certs/"
```

---

## 3. 工作流：“一键配置云同步” (Sync)

如果您已经在本地编写好了 `config.yaml` 规则，并希望快速无缝迁移至分布式的 Litemesh 集群环境：

**执行命令：**
```powershell
.\litegate.exe -config config.yaml -litemesh-addr 127.0.0.1:8787 -sync-litemesh
```

**底层执行流程：**
1. 网关启动并读取您本地的 `config.yaml` 文件；
2. 自动建立与 Litemesh KV 存储的连接，并将解析后的全量配置文件一键推送到云端（默认 Key：`litegate/config/main`）；
3. **推送成功！** 此时您已经完成了配置入库，可以安全、彻底地删除本地的 `config.yaml` 物理文件，实现节点无盘化。

---

## 4. 工作流：“云原生无盘启动” (Bootstrap)

一旦本地配置成功同步到 Litemesh 之后，LiteGate 在启动时将**不再依赖任何本地物理配置文件**（即进入“无盘/无状态模式”），这非常适合容器化 Docker / Kubernetes 等弹性伸缩环境。

**启动命令：**
```powershell
.\litegate.exe -litemesh-addr 127.0.0.1:8787
```

**数据面拉起流程：**
1. 网关以纯粹的零配置状态连接到指定的 Litemesh Agent 服务端口；
2. 自动拉取 `litegate/config/main` 下的引导参数并初始化应用；
3. **自动注册 (Auto-Discovery)**：自动将当前网关节点的物理 IP 和状态注册至 Litemesh；
4. **统一证书申请 (Auto-Cert)**：网关向证书机构申请或自动续期 SSL 证书，并安全回存至 Litemesh 分布式 KV 中，供整个网关集群共享；
5. **动态热重载 (Live Watch)**：通过 SSE (Server-Sent Events) 长连接机制，毫秒级感知 `litegate/config/sites/` 前缀下的任何细粒度路由变更，并瞬间完成**无任何停机和连接重置的数据面热重载**。

---

## 5. 分布式核心特性

### A. 全自动服务注册与发现
网关在成功拉起后，会自动将自身以指定服务名（默认：`litegate`）注册到服务中心：
- **可视化面板**：可以直接在 Litemesh 仪表盘的“服务管理 (Services)”面板上查阅该节点。
- **主动健康检查**：健康检查探针地址为 `http://<节点-IP>:<端口>/health`。

### B. 分布式证书多节点共享
在开启 `cert_storage: true` 的网关集群环境下：
- **集中存储**：所有由内置 ACME 客户端申请到的 SSL 证书，全部加密存储在 Litemesh 的 `litegate/certs/` 目录下。
- **零成本秒级共享**：当 A 网关节点成功为 `example.com` 申请到证书后，B 节点会通过事件发布订阅瞬间感知，并直接同步调用，**绝不重复**向 Let's Encrypt 触发 ACME 速率上限。
- **高一致性**：彻底解决了分布式集群下各自独立申请证书导致被证书中心频次封禁的经典痛点。

### C. 毫秒级配置动态发布 (Hot Reload)
在开启 `config_watch: true` 时：
- 运维人员直接在 Litemesh 控制台上，于前缀 `litegate/config/sites/` 下新增或修改路由标签 KV；
- 网关采用极其轻量的高能 SSE（服务器发送事件）机制建立通信管道，网关在几毫秒内接收并使变更在内存中生效，**在保持当前长连接不断开的状态下瞬间完成平滑切换**。

---

**总结**：LiteGate 与 Litemesh 的完美结合，能够帮助您以最低的系统运维成本，快速构建一个完全无盘化、具备极致弹性收缩、证书自愈与动态路由发布的生产级网关集群。
