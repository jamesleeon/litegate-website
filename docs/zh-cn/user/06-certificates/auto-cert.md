# Auto-Cert (自动化证书管理)

LiteGate 内置了高性能的 ACME 客户端，支持从 Let's Encrypt 等机构自动申请、部署并续期 SSL 证书。它是实现全站 HTTPS 的核心组件。

---

## 1. 核心特性

- **零人工干预**: 证书每日检查，在剩余时间小于等于 `min(renew_days, 证书总有效期 / 3)` 时自动触发续期（`renew_days` 默认为 10 天），无感切换。
- **多 CA 支持**: 除 Let's Encrypt 外，还支持 ZeroSSL、Google Trust Services 及任意自定义 ACME 服务。
- **集群级共享**: 在 Litemesh 模式下，证书存储在分布式 KV 中，所有网关节点共享同一份证书，避免重复申请触发频率限制。
- **多种验证方式**: 支持 HTTP-01（80 端口）、TLS-ALPN-01（443 端口，无需 80/DNS）和 DNS-01（支持泛域名）。

---

## 2. 启用配置

### HTTP-01 验证 (单域名)
适用于网关 80 端口已公网可用的场景。

```yaml
domain: example.com
force_https: true # 开启此项即自动激活 Auto-Cert
routes:
  - name: my-app
    match: { path_prefix: "/" }
    action: { type: proxy, upstream: ["localhost:8080"] }
```

### TLS-ALPN-01 验证 (无需 80 端口，走 443 端口)
适用于运营商/云防火墙**封禁 80 端口**，或者纯 HTTPS 网关不希望对外暴露 80 端口，且**无需配置 DNS API 凭证**的场景。
CA 会直接向目标域名的 443 端口发起 TLS 握手，协商 `acme-tls/1` 协议完成所有权验证。

```yaml
# config.yaml
auto_cert:
  enabled: true
  email: "admin@example.com"
  default_challenge: "tls-alpn"  # 将默认非 DNS 域名的挑战类型设置为 tls-alpn（默认为 http）
```

挑战方式按域名选择：被已启用的 `dns_providers` 条目匹配的域名一律走 DNS-01，其余域名统一使用 `default_challenge`。目前不支持按单个域名在 HTTP-01 与 TLS-ALPN-01 之间单独指定。

> **注意**：
> - 宿主机外部的 443 端口必须能够直通/映射到 LiteGate 的 HTTPS 监听端口；
> - 根据 ACME 规范（RFC 8737），TLS-ALPN 验证仅支持单域名或 SAN 多域名，**不支持泛域名通配符**（泛域名必须使用 DNS-01）。

### DNS-01 验证 (泛域名)
适用于需要申请 `*.example.com` 或内网环境无法开放 80 端口的场景。

需要在 `config.yaml` 中配置 DNS Provider：

```yaml
auto_cert:
  enabled: true
  email: "admin@example.com"
  dns_providers:
    - name: "aliyun"
      type: "aliyun"
      enabled: true
      config:
        access_key_id: "LTAI..."
        access_key_secret: "..."
```

域名与供应商的映射写在 `config.yaml` 的 `dns_providers` 下：

```yaml
# config.yaml
auto_cert:
  enabled: true
  email: "you@example.com"
  dns_providers:
    - name: "aliyun-main"
      type: "aliyun"
      enabled: true
      domains: ["*.example.com", "example.com"]
```

> **安全最佳实践：不要在配置文件里写明文 AK/SK**
> - **首选：密文配置（`enc://`）**：用 `litegate secret encrypt` 把 AK/SK 加密成密文写进 yaml，私钥只留在网关本机，yaml 可以放心流转。详见 [密文配置（Sealed Secrets）](sealed-secrets.md)。
> - **需要集中管理多台网关的凭据**时，可配合 [CredKeeper 凭据托管服务](credkeeper.md) 使用。


---

## 3. 选择证书颁发机构 (CA)

默认使用 Let's Encrypt。通过 `ca_provider` 可切换到其它机构，LiteGate 会自动选用对应的 ACME 目录地址，并为每个 CA 单独保存账号私钥（互不干扰）。

```yaml
auto_cert:
  enabled: true
  email: "you@example.com"
  ca_provider: "zerossl"   # letsencrypt(默认) / zerossl / google / custom
```

| `ca_provider` | 内置 ACME 地址 | 是否需要 EAB |
| :--- | :--- | :--- |
| `letsencrypt`（默认） | `https://acme-v02.api.letsencrypt.org/directory` | 否 |
| `zerossl` | `https://acme.zerossl.com/v2/DV90` | **是** |
| `google` | `https://dv.acme-v02.api.pki.goog/directory` | **是** |
| `custom` | 由 `acme_url` 指定 | 视服务而定 |

### EAB（外部账号绑定）

ZeroSSL 与 Google Trust Services **强制要求** EAB 凭证。请先到对应控制台获取 `eab_kid` / `eab_hmac`，并在配置中成对填写：

```yaml
auto_cert:
  enabled: true
  email: "you@example.com"
  ca_provider: "zerossl"
  eab_kid: "your-key-id"
  eab_hmac: "your-hmac-key"
```

