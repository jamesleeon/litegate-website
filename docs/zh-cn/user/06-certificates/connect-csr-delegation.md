# Connect CSR 证书委托

Private 节点本地生成私钥与 CSR，通过已认证的 Connect 通道请 Cloud 代办 DNS-01，Cloud 仅返回证书链，私钥不传给 Cloud。Private 校验证书与 CSR 公钥、域名和链后保存并使用；Cloud 无需获知 Private 的存储密钥。

Cloud 启用 auto_cert 与 DNS Provider，并为 Peer 配置 allowed_cert_domains；Private 使用 Connect 客户端和本地证书存储。域名需属于该 Peer 的当前精确声明。拒绝通配符、保留域名、Cloud 本地站点冲突、CSR 声明不一致及所有权变化。签发还受冷却与预算限制。

auto_cert.storage_secret 可通过安全引用保护本地私钥存储，但不能防御被完全控制的主机。证书未就绪时发布状态为 pending_certificate，不应描述为无条件零丢失。上线前测试首次申请、续期、Peer 撤销、域名转移与 DNS 权限失效。CA 的外部额度以实际服务为准，不能按固定租户数承诺容量。

## 相关文档与代码

- [Connect configuration](../09-advanced/connect.md)
- [Certificate methods](certificate-application-guide.md)
- [Implementation](../../../../internal/connect)
