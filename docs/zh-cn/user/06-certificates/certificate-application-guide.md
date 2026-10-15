# 证书申请方式与配置

公网普通域名可使用 HTTP-01（CA 可访问 80）或 TLS-ALPN-01（CA 可访问 443，default_challenge: tls-alpn）。通配符必须使用 DNS-01，并配置可修改 TXT 记录的 DNS Provider。域名解析、端口映射与监听入口都需要正确设置；首次验证使用 staging，成功后切生产。

auto_cert.enabled 启用申请；email、ca_provider、certs_dir、renew_days 管理账户与证书生命周期。默认发行版包含 aliyun、tencent、cloudflare；其他 DNS 服务商需编译插件。DNS 凭据使用安全引用或密文，勿提交明文密钥。

ZeroSSL/Google Public CA 及自定义 ACME 的账户要求按所选服务配置；私有 CA 需客户端信任根。单机开发使用 Local CA。Private 节点无 DNS 凭据时，可使用 Connect CSR 委托，让私钥保留在 Private。

排错先检查 DNS、挑战端口、DNS API 权限、证书保存目录和日志。不要将 staging 证书用于生产，或把自动续期等同于跨副本证书同步。

```yaml
auto_cert:
  enabled: true
  email: ops@example.com
  ca_provider: letsencrypt
  default_challenge: tls-alpn
  use_staging: true
  certs_dir: ./certs
  renew_days: 10
```

## 相关文档与代码

- [Auto cert](auto-cert.md)
- [DNS providers](dns-providers.md)
- [CSR delegation](connect-csr-delegation.md)
- [Local CA](local-ca.md)
