<!-- GENERATED FILE — DO NOT EDIT.
     Source: internal/configdocs/docs/zh/on-demand-tls.md (package internal/configdocs)
     Regenerate: go generate ./internal/configdocs/...
     Edit the source instead; a drift test fails if this copy is edited directly. -->

# On-Demand TLS (SaaS 按需证书申请)

LiteGate 支持类似 Caddy 的 **On-Demand TLS** 功能，允许在 TLS 握手阶段动态申请证书。这对于 SaaS 平台至关重要，因为它可以让你的客户将自定义域名解析到你的平台，而无需你手动为每个域名配置证书或重启服务。

## 1. 核心工作原理

当 LiteGate 收到一个 TLS 握手请求，但本地（或分布式存储中）没有找到该域名的证书时，会触发以下流程：

1.  **鉴权 (Authorization)**: LiteGate 会询问你的业务后端（通过 `ask` 接口）或检查 KV 存储，确认该域名是否允许申请证书。
2.  **绑定 (Binding)**: 如果鉴权通过，LiteGate 会将该域名动态绑定到一个指定的“模板站点”（SaaS Template Site）。
3.  **申请 (ACME)**: LiteGate 自动通过 ACME 协议（默认 HTTP-01 挑战）向 Let's Encrypt 等机构申请证书。
4.  **缓存与同步**: 申请成功的证书会存入分布式存储（如 Litemesh/Consul）并缓存，以便后续请求直接使用。

## 2. 配置说明

在 `config.yaml` 中配置 `auto_cert.on_demand`：

```yaml
auto_cert:
  enabled: true
  email: "admin@example.com"
  certs_dir: "./certs"
  on_demand:
    enabled: true
    # 方式 A: 外部鉴权接口 (推荐)
    ask: "https://api.mysaas.com/v1/verify-domain"
    # 方式 B: Litemesh KV 鉴权
    kv_prefix: "saas/domains/"
    # 默认的 SaaS 模板站点域名 (即 sites 目录下的 domain 配置)
    saas_template_site: "template.mysaas.com"
```

### 参数详解
- **`ask`**: LiteGate 会向此 URL 发送 GET 请求，带上 `domain` 参数。例如：`https://api.mysaas.com/v1/verify-domain?domain=customer1.com`。
- **`saas_template_site`**: 这是你在 LiteGate 中预先定义好的一个站点的 `domain`（即 Loader 索引站点的 key）。所有通过验证的动态域名都会复用这个站点的后端配置。

## 3. SaaS 业务对接实现

### 后端 `ask` 接口实现
你的业务后端需要实现一个接口，返回 JSON 格式：

```json
{
  "authorized": true,
  "template": "premium-template.mysaas.com"
}
```

- `authorized`: **必须明确为 `true`** 才会触发申请流程。
- `template` (可选): 如果返回，将覆盖全局配置的 `saas_template_site`。

## 4. 最佳实践与注意事项

1.  **安全性**: 
    - **域名校验**: LiteGate 内置了严格的 SNI 校验和 IDNA 规范化，会自动拒绝 IP 地址或非法字符。
    - **鉴权接口**: 务必启用 `ask` 接口并严格校验。LiteGate 不再支持非 JSON 的 200 OK 回退，确保安全性。
2.  **生命周期**: 
    - **缓存**: 鉴权结果会在内存中短期缓存（默认 10 分钟），到期后会重新询问 `ask` 接口。
    - **续期**: 证书续期时会**重新鉴权**。如果租户已解绑，LiteGate 将停止续期该证书。
3.  **模板站点配置**: 模板站点应配置在 `sites/` 目录下。
    ```yaml
    domain: "template.mysaas.com"
    routes:
      - match:
          path_prefix: "/"
        action:
          type: "proxy"
          upstream: ["127.0.0.1:8080"]
    ```

## 5. 代码逻辑解析 (开发者视角)

LiteGate 的实现逻辑位于 `internal/certmanager/certmanager.go` 中的 `handleOnDemand` 方法：

1.  **校验与规范化**: 在 `internal/cert/manager.go` 中通过 `isValidHostname` 和 IDNA 对 SNI 进行规范化。
2.  **鉴权 (checkAuthorization)**: 使用安全参数编码请求 `ask` 接口，并验证 JSON 响应。
3.  **Loader 注册**: 鉴权通过后立即调用 `RegisterSaaSDomain` 建立映射。
4.  **分布式申请**: 获取分布式锁并执行 ACME 挑战。如果申请失败，会调用 `UnregisterSaaSDomain` 清理映射，防止失效路由。
5.  **SAN 保护**: 续期逻辑会提取现有证书的所有 `DNSNames`，确保多域名证书不会在自动续期时被降级。
