# Consul 服务发现集成

LiteGate 支持将 Consul 作为服务资产的来源。网关会定期同步 Consul Catalog 里的服务实例，并根据健康检查状态自动维护负载均衡池。

---

## 1. 全局开启 Consul 支持

在 `config.yaml` 中配置 Consul 代理地址（通常是内网地址）：

```yaml
service_discovery:
  catalogs:
    - enabled: true
      provider: "consul"
      url: "http://127.0.0.1:8500" # 建议指向本机的 Consul Agent
      token: "ACL-TOKEN-HERE"      # 如果开启了 ACL
```

---

## 2. 在站点中使用 Consul

一旦全局配置完成，您就可以在任意 Route 中引用 Consul 服务：

```yaml
domain: api.example.com
routes:
  - name: user-service-route
    match: { path_prefix: "/users" }
    action:
      type: proxy
      upstream_type: consul
      service_name: "user-api" # 对应 Consul 中的 Service Name
      lb_policy: round_robin
```

---

## 3. 健康检查与故障摘除

LiteGate 仅同步在 Consul 中状态为 `Passing` 的实例。
- **自动同步**: 网关每隔 5 秒（可配置）增量同步一次实例列表。
- **故障摘除**: 一旦某个实例在 Consul 中变为 `Critical`，网关会在下一个同步周期将其从负载均衡中移除。

---

## 4. 与 Litemesh 的区别

| 特性 | Consul | Litemesh |
| :--- | :--- | :--- |
| **同步机制** | 定期轮询 (Polling) | 事件推送 (SSE Push) |
| **同步时效** | 秒级 (1-5s) | 毫秒级 (< 500ms) |
| **多租户支持** | 通过命名空间隔离 | 通过 SID/Env 隔离 |
| **适用范围** | 传统微服务架构 | 云原生服务网格 |

---

## 延伸阅读
- [配置 Litemesh 分布式发现](./litemesh.md)
- [理解负载均衡策略](../02-concepts/actions.md#负载均衡协议)
