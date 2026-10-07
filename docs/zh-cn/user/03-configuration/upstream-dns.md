# 上游自定义 DNS

默认情况下，代理域名使用 Go 的默认解析机制。需要访问企业内网、VPN 或内外网返回不同地址的域名时，可以为上游指定独立 DNS，不必修改宿主机的 DNS。

在全局 `config.yaml` 中定义命名解析器：

```yaml
resolvers:
  corp:
    servers: [192.168.1.53:53, 192.168.1.54:53]
    timeout: 2s
```

`servers` 必须是带端口的 IP 地址，IPv6 使用 `[地址]:53`。多个服务器应属于同一个 DNS 视图；查询超时、连接失败或 SERVFAIL 等错误时按列表尝试备用服务器。NXDOMAIN 和无对应地址记录不会触发切换。`timeout` 是每次服务器查询的超时，省略或为零时使用 2 秒；整个连接过程仍受上游连接超时和请求截止时间约束。

V2 内联代理引用解析器：

```yaml
site: app.example.com
proxy:
  to: https://a.b.com
  resolver: corp
```

也可以在命名 Service 中配置，供多条路由复用：

```yaml
site: app.example.com
services:
  backend:
    to: https://a.b.com
    resolver: corp
    timeout: 5s
    health: {path: /health, interval: 10s}
/api:
  service: backend
```

旧标准 YAML / 高级 `action` 的代理使用 `resolver: corp`，与 `upstream` 或 `service_name` 同层。引用命名 Service 的路由不能另行覆盖 `resolver`。未知解析器在配置加载时被拒绝，包括未被路由引用的 Service。

解析器只改变连接目标 IP；请求 Host、HTTPS SNI 和证书域名验证沿用已有上游策略。HTTP、HTTPS、gRPC、快速 HTTP/1、WebSocket/协议升级、FastCGI TCP 连接和相关主动健康检查使用选定解析器。服务发现返回域名时也适用，返回 IP 则直接连接；Unix Socket 不需要 DNS。

显式选择解析器后，不读取系统 hosts，也不回退系统 DNS。为保证 DNS 视图生效，该上游直接连接，不使用 `HTTP_PROXY` / `HTTPS_PROXY` 等环境代理；未指定解析器的上游保持原有行为。不同 DNS 配置的连接池与主动健康检查状态独立。

当前支持 UDP DNS，响应截断时改用 TCP；支持 A、AAAA 和 CNAME。每次新建连接重新查询，不额外缓存 DNS 结果，也不将 DNS 多地址展开为网关负载均衡实例。已建立连接可以继续复用，DNS 地址变化不会立即迁移长连接。修改解析器配置并成功重新编译站点后，新请求使用新配置对应的连接池；进行中的请求保留旧配置。

文件站点在全局配置成功重载时重新编译；删除仍被引用的解析器会拒绝重载并保留旧配置。Consul/LiteMesh `config_watch` 模式下修改或删除 `resolvers` 需要重启，热重载会明确拒绝，避免站点继续绑定旧解析器。

DoH、DoT、SRV 服务发现和 ECH 不属于本功能。
