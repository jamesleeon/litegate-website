# Forward 隧道与 HTTP 正向代理

Forward 是 LiteGate 客户端访问已授权 TCP 资产的隧道；HTTP forward_proxy 是浏览器/工具通过代理访问目标 HTTP/HTTPS 的入口插件，两者协议与授权不同。

Forward 的目标由服务端映射与白名单约束，适合数据库、SSH 等；正向代理处理绝对 URL 或 CONNECT，客户端设置标准代理地址。两者均需认证、目标限制与日志，不因名字相似而共享配置。

HTTP 正向代理不能冒充通用 UDP VPN；Forward 也不能用普通浏览器代理设置代替专用隧道客户端。按下面两套指南配置并验证拒绝未授权目标。

## 相关文档与代码

- [Forward tunnel](user/03-configuration/stream-config.md)
- [Forward proxy example](../../examples/plugins/ingress/forwardproxy/README.md)
- [Ingress plugin](ingress-plugin-guide.md)
