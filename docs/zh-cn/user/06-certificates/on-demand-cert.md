# On-Demand TLS (按需签发证书)

On-Demand TLS 是 LiteGate 的进阶证书特性。与标准的 Auto-Cert 不同，按需签发不会在启动时申请证书，而是在 **第一次握手 (First Handshake)** 时实时申请。

---

## 1. 核心场景

- **SaaS 平台**: 允许您的客户将他们的域名（如 `customer.com`）解析到您的网关，而您事先并不知道这些域名。
- **海量域名**: 您管理着成千上万个不常用的二级域名，在启动时全部申请会导致频率限制或内存压力。

---

## 2. 启用配置

在 `config.yaml` 中配置允许按需签发的策略（关键：必须有策略，以防滥用）：

```yaml
auto_cert:
  enabled: true
  on_demand:
    enabled: true
    # 策略：通过 HTTPS API 询问是否准许为该域名签发（默认强制 HTTPS 校验）
    ask: "https://your-backend:8443/check-domain"
    ask_ca: "/etc/litegate/certs/ask-ca.pem" # 可选：指定自定义根 CA 路径锁定 Ask 服务证书
    allow_insecure_ask: false                # 可选：是否豁免强制 HTTPS 校验（设为 true 允许 HTTP）
```

### 站点配置
```yaml
domain: "*"  # 配合泛解析使用
force_https: true
```

---

## 3. 工作流程

1.  **首位访客**: 访问 `https://random-user.com` ➡️ 指向 LiteGate。
2.  **握手阶段**: 握手被拦截。网关请求 `ask` 端点：“域名 `random-user.com` 是我们的客户吗？”
3.  **鉴准**: 后端返回 `200 OK`。
4.  **实时申请**: 网关触发 ACME HTTP-01 验证任务，并在 3-10 秒内获得证书。
5.  **握手成功**: 证书缓存在内存并持久化，后续访问将直接使用该证书。

---

## 4. 安全防护与通道加固

由于申请证书是耗时且消耗资源的操作，网关提供了以下防护与加固机制：
- **最大并发申请数**: 限制同时进行的 ACME 任务数量。
- **白名单校验**: 严格执行 `ask` 端点校验，防止被恶意消耗 Let's Encrypt 额度。
- **双轨 TLS 固定验证 (Ask CA)**：为了防止黑客在内网或传输中劫持/伪造网关的 `ask` 校验结果，网关默认强制要求 `ask` 端点使用 HTTPS 协议。您可以通过 `ask_ca` 配置文件路径指定根 CA 证书建立独立 TLS 信任，实行 Pinning 校验；在开发或测试环境，可以通过设置 `allow_insecure_ask: true` 降级放行 HTTP。

---

## 5. 本地白名单策略 (Allowed Patterns)

除了通过动态接口 (`ask` 端点) 或 KV 存储鉴权外，网关还支持配置本地的域名匹配白名单 `allowed_patterns`。

其安全模型与工作模式如下：
- **双轨过滤 (Pre-Filter)**：如果配置了 `allowed_patterns` 并且也配置了 `ask`（或 `kv_prefix`），网关在收到请求时，会先匹配模式。只有在模式匹配成功后，才会去请求后端接口校验。这有助于减少对后端接口的无谓请求，减轻后端压力并拦截非法探测。
- **直接白名单授权**：如果仅配置了 `allowed_patterns`，而将 `ask` 和 `kv_prefix` 保持为空，则只要域名匹配白名单中定义的模式，网关便会**直接**授权该域名并进行证书申请。这适用于域名范围明确、无需搭建后端动态校验服务的轻量级防滥用场景。

> [!IMPORTANT]
> 无论是使用 `ask` 接口、`kv_prefix` 还是 `allowed_patterns`，请务必保证至少启用其中一种策略。在没有任何安全过滤策略的情况下，**请勿**开启泛域名 (`domain: "*"`) 的 On-Demand 证书申请，否则这会导致严重的证书资源滥用风险。

示例配置：
```yaml
auto_cert:
  enabled: true
  on_demand:
    enabled: true
    # 仅使用本地白名单模式进行安全过滤，无需搭建外部 ask 服务
    allowed_patterns:
      - "*.user.example.com"
      - "custom.domain.org"
```

---

## 延伸阅读
- [配置 404 响应页面](../../user/04-actions/respond.md)
- [自动化证书全解](./auto-cert.md)
