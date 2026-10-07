# 密文配置（Sealed Secrets）：配置文件中不出现明文密钥

## 一、解决什么问题

DNS-01 申请证书需要云厂商的 AccessKey/SecretKey。直接写在 `config.yaml` 里，一旦配置文件被传给同事、提交到 git、进入备份或出现在工单截图里，密钥就泄露了。

密文配置的做法是：**yaml 里只写密文，解密私钥只存在网关本机**。

- 公钥可以公开，谁都能用它加密，但加密后只有持有私钥的那台网关能解开。
- 配置文件拷到其他机器上无法解密，可以放心流转、进 git。
- 实施人员全程只经手密文：客户安全人员用公钥自行加密 AK/SK，再把密文交给实施方。

算法：X25519 密钥协商 + HKDF-SHA256 + AES-256-GCM（每次加密使用随机临时密钥，同一明文每次加密结果都不同，篡改会被检测）。

## 二、安全边界（请如实告知客户）

| 场景 | 是否防护 |
| :--- | :--- |
| 配置文件外泄（git、邮件、工单、截图、备份） | ✅ 防护：只有密文 |
| 配置文件被拷到其他机器 | ✅ 防护：没有私钥无法解密 |
| 攻击者已获得网关主机的 root/管理员权限 | ❌ 无法防护：可读取私钥，也可读取进程内存 |

任何纯软件方案都无法防御主机被完全控制（网关最终必须用明文调用云 API）。请配合主机加固、最小权限的 RAM 子账号（仅授予 DNS 解析权限）一起使用。

## 三、使用步骤

### 1. 在网关主机上生成密钥对（每台主机一次）

```bash
litegate secret keygen
```

- 私钥默认写入 `/etc/litegate/secret.key`（Windows：`%ProgramData%\LiteGate\secret.key`），权限 0600。
- 屏幕输出的 `lgpk1_...` 是公钥，可以发给客户安全人员。
- 私钥请离线备份。**私钥丢失后，所有用它加密的密文都无法解开**，只能重新生成密钥对并重新加密。
- 已存在私钥时命令会拒绝覆盖，确需重建请加 `--force`。

随时可以查看本机公钥：

```bash
litegate secret pubkey
```

### 2. 加密密钥

在网关本机加密（默认使用本机公钥），从标准输入读取，避免明文留在 shell 历史里：

```bash
litegate secret encrypt
```

客户安全人员在自己的电脑上，用网关的公钥加密：

```bash
litegate secret encrypt --pubkey lgpk1_xxxxxxxx
```

输出形如 `enc://AWoirIpF...` 的一行密文。

### 3. 写入配置

```yaml
auto_cert:
  enabled: true
  email: "admin@example.com"
  dns_providers:
    - name: aliyun
      type: aliyun
      domains: ["*.example.com"]
      config:
        access_key_id: "enc://AWoirIpF..."
        access_key_secret: "enc://AbX9k2Qe..."
        region_id: "cn-hangzhou"   # 非敏感字段可保持明文
```

`enc://` 可用于所有支持密钥引用的字段（DNS 服务商 `config` 下的各项、`webhook_token` 等），与 `env://`、`file://`、`${VAR}` 用法一致。

## 四、私钥的查找顺序

1. 环境变量 `LITEGATE_SECRET_KEY`（直接给出私钥内容，适合容器 secret / systemd credentials 注入）
2. 环境变量 `LITEGATE_SECRET_KEY_FILE`（私钥文件路径）
3. 平台默认路径：Linux/macOS `/etc/litegate/secret.key`，Windows `%ProgramData%\LiteGate\secret.key`

> 请勿把私钥文件放在配置目录里，也不要和配置一起打包、备份或提交。

## 五、与 CredKeeper 的关系

- **单台或少量网关**：直接使用密文配置即可，无需额外部署服务。
- **多台网关共享、需要集中轮换凭据**：使用 [CredKeeper](credkeeper.md)。此时 `secret_token` 本身也可以写成 `enc://` 密文，这样 yaml 里同样没有任何明文秘密。
