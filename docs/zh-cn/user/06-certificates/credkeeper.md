# CredKeeper 集中凭据托管

CredKeeper 是独立服务，通过 Web 控制台录入 DNS 凭据，并以 AES-256-GCM 加密保存。LiteGate 使用 secret:// 引用按需获取，解密结果短期缓存在内存。单机仅需避免 YAML 明文时，可先使用 Sealed Secrets。

secret_token 同时用于鉴权和解密，必须像主密钥一样保护，建议使用 env://、file:// 或 enc://。CredKeeper 默认监听回环；跨主机通信使用 HTTPS 或受保护通道。响应加密不能替代 TLS，因为 token 随请求传输。轮换凭据与 token 时同步更新客户端。

默认网关内置 aliyun、tencent、cloudflare。CredKeeper 可以保存其他服务商凭据，但不自动为网关安装 DNS 插件；例如 huawei 必须先编译对应插件。HTTP-01/TLS-ALPN-01 不需要 DNS API 密钥；通配符 DNS-01 才需要这些凭据。

先验证服务启动、密文存储权限、客户端认证与所引用凭据名称，再测试 staging 证书申请。不要将凭据文件、token 或私钥放入公开仓库。

## 相关文档与代码

- [Sealed secrets](sealed-secrets.md)
- [Service implementation](../../../../credkeeper)
- [Secret resolver](../../../../internal/secret)
