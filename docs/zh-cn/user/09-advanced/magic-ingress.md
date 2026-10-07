# Magic Ingress (零配置服务接入)

**Magic Ingress** 是 LiteGate 在 Litemesh 模式下的旗舰功能。它实现了“服务定义路由”的自动化运维，让开发者无需编写任何 Gateway 配置文件。

---

## 1. 设计初衷

传统的 Ingress 流程往往非常繁琐：
- 部署 Pod ➡️ 配置 Service ➡️ 编写 Ingress YAML ➡️ 等待证书签发 ➡️ 配置 DNS。

**使用 Magic Ingress 后，您只需要一步**：
- 给您的服务打上一个域名标签，剩下的所有步骤（路由配置、证书申请、DNS 更新）全部由 LiteGate 自动完成。

---

## 2. 启用配置

Magic Ingress 是自动生效的,没有单独的开关。你只需在 `config.yaml` 里连上一个发现源(Litemesh、Consul 或 Docker):

```yaml
litemesh:
  enabled: true
```

发现源接通后,任何用下面的魔术标签注册的服务,无需为它单独配路由就能通过网关访问。

---

## 3. 使用魔术标签 (Magic Tags)

在您的微服务（SDK 注册或 Sidecar 注册）中添加以下元数据：

| 标签 Key | 示例值 | 说明 |
| :--- | :--- | :--- |
| `litegate.http.host/path/path_prefix/strip_path` | `myapi.com`、`/api`、`true` | 单 Router 快捷模式，目标是当前注册服务。 |
| `litegate.http.routers.<name>.*` | Router 属性 | 需要多路由、IDS 或显式 Middleware 时使用完整资源模型。 |
| `litegate.http.services.<name>.*` | Service 属性 | 定义发现、Selector 和负载均衡。 |

> 完整标签清单见[服务标签参考](../03-configuration/tag-reference.md)。

### 示例 (Go SDK):
```go
service := &sdk.ServiceInstance{
    Name: "user-service",
    Tags: []string{"litegate.http.host=user.example.com"},
}
client.Register(service)
```

快捷模式不能与 vNext 资源标签混用。简单 `/v1` 前缀可添加 `litegate.http.path_prefix=/v1`；需要多个 Router、IDS 或其他高级属性时再使用完整资源模型。

---

## 4. 自动化流水线

1.  **自动路由**: LiteGate 发现标签后立即在内存生成路由，此时 `user.example.com` 已可访问。
2.  **自动证书**: 后台自动异步触发 Let's Encrypt 证书申请流程。
3.  **自动 DNS (DDNS)**: 如果配置了 DNS 更新器，会自动将 `user.example.com` 指向当前网关。

---

## 延伸阅读
- [Magic Ingress 深度架构解析](../../magic_ingress_architecture_zh.md)
- [配置 Litemesh 集成](../07-discovery/litemesh.md)
- [自动化证书全解](../06-certificates/auto-cert.md)
