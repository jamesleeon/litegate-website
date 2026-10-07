# 证书申请配置指南

本文说明 LiteGate 如何申请、续期和保存 HTTPS 证书，覆盖 Let's Encrypt、ZeroSSL、Google Public CA、自定义 ACME、LiteMesh 私有 CA、通配符证书和本地开发 CA。

## 1. 先选择申请方式

| 场景 | 推荐方式 | 客户端是否需要额外信任根证书 |
| :--- | :--- | :--- |
| 公网普通域名 | Let's Encrypt + HTTP-01 | 否 |
| 公网普通域名（80 端口被封或无需开放 80） | Let's Encrypt + TLS-ALPN-01 | 否 |
| 公网通配符域名 | Let's Encrypt + DNS-01 | 否 |
| 内网穿透/混合云多租户 | Connect 委托签发（DNS-01 代办 + 私钥本地闭环） | 否 |
| 需要备用公网 CA | ZeroSSL 或 Google Public CA | 否 |
| 企业内网域名 | LiteMesh/其他私有 ACME + DNS-01 | 是 |
| 单机开发域名 | LiteGate Local CA | 是 |

证书申请需要 `auto_cert.enabled: true`。HTTP-01 要求 CA 能访问域名的 80 端口；TLS-ALPN-01 要求 CA 能访问域名的 443 端口（无需开放 80 端口，也无需配置 DNS API 凭据）；DNS-01 要求 LiteGate 有权限创建 `_acme-challenge` TXT 记录；若内网 Private 节点没有公网 DNS 凭据且需要端到端 TLS 终结，推荐使用 [Connect 证书委托签发](connect-csr-delegation.md)。

## 2. Let's Encrypt 普通域名 (HTTP-01)

```yaml
auto_cert:
  enabled: true
  email: "ops@example.com"
  ca_provider: "letsencrypt"
  use_staging: false
  certs_dir: "./certs"
  renew_days: 10
```

确认域名 A/AAAA 记录指向 LiteGate，并把宿主机 80、443 端口映射到 LiteGate。首次调试可设置 `use_staging: true`，验证成功后再切回生产环境。

## 2.1 Let's Encrypt 普通域名 (TLS-ALPN-01)

如果您的 80 端口被运营商或云防火墙拦截，或者纯 HTTPS 网关不希望开启 80 端口，且没有 DNS API 凭据，推荐使用 TLS-ALPN 验证：

```yaml
auto_cert:
  enabled: true
  email: "ops@example.com"
  ca_provider: "letsencrypt"
  default_challenge: "tls-alpn"  # 开启全局 TLS-ALPN-01 验证（走 443 端口）
  certs_dir: "./certs"
```

CA 在验证时会直接向 443 端口发起 TLS 握手，LiteGate 内部会自动协商 `acme-tls/1` 协议完成挑战，签发正式证书。
> 提示：TLS-ALPN 不支持申请通配符证书（`*.example.com`），若需通配符证书请配置下方的 DNS-01。

## 3. DNS-01 与通配符证书

通配符证书不能使用 HTTP-01，必须配置 DNS Provider：

```yaml
auto_cert:
  enabled: true
  email: "ops@example.com"
  ca_provider: "letsencrypt"
  dns_providers:
    - name: "aliyun-main"
      type: "aliyun"
      enabled: true
      domains: ["example.com", "*.example.com"]
      config:
        access_key_id: "${ALIYUN_ACCESS_KEY_ID}"
        access_key_secret: "${ALIYUN_ACCESS_KEY_SECRET}"
```

`domains` 决定哪些域名使用该 DNS Provider。同一张 SAN 证书中的所有域名必须命中同一个挑战 Provider。

## 4. ZeroSSL 与 Google Public CA

两者都需要 EAB：

```yaml
auto_cert:
  enabled: true
  email: "ops@example.com"
  ca_provider: "zerossl" # 或 google
  eab_kid: "your-eab-key-id"
  eab_hmac: "your-eab-hmac"
```

Google 设置 `use_staging: true` 时会使用其测试目录。生产和测试环境的 EAB 凭据不能混用。每个 CA 使用独立的 ACME 账号私钥。

> Buypass 已停止签发 TLS 证书，LiteGate 不再接受 `ca_provider: buypass`。

## 5. 自定义 ACME 与私有 HTTPS 根证书

```yaml
auto_cert:
  enabled: true
  email: "pki@example.internal"
  ca_provider: "custom"
  acme_url: "https://ca.example.internal/acme/directory"
  acme_ca_cert: "/etc/litegate/private-acme-root.pem"
  acme_headers:
    Authorization: "Bearer private-acme-token"
```

`acme_ca_cert` 可以是 PEM 文件路径，也可以直接填写 PEM 内容。LiteGate 会在系统信任库基础上追加该根证书，不会关闭 TLS 校验。`acme_headers` 只允许在 `custom` 模式使用，敏感值应通过受保护的配置或密钥管理系统注入。

