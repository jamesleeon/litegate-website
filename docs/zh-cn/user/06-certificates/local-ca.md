# 本地 CA (Local CA / 自签自信任)

本地 CA 让 LiteGate **自己充当证书颁发机构**：生成一个本地 Root CA，并为本地/内网域名按需即时签发叶子证书。适合 `localhost`、`*.test`、内网域名等**公网 CA 签不了**的场景，让本地开发也能用上绿锁 HTTPS。对标 Caddy 的 `tls internal`。

> 与 ACME / On-Demand TLS 的区别：ACME 由 Let's Encrypt 等公网 CA 签发、浏览器默认信任；本地 CA 由 LiteGate 自签，需要把它的 Root CA **导入一次系统/浏览器信任库**才不会报警告。

---

## 1. 启用

在 `config.yaml` 中开启：

```yaml
tls:
  local_ca: true                       # 启用本地 CA
  local_ca_domains:                    # 允许签发的域名（可选）
    - ".localhost"
    - ".test"
    - "my-app.internal"
  local_ca_trust: false                # 是否自动装入系统信任库（见第 4 节）
```

启用后：

- 首次启动会在证书目录（默认 `./certs`）生成 `local_root_ca.crt` 与 `local_root_ca.key`；
- 访问命中允许域名时，网关在内存即时签发该域名的叶子证书并完成 HTTPS 握手。

---

## 2. 字段参考

| 字段 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `local_ca` | bool | `false` | 启用本地 CA 按需签发 |
| `local_ca_domains` | string[] | `[".localhost", ".test"]` | 允许签发的域名白名单。`.` 开头表示后缀匹配；不带点表示精确匹配（含其子域） |
| `local_ca_trust` | bool | `false` | 是否在**首次生成** Root CA 时自动装入本机系统信任库 |

> `localhost`、`127.0.0.1`、`::1` 始终允许，无需显式配置。

---

## 3. 域名白名单匹配规则

- `.localhost` —— 匹配 `app.localhost`、`api.localhost` 等任意子域；
- `my-app.internal` —— 精确匹配 `my-app.internal`，也匹配其子域 `x.my-app.internal`；
- 不在白名单内的域名**不会**被本地 CA 签发（公网域名仍走 ACME）。

这一限制确保即使 Root CA 私钥泄露，影响也被限定在本地/内网域名内。

---

## 4. 信任 Root CA

浏览器默认不信任自签 CA。两种方式让它信任：

### 方式 A：自动（`local_ca_trust: true`）
LiteGate 会在**首次生成** Root CA 时尝试装入系统信任库：

- Windows：`certutil -user -addstore ROOT`（用户级，无需管理员）
- macOS：`security add-trusted-cert`（可能需要授权）
- Linux：复制到 `/usr/local/share/ca-certificates/` 并执行 `update-ca-certificates`（需要 root）

> ⚠️ **安全提示**：把 Root CA 装进系统信任库等于赋予其签发任意站点证书的能力。**仅在你自己的开发机上开启 `local_ca_trust`**，不要在共享/staging/生产环境开启。该动作只在首次生成 CA 时执行，不会每次启动重复。

### 方式 B：手动
保持 `local_ca_trust: false`，把 `./certs/local_root_ca.crt` 手动导入系统/浏览器信任库。团队共享时推荐这种方式，更可控。

---

## 5. 典型用法：本地开发 HTTPS

```yaml
tls:
  local_ca: true
  local_ca_domains: [".localhost"]
  local_ca_trust: true        # 仅本机开发开启
```

```yaml
# sites/app.localhost.yaml
site: https://app.localhost
proxy: 127.0.0.1:3000
```

之后访问 `https://app.localhost` 即为受信任的 HTTPS，无证书警告。

---

## 安全说明

- Root CA 私钥保存在 `./certs/local_root_ca.key`，文件权限 `0600`，请勿外泄或提交到仓库。
- 签发受**速率限制（5/s）**与**缓存淘汰**保护，避免被构造大量不同 SNI 打爆 CPU / 内存。
- 本地 CA 仅用于本地/内网；面向公网的站点请使用 [Auto-Cert (ACME)](./auto-cert.md) 或 [On-Demand TLS](./on-demand-cert.md)。

---

## 延伸阅读
- [Auto-Cert 自动证书](./auto-cert.md)
- [On-Demand TLS 按需签发](./on-demand-cert.md)
