# 生产环境部署建议 (Production Best Practices)

LiteGate 的默认配置追求易用性，但在生产环境高并发、高可用场景下，需要进行额外的调优和加固。

---

## 1. 性能优化 (Performance Tuning)

### 系统级内核优化 (Linux)
为了承载数万级并发连接，需要调整操作系统的文件描述符限制：
```bash
# 查看并修改
ulimit -n 65535
```

---

## 2. 高可用架构 (High Availability)

> [!IMPORTANT]
> **关键原则**: 永远不要部署单点网关。

### 推荐方案：双机热备 (Litemesh)
1.  部署 2 台以上 LiteGate 节点。
2.  开启 Litemesh 集成，实现证书和配置的实时同步。
3.  最前端使用运营商级 LB（如阿里云 SLB）或硬件 LB 对多台 LiteGate 进行 80/443 转发。

---

## 3. 安全加固 (Security Hardening)

### 账号保护
必须修改默认的 Dashboard 管理密码，并使用 `ip_restriction` 中间件限制管理端只能通过运维内网访问。

### 协议加固
- 全站强制 HTTPS 跳转。
- 开启 HSTS 策略。
- 禁用 SSL 3.0, TLS 1.0/1.1 等过时、不安全的加密协议。

---

## 4. 监控与备份

- **监控**: 集成 Prometheus 抓取 `/metrics`。
- **备份**: 定期备份 `sites/` 目录以及 `certs/` 目录下的私钥（如果未使用集群 KV 存储）。

---

## 延伸阅读
- [如何开启集群证书共享](../06-certificates/auto-cert.md)
