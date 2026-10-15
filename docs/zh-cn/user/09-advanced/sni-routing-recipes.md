# SNI 分流实战

SNI 在 TLS 握手阶段选择 L4 处理路径，不能按 HTTP Path 分流。按 Path/Header/Query 选择上游，需要先终结 TLS 后执行 L7 路由。共享 443 的配置以挂载 Stream 为基础。

透传时上游负责证书、ALPN 与 HTTPS；终止时 LiteGate 负责证书，再把解密后的字节发往匹配协议的后端。不要将 TLS 上游误当明文后端。数据库和自定义 TCP 协议需客户端能发出预期 SNI。

迁移配置时逐项核对 SNI 匹配、非 TLS/无 SNI 策略、上游 TLS、PROXY Protocol 与空闲超时。精确域名、通配符和冲突应通过当前加载校验验证；不按其他项目的路由顺序推断 LiteGate 行为。

## 相关文档与代码

- [Shared 443 example](shared-443-l4-stream.md)
- [L4 configuration](../03-configuration/l4-guide.md)
- [Entrypoints](../03-configuration/entrypoints.md)
