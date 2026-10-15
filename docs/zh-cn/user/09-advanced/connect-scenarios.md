# Connect 场景与部署职责

Connect 适合内网网站通过 Cloud 发布的场景：Private 主动建立连接，Cloud 接收公网 SNI 流量并转交 Private，Private 负责完整 Site 的 TLS、认证和业务代理。多个分支使用不同 Peer 和明确域名授权。

浏览器无需隧道客户端；数据库等非 HTTP 场景需要 Stream 与匹配的客户端协议。Cloud 域名授权、Private 域名声明、证书就绪和后端可达性必须同时满足。CSR 委托可避免把 DNS 凭据和私钥集中到 Cloud。

需要高可用时按现有配置测试连接重建和节点故障，而不把历史 N×M 架构提案当作已发布承诺。上线检查公网 DNS、443、Peer 凭据、域名冲突、待签发状态以及业务应用自身授权。

## 相关文档与代码

- [Connect](connect.md)
- [CLI HTTP](connect-cli-http.md)
- [CSR delegation](../06-certificates/connect-csr-delegation.md)
