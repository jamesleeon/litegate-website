# Litemesh 服务发现集成

LiteGate 与 Litemesh 原生集成，提供了比传统 Consul 发现更快的响应速度和更强的身份安全性。

---

## 1. 核心优势

- **推送式更新**: 基于 SSE (Server-Sent Events) 协议，当后端服务上下线时，网关在 100ms 内即可感知。
- **内生安全**: 自动支持 mTLS (双向 TLS) 加密，网关与后端点对点通信受证书保护。
- **多租户隔离**: 支持通过 `sid` (Service ID) 进行精细化的租户流量切分。

---

## 2. 全局配置

在 `config.yaml` 中指定 Litemesh 控制面的地址：

```yaml
litemesh:
  enabled: true
  address: "http://litemesh-agent:8787"  # Litemesh 控制面地址
  mtls: true                             # 开启全链路 mTLS 加密
  token: "your-auth-token"               # 可选：访问令牌
```

---

## 3. 在路由中使用

在站点配置中，将 `upstream_type` 设置为 `litemesh`：

```yaml
domain: api.cloud.com
routes:
  - name: user-service
    match: { path_prefix: "/users" }
    action:
      type: proxy
      upstream_type: litemesh
      service_name: "user-api" # 对应远程服务名
      lb_policy: least_conn    # 推荐使用最少连接策略
```

---

## 4. 故障迁移与高可用

Litemesh 节点间通过 Gossip 协议实现状态同步。网关会同时连接多个 Litemesh 节点（如果配置了多个地址），确保即便某个 Litemesh 节点宕机，发现能力依然可用。

---

## 延伸阅读
- [配置 Consul 发现](./consul.md)
- [理解 mTLS 安全架构](../../tls_mtls_architecture.md)
- [使用 Magic Ingress 零配置上线](../09-advanced/magic-ingress.md)
