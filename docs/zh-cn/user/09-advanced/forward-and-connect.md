# Forward 与 Connect

Forward 将 Cloud 可访问的 TCP 资产映射给持有 Token 的客户端；Connect 将 Private/Home 的网站或 TCP Stream 发布到 Cloud 公网入口。两者由内侧主动建立 TLS 连接，但流量方向不同。

| 场景 | 选择 |
|---|---|
| 本机数据库工具访问云 RDS/Redis/SSH | Forward 客户端与 Cloud Forward Site |
| 无公网 IP 的内网网站发布为 HTTPS | Connect Cloud 与 Private/Home |
| 访问 Home 内的 TCP 资产 | 按需组合 Forward 与 Connect |
| 整网互联或任意 UDP | 不能将两者当作通用 VPN |

Forward 隧道不是浏览器 HTTP 正向代理；后者使用 forward_proxy 插件。Forward 单目标或多映射的准确语法、Token、目标白名单与传输选择见 Stream 指南。Connect 的 Cloud 负责 SNI/L4 转交，完整 Site 模式在 Private 终结 TLS、执行 L7 中间件；HTTP CLI 简化模式有独立限制。

数据库即使借用 443 也需要匹配的隧道客户端或 TLS 包装，不能直接把原生明文数据库连接发到 HTTPS。

## 相关文档与代码

- [Stream / Forward](../03-configuration/stream-config.md)
- [Connect](connect.md)
- [CLI HTTP](connect-cli-http.md)
- [Forward proxy](../../forward-vs-forward-proxy.md)
