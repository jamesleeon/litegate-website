# 数据库 TCP 资产访问

云内网数据库可通过 Forward Site/Stream 给持有 Token 的客户端提供受控隧道，或通过 Connect 发布 Private 内的 Stream。网关是 TCP 传输层，不解析 SQL、不替代数据库账户与权限。

客户端本地监听映射到受授权目标，数据库工具连接本地端口。服务端应限定目标白名单、Peer/Token 与入口，数据库自身限制账户、网络权限与加密。不要把未包装的数据库协议直接发往 HTTPS，也不要开放任意目标 SOCKS/正向代理。

多映射、--target、传输 auto/v3/v2 与 TLS 参数使用当前 Stream/Forward 指南；默认值和协商兼容性不能从历史单目标设计推断。RDS 场景还需确认 Cloud 网关到 RDS 的网络、账号、端口与空闲超时。

## 相关文档与代码

- [Forward configuration](user/03-configuration/stream-config.md)
- [Forward / Connect](user/09-advanced/forward-and-connect.md)
- [Connect](user/09-advanced/connect.md)
