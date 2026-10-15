# 密文配置（Sealed Secrets）

enc:// 让配置保存密文，网关用本机私钥解密。算法为 X25519、HKDF-SHA256 和 AES-256-GCM，每次加密使用随机临时密钥。它保护配置文件外泄，不能保护已被管理员/root 完全控制的主机。

在网关运行 secret keygen，公钥 lgpk1_... 可分发；私钥默认保存在 Linux /etc/litegate/secret.key、Windows %ProgramData%\LiteGate\secret.key。已存在时拒绝覆盖，--force 会重建；私钥丢失需重新加密全部值。使用 secret pubkey 随时导出公钥。

secret encrypt 从标准输入读取；客户机器可通过 --pubkey 指定网关公钥。将输出的 enc:// 值填入支持 secret 引用的字段，如 DNS config。不要将它用于任意不支持解析的配置字段。

解析私钥先检查 LITEGATE_SECRET_KEY，再检查 LITEGATE_SECRET_KEY_FILE，最后使用默认文件。备份私钥并限制权限；多台机器使用不同私钥时需分别加密。

```bash
litegate secret keygen
litegate secret pubkey
litegate secret encrypt --pubkey lgpk1_REPLACE_WITH_GATEWAY_PUBLIC_KEY
```

## 相关文档与代码

- [Resolver](../../../../internal/secret/enc.go)
- [CLI](../../../../pkg/litegate/secret_cmd.go)
