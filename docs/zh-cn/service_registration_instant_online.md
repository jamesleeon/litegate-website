# 服务注册即上线：完整自动化流程验证

## 🎯 核心逻辑

LiteGate 生态系统的核心价值在于：微服务只需“打标签注册”，即可完成从域名解析到 HTTPS 证书申请的全链路闭环。

让我们验证这个完整的自动化流程：

```
payment 微服务注册 (携带 litegate.http.host 标签)
    ↓
Litemesh 记录服务并持久化
    ↓
LiteGate 通过 SSE (Server-Sent Events) 准实时感知
    ↓
LiteGate 内存中动态生成 Site 配置
    ↓
DNS Update 向内网 CamoDNS 注册 payment.company.com 指向 LiteGate IP
    ↓
DDNS 向外网 DNS (如阿里云) 注册 payment.company.com 指向公网 IP
    ↓
Auto-Cert 触发 ACME 流程申请证书
    ↓
✅ 内网访问: https://payment.company.com (秒级生效)
✅ 外网访问: https://payment.company.com (分钟级生效，受 DNS 缓存影响)
```

---

## 📋 流程分解

### 1. 微服务注册到 Litemesh

**服务启动代码示例**:

```go
// 注册服务
service := &sdk.ServiceInstance{
    Name:     "payment",
    Addr:     "192.168.1.200",
    Port:     8080,
    Protocol: "http",
    Tags:     []string{
        "litegate.http.host=payment.company.com",  // 🔥 魔法标签：触发自动网关配置
    },
    Check: &sdk.Check{
        Type:     "http",
        Target:   "http://192.168.1.200:8080/health",
        Interval: "10s",
    },
}
client.Register(service)
```

### 2. Litemesh 事件广播
- 收到注册请求，存入 KV。
- 通过 Gossip 协议同步集群状态。
- 通过 SSE 通道向所有连接的网关节点推送 `SERVICE_ADDED` 事件。

### 3. LiteGate 动态感知与 Site 生成
LiteGate 监听到服务变化后，`CatalogLoader` 会扫描带有 `litegate.http.host` 标签的服务。
- **动态生成**: 在内存中直接构建一个 `Site` 对象，无需修改磁盘上的 `yaml` 文件。
- **即时生效**: 路由引擎更新，此时 `http://payment.company.com` 已可访问。

### 4. 内网 DNS (LiteDNS) 自动同步
LiteGate 调用 `internal/certmanager/dns_update.go` 中的逻辑：
- 将新域名和网关内网 IP 写入 LiteMesh KV（`litedns/v1/records/{domain}/{node_id}`），LiteDNS 监听后立即生效。
- **结果**: 内网机器执行 `dig @litedns payment.company.com` 即可得到网关内网 IP。

### 5. 外网 DDNS 与 ACME 证书
- **DDNS**: 自动将域名同步至公网 DNS 服务商。
- **ACME**: 证书管理器检测到新域名，启动申请流程。由于上一步 DNS 已就绪，HTTP-01 或 DNS-01 验证将顺利通过。

---

## ⏱️ 预期时间线

| 时间点 | 事件 | 状态 |
| :--- | :--- | :--- |
| **T + 0s** | 服务调用 SDK 完成注册 | 🚀 开始 |
| **T + 0.5s** | LiteGate 完成内存路由构建 | 🌐 内网 HTTP 可访 |
| **T + 1s** | 内网 DNS 解析生效 | 📡 域名就绪 |
| **T + 60s** | 证书申请完成并在集群内广播 | 🔒 HTTPS 全面就绪 |

---

## 🎯 为什么这个架构很“硬”？

1.  **解耦**: 业务开发人员不需要懂网关配置，只需要知道自己的域名。
2.  **高可用**: 如果一个 LiteGate 节点挂了，内网 DNS 会通过心跳自动切换到另一个节点。
3.  **零操作**: 证书、解析、路由全部全自动，真正实现了 **"Architecture as Operations"**。

---

## ⚡ 相关技术细节

- [Litemesh + LiteGate 集成](litemesh_integration.md)
