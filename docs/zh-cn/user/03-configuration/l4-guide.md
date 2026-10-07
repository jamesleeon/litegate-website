<!-- GENERATED FILE — DO NOT EDIT.
     Source: internal/configdocs/docs/zh/stream-config.md (package internal/configdocs)
     Regenerate: go generate ./internal/configdocs/...
     Edit the source instead; a drift test fails if this copy is edited directly. -->

# L4 Stream Guide

## 统一的 `site` 写法

新配置可以像 HTTP 站点一样使用 `site` 和 `proxy`。L4 文件仍放在 `streams/`，
HTTP 文件放在 `sites/`。简写会转换成现有 Stream 运行配置；旧的 `name`、`port`、
`protocol`、`upstream`、`listen`、`hostnames` 写法继续兼容。

```yaml
# streams/mysql.yaml：独立 TCP 端口
site: tcp://:3307
proxy: 192.168.1.100:3306
---
# streams/dns.yaml：独立 UDP 端口
site: udp://:5353
proxy: 192.168.1.100:53
---
# 共享 TCP 443，按 TLS SNI 分流
site: tcp://db.example.com
entrypoints: [websecure]
proxy: 192.168.1.100:3306
```

- `tcp://:端口`、`udp://:端口` 创建独立监听，端口范围 1–65535。暂不支持绑定 IP 或路径；
  不可同时配置 `listen: false` 或共享 entrypoints。
- `tcp://域名` 设置 `hostnames` 和 `listen: false`。未启用 Connect 发布时默认挂载
  `[websecure]`。这不是普通 TCP 的域名路由：共享 443 的客户端必须发送匹配的 TLS SNI；
  原生 MySQL、SSH 和明文 TCP 应用应使用独立端口或经过认证的 Forward。
  未配置终止 TLS 的 `tls` 时，由上游处理 TLS。
- UDP 不支持按域名分流，`udp://域名` 会被拒绝。
- `proxy` 是字符串形式的 `upstream` 别名，两者不能同时使用。
  服务发现则省略两者，使用 `service_name` 和 `upstream_type`。
- `name` 可省略，自动生成 `tcp-3307`、`udp-5353`、`tcp-db.example.com`。
  Forward 或 Entrypoint `handle.stream` 引用流时，建议显式设置稳定名称。
- `enabled` 默认 true。单条、列表和 `---` 多文档使用同一严格解析器，未知字段和冲突简写会报错。

### 经过认证的 Forward 私有目标

私有目标没有监听地址，因此不用填写 `site`；设置名称供 HTTP Forward 站点引用：

```yaml
# streams/private-mysql.yaml
name: private-mysql
protocol: tcp
listen: false
proxy: 192.168.1.100:3306
```

```yaml
# sites/forward.yaml
site: forward.example.com
forward:
  target: {type: stream, name: private-mysql}
  token_file: ./secrets/forward.token
```

### Connect 发布

Private 节点在全局启用 Connect client 后，可发布流而不开本地公网端口：

```yaml
site: tcp://mysql.home.example.com
name: home-mysql
connect_publish: forward_only
proxy: 192.168.1.20:3306
```

`forward_only` 通过 Cloud 上经过认证的 Forward 访问；只有确实需要在 Cloud 暴露 TLS SNI
入口时才使用 `public`，它本身不增加认证。隧道配置参见 [Connect](../09-advanced/connect.md)。
共享端口实战参见 [同一个 443 承载 HTTPS 与 L4 TCP](../09-advanced/shared-443-l4-stream.md)。

### SOCKS5 与验证流程

```yaml
name: private-socks5
protocol: socks5
listen: false
socks5:
  allowed_destinations: ["10.0.0.0/8:3306", "192.168.1.0/24:22"]
```

SOCKS5 逐连接选择目标，必须配置白名单，不使用固定 `proxy`。
应用配置前运行 `litegate -t`。MCP 应先读取 `get_stream_config_schema`，再调用
`validate_stream_config` 和 `save_stream_config`。保存成功不代表重载成功；应用后检查
运行时 Stream 并验证实际连通性。


## TLS 终止与字段参考

共享 SNI 路由默认将 TLS 字节转交上游。若需要 LiteGate 终止 TLS 并向后端发送明文 TCP，
启用 Stream TLS：

```yaml
site: tcp://db.example.com
proxy: 192.168.1.100:3306
tls:
  enabled: true
  auto_cert: true
```

先在全局启用 `auto_cert` 并配置证书签发。Stream 的 `tls.domains` 默认使用站点域名，
已有有效且覆盖域名的证书会复用。使用手动证书时，将 `auto_cert` 替换为 `cert_file` 和
`key_file`。共享 Stream 会优先于同域名 HTTP 站点分流，不应无意间让两者使用同一域名。

| 字段 | 含义 |
| --- | --- |
| `site` | TCP/UDP 端口地址或 TCP TLS SNI 域名。 |
| `proxy` / `upstream` | 一个静态后端，TCP 支持 Unix socket；选择一种拼写。 |
| `name` | 稳定的运行时标识；省略时从 `site` 生成。 |
| `entrypoints` | 当前支持 `[websecure]`；共享入口不创建独立监听。 |
| `listen` | 旧配置默认 true；域名简写自动设为 false。 |
| `enabled` | 默认 true；显式 false 禁用 Stream。 |
| `service_name`, `upstream_type`, `service_tag` | 发现目标、注册中心与可选标签筛选。 |
| `lb_policy`, `backends` | 负载均衡策略和后端列表。 |
| `connect_publish` | `public`、`forward_only` 或 false / `disabled`。 |
| `tls` | TLS 终止或 `passthrough`；UDP 不支持 TLS 终止。 |
| `ip_restriction` | Stream IP 允许/拒绝规则。 |
| `idle_timeout` | 空闲超时秒数；省略或零值默认 60 秒。 |
| `max_sessions` | 并发会话上限。 |
| `proxy_protocol`, `proxy_protocol_version` | PROXY 协议头；后端必须支持。 |
| `socks5.allowed_destinations` | `protocol: socks5` 必填的目标白名单。 |

高级 TLS 路由、UDP、PROXY 协议、服务发现和运行细节参见 [Stream 字段参考](stream-config.md)。
