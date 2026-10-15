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
    # 默认的 SaaS 模板站点域名 (即 sites 目录下的 site 配置)
    saas_template_site: "template.mysaas.com"
```

### 参数详解
- **`ask`**: LiteGate 会向此 URL 发送 GET 请求，带上 `domain` 参数。例如：`https://api.mysaas.com/v1/verify-domain?domain=customer1.com`。
- **`saas_template_site`**: 这是你在 LiteGate 中预先定义好的一个站点的 `site`（即 Loader 索引站点的 key）。所有通过验证的动态域名都会复用这个站点的后端配置。

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

### 请求与响应契约

LiteGate 请求 `GET {ask}?domain=shop.customer.com`；已有查询参数会保留，domain 参数会设置为当前申请证书的域名。没有 JSON 请求体，也不会自动附加业务鉴权头。请求超时为 5 秒。

允许必须返回 **HTTP 200** 和 JSON 对象，例如 `{"authorized": true}`；也可附加 `template` 指定已存在的模板站点域名。省略或留空 template 时使用 saas_template_site。建议返回 Content-Type: application/json。拒绝可返回 HTTP 403 和 `{"authorized": false}`，或 HTTP 200 和同一 JSON。缺少 authorized、false、空响应、非法 JSON、非 200 状态、网络错误和超时均拒绝。

ask 默认要求 HTTPS 并校验证书。内部 HTTP 服务必须显式设置 allow_insecure_ask: true；HTTPS 使用私有 CA 时配置 ask_ca。allow_insecure_ask 不会关闭 HTTPS 证书校验。ask 本身必须能在申请客户证书之前访问，避免把它放在依赖本次证书申请的域名上。

### CNAME 客户域名

例如客户设置 `shop.customer.com CNAME edge.mysaas.com`，并访问 `https://shop.customer.com`：TLS SNI 和 ask 的 domain 都是 shop.customer.com，申请的证书也覆盖这个客户域名。CNAME 目标的证书不会自动覆盖客户域名。ask 应查询已验证、已启用的租户域名绑定；不要仅因 CNAME 指向平台就允许任意域名申请。

CNAME 链最终需要解析到能接收验证请求的网关。使用 HTTP-01 时，客户域名的公网 80 端口和 `/.well-known/acme-challenge/` 必须能到达挑战处理器；代理/CDN 也需要放行这条路径。DNS-01 的 `_acme-challenge` CNAME 委派是另一种机制，普通业务域名的 CNAME 并不自动配置 DNS-01。参见 [Let's Encrypt 验证方式](https://letsencrypt.org/zh-cn/docs/challenge-types/)。

### 最小 Go ask 服务

```go
package main

import (
    "encoding/json"
    "log"
    "net/http"
    "strings"
)

func main() {
    // Replace with verified, active tenant-domain bindings from your database.
    bindings := map[string]string{
        "shop.customer.com": "template.mysaas.com",
    }
    http.HandleFunc("/v1/verify-domain", func(w http.ResponseWriter, r *http.Request) {
        if r.Method != http.MethodGet {
            w.Header().Set("Allow", "GET")
            http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
            return
        }
        domain := strings.TrimSuffix(strings.ToLower(strings.TrimSpace(r.URL.Query().Get("domain"))), ".")
        template, allowed := bindings[domain]
        w.Header().Set("Content-Type", "application/json")
        if !allowed {
            w.WriteHeader(http.StatusForbidden)
        }
        _ = json.NewEncoder(w).Encode(struct {
            Authorized bool   `json:"authorized"`
            Template   string `json:"template,omitempty"`
        }{allowed, template})
    })
    log.Fatal(http.ListenAndServe("127.0.0.1:9080", nil))
}
```

该示例只监听本机 HTTP。生产环境可在前面加 HTTPS 反向代理；同机内网试用可配置 ask: http://127.0.0.1:9080/v1/verify-domain 并设置 allow_insecure_ask: true。实际部署将静态 map 替换为数据库中完成域名验证的有效绑定，解绑后停止放行。

### 授权来源与缓存

精确匹配的已配置 HTTPS 站点可直接授权，不会每次调用 ask。动态 SaaS 域名先经过 allowed_patterns（如果配置），再检查 Litemesh KV，最后回退到 ask；有效 KV 记录可绕过 ask。因此若要求全部动态域名由 ask 决定，请省略 kv_prefix。成功授权缓存约 10 分钟；解绑不会立即撤销已签发的证书或缓存，ask 也不是每个 HTTP 请求的业务访问控制。

## 4. 最佳实践与注意事项

1.  **安全性**: 
    - **域名校验**: LiteGate 内置了严格的 SNI 校验和 IDNA 规范化，会自动拒绝 IP 地址或非法字符。
    - **鉴权接口**: 务必启用 `ask` 接口并严格校验。LiteGate 不再支持非 JSON 的 200 OK 回退，确保安全性。
2.  **生命周期**: 
    - **缓存**: 鉴权结果会在内存中短期缓存（默认 10 分钟），到期后会重新询问 `ask` 接口。
    - **续期**: 证书续期时会**重新鉴权**。如果租户已解绑，LiteGate 将停止续期该证书。
3.  **模板站点配置**: 模板站点应配置在 `sites/` 目录下。
    ```yaml
    site: "template.mysaas.com"
    routes:
      - match:
          path_prefix: "/"
        proxy: ["127.0.0.1:8080"]
    ```

## 5. 代码逻辑解析 (开发者视角)

LiteGate 的实现逻辑位于 `internal/certmanager/certmanager.go` 中的 `handleOnDemand` 方法：

1.  **校验与规范化**: 在 `internal/cert/manager.go` 中通过 `isValidHostname` 和 IDNA 对 SNI 进行规范化。
2.  **鉴权 (checkAuthorization)**: 使用安全参数编码请求 `ask` 接口，并验证 JSON 响应。
3.  **Loader 注册**: 鉴权通过后立即调用 `RegisterSaaSDomain` 建立映射。
4.  **分布式申请**: 获取分布式锁并执行 ACME 挑战。如果申请失败，会调用 `UnregisterSaaSDomain` 清理映射，防止失效路由。
5.  **SAN 保护**: 续期逻辑会提取现有证书的所有 `DNSNames`，确保多域名证书不会在自动续期时被降级。