## 6. 使用 LiteMesh 私有 CA 签发站点证书

LiteMesh 有两类接口：

- `/v1/ca/sign`：签发 SPIFFE/mTLS 工作负载身份证书。
- `/acme/directory`：供 LiteGate 申请网站 HTTPS 证书。

### 6.1 启用 LiteMesh ACME

```yaml
ca:
  bootstrap: true
  cert_valid_days: 365
  acme:
    enabled: true
    domain_policies: [".internal", ".svc.litemesh"]
    disable_challenge: false
    allow_private_http01: false
```

生产环境推荐保留挑战校验，并为内部 DNS 配置 DNS-01。LiteMesh 会同时向普通域名发布 HTTP-01 和 DNS-01；通配符域名只发布 DNS-01。

LiteGate 配置示例：

```yaml
auto_cert:
  enabled: true
  email: "pki@example.internal"
  ca_provider: "custom"
  acme_url: "http://litemesh:8080/acme/directory"
  dns_providers:
    - name: "internal-dns"
      type: "mydns" # plugin.RegisterDNSProviderV2 注册的名称
      enabled: true
      domains: ["corp.internal", "*.corp.internal"]
      config:
        endpoint: "https://dns-api.example.internal"
        token: "your-dns-api-token"
```

如果 LiteMesh ACME 使用私有 HTTPS，再增加 `acme_ca_cert`。DNS Provider 写入的 TXT 记录必须能被 LiteMesh 所使用的 DNS 解析器查询到。

### 6.2 内网 HTTP-01

只有在 CA 与目标主机处于可信隔离网络时，才可设置：

```yaml
ca:
  acme:
    allow_private_http01: true
```

该选项允许 LiteMesh 访问私网/回环地址进行 HTTP-01 校验，会扩大 SSRF 访问面；能使用 DNS-01 时不要开启。

### 6.3 受信任环境跳过挑战

测试或高度受控的内部环境可以设置 `disable_challenge: true`，并让 LiteGate 携带集群 Token：

```yaml
auto_cert:
  ca_provider: "custom"
  acme_url: "http://litemesh:8080/acme/directory"
  acme_headers:
    X-Lito-Token: "your-litemesh-cluster-token"
```

不要在开放网络中跳过域名控制验证。

### 6.4 分发 LiteMesh 根证书

私有 CA 签发的站点证书不会自动被浏览器、操作系统或业务容器信任。通过 LiteMesh `GET /v1/ca/root` 导出根证书，并安装到所有访问端的信任库。根证书可以分发，根私钥绝不能离开 CA 节点。

## 7. LiteMesh mTLS 身份证书

使用集群管理员 Token：

```yaml
litemesh:
  enabled: true
  address: "litemesh:8080"
  token: "cluster-token"
  mtls: true
  spiffe_id: "spiffe://litemesh.local/ns/default/sa/litegate"
```

或者使用工作负载凭据：

```yaml
litemesh:
  enabled: true
  address: "litemesh:8080"
  mtls: true
  spiffe_id: "spiffe://litemesh.local/ns/default/sa/litegate"
  workload_service_id: "litegate-node-1"
  workload_token: "registered-workload-token"
```

工作负载的服务名、命名空间、来源 IP 和 Token 必须与 LiteMesh 注册信息一致。

## 8. LiteGate Local CA

```yaml
tls:
  enabled: true
  certs_dir: "./certs"
  local_ca: true
  local_ca_domains: [".localhost", ".test", "dev.internal"]
  local_ca_trust: false
```

根证书位于 `certs/local_root_ca.crt`。建议手动分发和信任；不要在生产环境开启 `local_ca_trust`。如果根证书或私钥缺失、损坏，LiteGate 会拒绝自动换根，避免所有客户端突然失去信任。

## 9. 排错清单

1. 查看日志中实际选择的 CA URL 和挑战类型。
2. HTTP-01：从 CA 所在网络访问 `http://域名/.well-known/acme-challenge/test`，确认 80 端口可达。
3. DNS-01：查询 `_acme-challenge.域名` 的 TXT，确认权威 DNS 和 LiteMesh 使用的解析器都可见。
4. 私有 HTTPS ACME：确认 `acme_ca_cert` 是签发 ACME 服务端证书的根证书。
5. ZeroSSL/Google：确认 EAB 完整、属于正确环境，且 ACME 账号私钥存储未丢失。
6. 私有 CA 证书浏览器报不可信：检查访问端是否安装了正确的 Root CA，而不是只检查 LiteGate 服务端。
7. 集群部署：所有 LiteGate 节点必须使用相同 `ca_provider` 和 `acme_url`，并共享证书存储。