> 提示：若选择 zerossl/google/gts 却未配置 EAB 凭证（eab_kid/eab_hmac），LiteGate 将在启动初始化时直接报告配置错误并拒绝启动。

### 自定义 ACME 服务

私有 CA 或 step-ca 等场景，使用 `custom` 并填写 `acme_url`（必填）：

```yaml
auto_cert:
  enabled: true
  ca_provider: "custom"
  acme_url: "https://ca.internal.example.com/acme/acme/directory"
  acme_ca_cert: "/etc/litegate/private-acme-root.pem"
  acme_headers:
    X-Lito-Token: "your-private-ca-token"
```

> [!TIP]
> **关于 custom CA 升级迁移**
> - 从新版本起，`custom` 模式的全局 CA 校验和账号私钥加入了对 `acme_url` 的 SHA256 哈希作为唯一身份后缀进行强隔离。
> - 如果您是从旧版本（旧版本使用统一的 `"custom"` 作为元数据）升级，启动时可能会被集群 CA 一致性冲突校验（`_cluster_ca_provider` 不匹配）拦截。
> - **解决方法**：升级前，只需手动删除存储（Consul / Litemesh 或者是本地磁盘）中的系统元数据键 `_cluster_ca_provider`（如本地磁盘 `certs_dir` 目录下的 `_cluster_ca_provider.pem` 和 `_cluster_ca_provider.key` 两个系统文件），再次启动即可自动完成无缝迁移。
> - **已有证书重签说明**：仅修改 `acme_url` 时，处于有效期内的已有域名证书**不会被自动强制重签**。若希望立刻将已有域名证书全部切换至新的 Custom ACME 服务端下，可在更改配置的同时，手动在存储中删除对应的旧域名证书（如本地磁盘 `certs_dir` 目录下的 `example.com.pem` 和 `example.com.key` 文件，或者 Consul / Litemesh KV 中对应的 domain bundle 键），网关下次运行即可立即自动完成换签。

---

## 4. 证书存储路径与安全加密

证书及 ACME 私钥默认存储在配置文件指定的 `certs_dir` 目录下：

```text
certs/
├── example.com.pem     # 包含完整证书链
└── example.com.key     # 证书私钥
```

### ACME 账号私钥安全加密

为了避免 ACME 账号注册私钥明文落盘或未加密存储在 Consul/Litemesh 等共享 KV 中引发的安全隐患，建议在全局配置 `config.yaml` 的 `auto_cert` 块中配置 `storage_secret` 对称加密密钥：

```yaml
auto_cert:
  enabled: true
  certs_dir: "./certs"
  storage_secret: "a-secure-32-character-long-secret-key-here!" # 对称密钥，长度需 >= 32 字节
```

- **持久层强加密**：配置 `storage_secret` 后，申请证书所需的全局 ACME 账号私钥（Let's Encrypt 对应键 `_acme_account`，其它 CA 为 `_acme_account_<provider>`，如 `_acme_account_zerossl`，各 CA 互相隔离）以及**域名证书私钥**在保存到持久存储（如共享 Consul/Litemesh KV 存储）之前，均会先通过 AES-256-GCM 算法进行高强度对称加密，密文数据附加 `LG_ENC_001` 魔数前缀。
- **Fail-Closed 故障防御**：若配置了 `storage_secret` 但在持久化时因密钥长度不足等引发加密失败，系统将执行 Fail-Closed 阻断，拒绝明文落盘并报错，消除明文兜底存储漏洞。
- **平滑无感升级**：当网关中存有先前保存的明文 ACME 私钥或域名证书私钥，一旦在 `config.yaml` 中追加定义了非空 `storage_secret` 并在启动或加载时检测到明文，网关在成功将其加载到内存的瞬间，会立即执行 AES 对称加密并覆写回持久化存储层。
- **本地磁盘镜像与同步加密**：本地磁盘上的证书私钥文件（`example.com.key`）仍将保持明文并受严格的 `0600` 文件权限保护（以满足 TLS 握手的高速加载需求）。但是在执行证书同步推送（如 `SyncCertificatesToLitemesh`）上传至 Litemesh KV 存储时，网关会自动使用 `storage_secret` 对私钥进行 AES 加密后再进行分发存储，防止在共享 KV 注册表中发生私钥明文泄漏。

---

## 5. 常见问题排查

### 证书申请一直处于 Pending 状态？
1.  **检查 80 端口**: 如果是 HTTP-01 验证，请确保公网能访问到网关的 80 端口。
2.  **检查 DNS 解析**: 域名 A 记录必须已经指向网关 IP。
3.  **检查频率限制**: Let's Encrypt 对单一域名有每周申请次数限制。

### 如何强制续期？
删除对应的证书及私钥文件（如本地磁盘 `certs_dir` 目录下的 `example.com.pem` 和 `example.com.key`，或者 Consul/Litemesh KV 中对应的 domain bundle/key 键）并重启 LiteGate，网关会立即进入申请流程。

---

## 延伸阅读
- [配置全局 Auto-Cert 参数](../03-configuration/global-config.md#2-自动化证书-auto-cert)
- [生产环境部署建议](../10-deployment/production.md)
