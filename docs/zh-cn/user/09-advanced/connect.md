# LiteGate Connect 配置与上线指南

LiteGate Connect 用一条由 Home 主动拨向 Cloud 的 TLS 隧道，把 Home 上的 HTTPS Site 和可选的
L4 TCP Stream 发布到公网。Home 不需要开放入站端口；业务域名和 Connect 控制域名的 DNS 都指向
Cloud。

Connect 与 Forward 的区别、如何选择和组合见 [Forward 与 Connect 总览](forward-and-connect.md)。

本文是运维配置指南。协议、所有权和安全设计见
[LiteGate Connect 设计文档](https://github.com/jamesleeon/LiteGate/blob/master/docs/zh-cn/litegate-connect-design.md)；如何选择模式、如何用 Connect 落地私有化数据通道，
见 [Connect 场景与架构指南](connect-scenarios.md)。

## 1. 上线前准备

- Cloud 的 `web`（通常 `:80`）和 `websecure`（通常 `:443`）入口已经工作；
- `connect.example.com` 和待发布业务域名均解析到 Cloud；
- Cloud 能为 `connect.example.com` 完成正常 TLS 终止；
- Home 能主动访问 Cloud TCP/443；
- Home 的业务 Site 已绑定 `websecure`，且证书已就绪；
- 准备至少 32 字节的随机 Token，并以 `0600` 权限保存在两端。

推荐由 LiteGate 直接生成并以安全权限（自动创建 `0700` 目录、文件设为 `0600`、防止意外覆盖）保存：

```bash
sudo litegate connect token --output /etc/litegate/secrets/home-connect.token
```

也可以使用 LiteGate 的密钥生成命令直接在控制台输出随机密钥：

```bash
litegate -gen-secret
```

不要把 Token 直接写进 YAML 或提交到 Git。

## 2. Cloud 配置

在 Cloud 的主配置中启用 Connect Server：

```yaml
connect:
  server:
    enabled: true
    hostname: connect.example.com
    path: /_litegate/connect/v1
    state_file: data/connect-registry.json

    # 可选：控制域名之外仍禁止 Peer 注册的域名。
    reserved_domains:
      - admin.example.com

    peers:
      home:
        token_file: /etc/litegate/secrets/home-connect.token
        allowed_domains:
          - "*.home.example.com"
          - camera.example.com
        max_sites: 200
        max_connections: 4096
        sessions: 2
        max_registrations_per_minute: 30
```

`hostname` 必须是精确域名，不能是 IP 或通配域名。它会自动加入保留域名，任何 Home 都不能注册
该名称。`allowed_domains` 是授权边界，不是路由配置：Home 只能发布其中允许的精确域名或通配
pattern，Cloud 仍会检查本地 Site、保留名称和其他 Peer 的所有权冲突。

`state_file` 保存最后一版已验证所有权，不保存 Token 或活动 Session。文件损坏、版本不兼容或
因策略收紧导致个别 Peer 不再合法时，Cloud 会跳过不可用条目并继续启动；受影响的 Home 重连后
会重新注册。

默认值：

| 字段 | 默认值 | 含义 |
| --- | ---: | --- |
| `path` | `/_litegate/connect/v1` | TLS Upgrade 端点；可配置为任意绝对路径，Cloud 与 Home 必须保持一致 |
| `state_file` | `data/connect-registry.json` | Cloud 所有权缓存 |
| `max_sites` | `200` | Peer 最多发布的 Site 数 |
| `max_connections` | `4096` | Peer 全局活动数据流上限 |
| `sessions` | `2` | 同一 Peer 允许的物理 Session 数 |
| `max_registrations_per_minute` | `30` | 新 generation 注册速率上限 |

## 3. Home 配置

Home 使用相同的 Peer 名称和 Token 主动连接 Cloud：

```yaml
connect:
  client:
    enabled: true
    name: home
    remote: https://connect.example.com/_litegate/connect/v1
    token_file: /etc/litegate/secrets/home-connect.token
    publish_sites: true
    publish_streams: false
    sessions: 2
    max_connections: 4096
    registration_debounce: 500ms
    exclude_domains:
      - connect.example.com
      - admin.example.com
```

`publish_sites` 发布 Home Loader 中暴露在 `websecure` 的 Site。证书或 Home websecure 尚未就绪时，
域名以 `pending_certificate` 注册并在 Cloud fail-closed，不会回落到 Cloud 的泛域名站点。

`exclude_domains` 用于排除只应留在 Home 本机或控制面的域名。它不能扩大 Cloud
`allowed_domains` 的授权范围。

### 3.1 用 CLI 快速发布 HTTP 服务

完整的 Cloud、DNS、证书、Dashboard 和排障步骤见[使用 CLI 发布内网 HTTP 服务](connect-cli-http.md)。

少量 HTTP 服务无需启动 Home LiteGate 的 `web`、`websecure` 或配置 Site，可以直接运行：

```bash
litegate connect http \
  --remote https://connect.example.com \
  --name home \
  --token-file /etc/litegate/secrets/home-connect.token \
  --domain audit.home.example.com \
  --upstream http://192.168.50.247:8090
```

Cloud 终止公网 TLS，再以单个 HTTP 请求为单位通过 Connect 转发。普通请求、上传、下载、长轮询和
SSE 均支持流式传输；WebSocket 和其他 HTTP Upgrade 当前不支持，请继续使用完整的 Connect Site。
除 Connect 控制端点和 ACME challenge 外，发布服务拥有完整路径空间，包括 `/healthz`、
`/readyz` 和 `/_litegate/*`。

Cloud 必须能为 `--domain` 提供证书：可以预装精确/泛域名证书，也可以设置
`auto_cert.on_demand.enabled: true` 启用自动签发；仅完成 Connect 注册不会自动开启按需 TLS。
开启后，通过认证且满足 Peer `allowed_domains` 的活动 Connect HTTP 注册会把已注册的精确域名
加入受限流保护的按需签发授权，并在注册 ACK 后异步预签发缺少的证书。HTTP 注册不接受通配 hostname，
未注册域名也不会获得签发权限；已有精确、SAN 或泛域名证书时不会重复申请。

默认保留公网 Host（等价于 `--host-header preserve`），例如 upstream 会收到 `Host: audit.home.example.com`。需要按内部虚拟主机选路时
可使用 `--host-header upstream`，或传入明确值（例如 `--host-header audit.internal`）。CLI 会删除
客户端提供的 `Forwarded`、`X-Forwarded-*` 和 `X-Real-IP`，再根据 Cloud 的
`trusted_proxies` 结果生成可信客户端地址。

Token 不接受明文 `--token` 参数，以免出现在 shell 历史和进程列表中；除 `--token-file` 外，也可
使用 `LITEGATE_CONNECT_TOKEN`。`LITEGATE_CONNECT_REMOTE`、`LITEGATE_CONNECT_NAME` 和
`LITEGATE_CONNECT_TOKEN_FILE` 可用于省略重复参数。

## 4. Home Site 示例

```yaml
domain: camera.home.example.com
entrypoints:
  - websecure
tls:
  enabled: true
  cert_file: /etc/litegate/certs/home-wildcard.crt
  key_file: /etc/litegate/certs/home-wildcard.key
routes:
  - name: camera
    match:
      path_prefix: /
    action:
      type: proxy
      upstream:
        - http://192.168.1.50:8080
```

客户端 TLS 最终在 Home / Private 终止，因此私钥与证书必须由本地持有（Cloud 仅做 4 层 SNI 盲转发）。
为保障多租户隔离与私钥绝对安全，LiteGate 严禁向客户端下发泛域名证书与私钥，推荐在 Home 端配置 `auto_cert` 启用 `type: connect` 的委托签发模式：
- **私钥本地生成**：私钥在本地生成并支持 AES-GCM 本地落盘加密，绝不出网；
- **DNS-01 集中代办**：由掌控 DNS 凭据的 Cloud 代理完成 ACME 验证；
- **无感签发与热续期**：公钥证书自动下发并热加载，杜绝租户越权。

详细配置与安全原则详见 [Connect 证书委托签发与端到端私钥安全管理](../06-certificates/connect-csr-delegation.md)。

已登记的 Connect Host 通过 Cloud TCP/80 访问时会返回 308 到相同规范化 Host 和 URI 的 HTTPS
地址，包括 `pending_certificate` 和 `offline` 状态。未知 Host 不会被重定向，避免 Host Header
开放重定向。

## 5. 多 Cloud 与 mTLS

多 Cloud 节点使用 `remotes`；`sessions` 必须不少于远端数量：

```yaml
connect:
  client:
    enabled: true
    name: home
    remotes:
      - https://connect-a.example.com/_litegate/connect/v1
      - https://connect-b.example.com/_litegate/connect/v1
    sessions: 4
    token_file: /etc/litegate/secrets/home-connect.token
    publish_sites: true
```

可选 mTLS：Cloud 设置 `connect.server.client_ca_file`，Home 同时设置
`connect.client.cert_file` 和 `connect.client.key_file`。客户端证书的 DNS 或 URI SAN 必须绑定 Peer
名称；mTLS 是 Token 认证之外的第二层身份校验。

## 6. 发布 L4 TCP / SOCKS5 Stream

Home 开启 `publish_streams`，并只对需要发布的 Stream 设置 `connect_publish`。普通 TCP
Stream 使用 `true` 时既能从公网按 SNI 直连，也能被 Forward 分发：

```yaml
name: home-git-ssh
protocol: tcp
enabled: true
listen: false
connect_publish: true
hostnames:
  - git-ssh.home.example.com
upstream: 192.168.1.60:22
idle_timeout: 300
```

只打算给 Forward 使用时，设置 `connect_publish: forward_only`。Cloud 会保留该域名的
Connect 路由供 Forward 查找，但拒绝不带 Forward token 的公网 SNI 直连。

SOCKS5 Stream 也可以发布。为兼容旧配置，布尔值 `connect_publish: true` 会记录提示日志并
自动收紧为 `forward_only`；显式写 `connect_publish: public` 会校验失败，避免误以为 SOCKS5
可以安全地通过公网 SNI 直接发布：

```yaml
name: home-socks
protocol: socks5
enabled: true
listen: false
connect_publish: forward_only
hostnames: [access.home.example.com]
idle_timeout: 600
socks5:
  allowed_destinations:
    - private:22,80,443,3389
```

Cloud 只需一个使用 `target.type: connect` 的 Forward Site：

```yaml
domain: forward.example.com
forward:
  target:
    type: connect
    name: access.home.example.com
  token_file: /etc/litegate/secrets/home-forward.token
  max_sessions: 200
  idle_timeout: 600
```

以后新增家庭服务只需调整 Home 白名单和客户端 mapping，无需修改 Cloud。Connect 当前发布
TCP 和 SOCKS5 Stream；原生 QUIC/UDP 数据面尚未实现。

## 7. 从 Cloud Site 零中断迁移

在现有 Cloud Site 上添加指定 Peer 的迁移授权：

```yaml
domain: camera.example.com
connect_override: home
routes:
  - name: old-cloud-upstream
    match:
      path_prefix: /
    action:
      type: proxy
      upstream:
        - http://127.0.0.1:8080
```

`connect_override` 只能用于精确域名，值必须是 Cloud 已配置的 Peer 名称。配置授权本身不会立即
切流：在 `home` 成功注册同名精确域名后，新连接才原子切换到 Connect。接管后即使 Home 离线也
保持 fail-closed，不会自动回落旧 Cloud upstream。回滚时先让 Home 撤销发布，再移除
`connect_override`。

## 8. Token 轮换

Cloud Token 文件允许每个非空行一个 Token。零中断轮换顺序：

1. Cloud 文件写入“新 Token”第一行、“旧 Token”第二行；
2. Home 文件只写新 Token；
3. 等待所有 Home Session 使用新 Token 重连；
4. 从 Cloud 文件删除旧 Token。

已有 Session 不会因 Token 文件变化被强制断开；新握手使用最新有效凭据快照。

## 9. 验证与排障

推荐分阶段上线：

1. 只启用 Cloud，确认原有 443 Site 和 Stream 不受影响；
2. 启用 Home，但先用测试域名；
3. 检查 Dashboard 中 Peer、Session、generation 和域名状态；
4. 对完整 Site 测试 WebSocket/SSE；对 CLI HTTP 模式测试 HTTP 308、HTTPS、SSE、大文件上传下载及断网恢复；
5. 稳定运行一晚后，再用 `connect_override` 逐个迁移。

重点指标：

- `litegate_connect_sessions`
- `litegate_connect_domains{state="ready|pending|offline|conflict"}`
- `litegate_connect_active_connections`
- `litegate_connect_connections_total`
- `litegate_connect_registrations_total`
- `litegate_connect_authentication_total`
- `litegate_sni_connect_dispatch_queue_depth`

常见状态：

| 状态 | 含义与处理 |
| --- | --- |
| `pending_certificate` | Home websecure 或证书未就绪；检查证书文件、自动签发和 Site entrypoint |
| `offline` | 所有物理 Session 已断开；检查 Cloud 地址、DNS、Token、TLS 和出口防火墙 |
| `conflict` | 同精度 Cloud 本地 pattern 占用；移除冲突或显式配置正确的 `connect_override` |
| 注册被拒绝 | 检查 `allowed_domains`、保留域名、跨 Peer 重名和注册速率限制 |
