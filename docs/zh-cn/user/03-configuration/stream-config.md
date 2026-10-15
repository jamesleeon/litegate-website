# Stream 与 Forward 配置

## Stream 入口与上游

Stream 文件位于 streams_dir，支持 TCP、UDP 和内建 SOCKS5。独立监听使用 port（默认 listen: true）；挂载共享 443 使用 listen: false、entrypoints: [websecure] 与 hostnames，并省略 port。Forward 绑定的内部 Stream 使用 listen: false，不配置 entrypoints/hostnames/Stream TLS。三种入口模式不能混用。

upstream 是静态地址（TCP 支持 unix:///绝对路径）；service_name 配合 upstream_type 使用发现源，不能同时填静态上游。proxy 是 upstream 别名；统一 site 写法见 L4 指南。idle_timeout 默认 60 秒；UDP max_sessions 默认 10000。

lb_policy 支持 round_robin（默认）、ip_hash、weighted/weighted_round_robin、least_conn、p2c 与插件，不支持 cookie。静态后端按策略选；混合发现列表先按 backend 权重选服务，再在服务内选实例。UDP 在会话创建时选目标并复用；P2C 的延迟是建立连接/首响应，不是业务请求耗时。

## SOCKS5 与 Forward

SOCKS5 allowed_destinations 必填，denied_destinations 优先。规则匹配解析后的 IP，public/private/any、IP/CIDR 与端口范围控制去向。回环、链路本地、元数据和未指定地址有内置拒绝保护，需要更精确显式前缀才能例外放行。public 排除保留/私有范围；private 包括 RFC1918 与 IPv6 ULA。

Forward Site 可以引用 stream，或使用 target/socks5 内联生成 forward:<domain> 内部 Stream，三者互斥。token_file 提供隧道授权，限制 max_sessions 和 idle_timeout。客户端不带 --target 提供透明隧道；--target 自动完成 SOCKS5 CONNECT，因此服务端必须为 SOCKS5 Stream。

客户端支持 --config 的 version: 1 文件。相对 token_file 相对配置目录；显式 CLI 参数覆盖对应字段。remote 与 remotes 互斥；多 mapping 与顶层 local/target 互斥；name/local 必须唯一，enabled 默认 true。绑定全部端口成功才启动，任一失败整体清理。非回环监听需 allow_lan_listen: true；多 mapping 已实现，配置热加载仍未提供。

## Forward v3 与故障切换

transport 为 auto（默认）、v3、v2。v3 对每个 Cloud 建立 TLS 长连接，用 litegate-forward.v3 Upgrade 鉴权，HTTP/2 CONNECT 承载本地连接、PING 保活。auto 遇旧服务端、代理环境或不支持 Upgrade 的入口可退回 WebSocket v2，十分钟后再试 v3；明确容量/目标拒绝不触发协议退回。

remotes 初次顺序尝试，后续优先最近成功节点；传输失败或容量拒绝可切换，SOCKS5 策略拒绝/目标连接拒绝不换 Cloud。服务端新流重新校验 token、站点和入口，撤销后拒绝新流，已有流持续到结束。每 IP 默认 32 个、每 Site 默认 256 个 v3 会话，超限返回 429。

## TLS、ACL、标签与观测

TCP TLS 使用 tls.enabled，手工 cert_file/key_file 成对，或 auto_cert 与 domains；共享入口可复用 hostnames 和已存在证书，min_version 为 1.2/1.3。独立监听不能抢占已用 HTTP/HTTPS 端口，共享 443 则按上面的挂载模式；不必改 https_port。数据库原生 STARTTLS 与原始 TLS 包装不同，需匹配客户端协议。

stream_ip_restriction 是全局 ACL，Stream 的 ip_restriction 可单独设置。独立 SOCKS5 无协议认证且监听所有网卡，应限制来源和目标。UDP/QUIC 的 PROXY v2 头拼在数据报前，默认只首包；proxy_protocol_udp_each_packet 可改每包，后端必须识别并剥离，注意 MTU。

发现标签须显式声明 TCP/UDP 端口，列入 service_discovery.tag_entrypoints.allowed_ports 并避免入口/静态 Stream 冲突；TLS 标签同组匹配，不支持 UDP TLS 卸载，无效 TCP TLS 配置不降级明文。Dashboard/metrics 观察会话、字节、拒绝和超时。

```yaml
name: mysql-proxy
port: 3307
protocol: tcp
upstream: 192.168.1.100:3306
enabled: true
idle_timeout: 300
```

```yaml
site: forward.example.com
forward:
  token_file: /etc/litegate/secrets/forward.token
  max_sessions: 200
  idle_timeout: 600
  socks5:
    allowed_destinations:
      - 10.0.0.25/32:3306
      - 10.0.0.26/32:6379
```

```yaml
version: 1
remotes:
  - https://forward-primary.example.com
  - https://forward-backup.example.com
token_file: ./forward.token
transport: auto
mappings:
  - name: mysql
    local: 127.0.0.1:13306
    target: 10.0.0.25:3306
  - name: redis
    local: 127.0.0.1:16379
    target: 10.0.0.26:6379
```

```bash
litegate forward --config ./forward.yaml
```

```yaml
name: database
listen: false
entrypoints: [websecure]
hostnames: [db.example.com]
protocol: tcp
upstream: unix:///run/litegate/database.sock
enabled: true
tls:
  enabled: true
  auto_cert: true
  min_version: '1.2'
```

## 相关文档与代码

- [L4 reference](l4-guide.md)
- [Entrypoints](entrypoints.md)
- [Shared 443](../09-advanced/shared-443-l4-stream.md)
- [Client implementation](../../../../pkg/litegate/forward_cmd.go)
- [Transport](../../../../internal/forward)
