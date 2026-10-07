# Forward 与 Connect：内网穿透总览

LiteGate 有两个"跨网络"能力：**Forward** 和 **Connect**。它们都只占用公网 443、都由内侧主动
向外建立 TLS 连接，但方向和用途完全不同。本文讲清两者的区别、如何选择、如何组合，以及它们
和 frp、Cloudflare Tunnel 等工具的边界。具体配置字段请看文末链接的专题文档，这里只给最小示例。

> [!NOTE]
> **概念辨析**：本文介绍的 **Forward** 是专用于将云端隔离资产（如 RDS 数据库）安全映射到本地端口的端到点加密隧道。
> 如果你需要的是让普通浏览器或爬虫通过 LiteGate 作为出网跳板访问互联网的标准 HTTP 正向代理，请参阅专门的辨析文档：[Forward (资产映射隧道) 与 Forward Proxy (正向代理) 的区别](../../forward-vs-forward-proxy.md)。

## 1. 一张图看清两个方向

```text
Forward：把"云里的服务"带到"我的电脑"
─────────────────────────────────────────────
Navicat ──TCP──▶ litegate forward ══TLS 443══▶ Cloud LiteGate ──TCP──▶ 云内网 RDS
（本机端口）      （客户端，主动拨出）            （Forward Site）

Connect：把"家里的服务"发布到"公网"
─────────────────────────────────────────────
浏览器 ──HTTPS──▶ Cloud LiteGate ◀══TLS 443══ Home LiteGate ──▶ 家里的 NAS / 内网系统
                  （按 SNI 转发）   （Home 主动拨出，       （在 Home 终止 TLS，
                                      反向承载流量）          走完整 Site 与中间件）
```

| | Forward | Connect |
| --- | --- | --- |
| 谁主动拨出 | 使用者电脑上的 `litegate forward` | Home 上的 LiteGate |
| 流量方向 | 使用者 → Cloud → Cloud 能访问的目标 | 公网访客 → Cloud → Home |
| 谁能访问 | 只有持有 Forward Token 的客户端 | 任何人（按 Site 自身的认证策略） |
| 典型对象 | 数据库、Redis、SSH 等 TCP 服务 | 网站、内网系统；也可发布 TCP Stream |
| 访问者需要安装什么 | `litegate` 客户端 | 什么都不用，浏览器即可 |

一句话：**Forward 是"我去用云里的东西"，Connect 是"让别人用我家里的东西"。**

## 2. 怎么选

| 你的需求 | 选择 | 专题文档 |
| --- | --- | --- |
| 家里/办公室没有公网 IP，想借一台 VPS 把 NAS、内网系统发布成公网 HTTPS | Connect | [Connect 配置与上线](connect.md) |
| 开发人员不开 VPN，从本机访问云上只有内网地址的 RDS、Redis | Forward | [云 RDS 安全代理到本地](../../rds-forward-guide.md) |
| 在外的同事访问放在 Home 的数据库、SSH 这类非 HTTP 服务 | Forward → Connect 组合 | 本文第 3.3 节 |
| 多个分支机构的内网系统统一从一个云入口发布 | Connect，每个分支一个 Peer | [Connect 配置与上线](connect.md) |
| 需要整网互通、访问任意内网 IP、跑 UDP | 都不合适，见第 6 节 | — |

## 3. 三种典型拓扑

### 3.1 Forward：本机访问云内网数据库

Cloud 上把一个 HTTPS 域名唯一绑定到一个 Stream，客户端**无法**自己指定连到哪台主机：

```yaml
# Cloud: streams/rds.yaml
name: rds
protocol: tcp
enabled: true
listen: false
upstream: 10.0.0.25:3306
idle_timeout: 600
```

```yaml
# Cloud: sites/forward.example.com.yaml
domain: forward.example.com
forward:
  stream: rds
  token_file: /etc/litegate/secrets/rds-forward.token
```

```bash
# Cloud：生成 Token（目录 0700、文件 0600，不会覆盖已有文件），再安全地交给使用者
litegate forward token --output /etc/litegate/secrets/rds-forward.token

# 使用者电脑
litegate forward --remote https://forward.example.com --local 127.0.0.1:3306 --token-file ./rds-forward.token
```

Navicat 连接 `127.0.0.1:3306` 即可。需要一个客户端访问多个目标时，把 Stream 换成带
`allowed_destinations` 白名单的 SOCKS5 Stream，并在客户端写多个 `mappings`，见
[Stream 配置](../03-configuration/stream-config.md)。

### 3.2 Connect：把 Home 的网站发布到公网

业务域名 DNS 指向 Cloud。Cloud 声明允许 Home 发布哪些域名，Home 声明要发布什么：

```yaml
# Cloud: config.yaml
connect:
  server:
    enabled: true
    hostname: connect.example.com
    peers:
      home:
        token_file: /etc/litegate/secrets/home-connect.token
        allowed_domains: ["*.home.example.com"]
        max_connections: 4096
```

```yaml
# Home: config.yaml
connect:
  client:
    enabled: true
    name: home
    remote: https://connect.example.com/_litegate/connect/v1
    token_file: /etc/litegate/secrets/home-connect.token
    publish_sites: true
    exclude_domains: [connect.example.com]
```

Home 上所有暴露在 `websecure` 的 Site 会自动注册。证书在 Home，TLS 在 Home 终止，Cloud 只看
SNI 转发、看不到明文。

### 3.3 Forward → Connect：在外访问 Home 的数据库

Home 发布一个只供 Forward 使用的 Stream，Cloud 用一个 `target.type: connect` 的 Forward Site
把它接出来：

```yaml
# Home: streams/home-mysql.yaml
name: home-mysql
protocol: tcp
enabled: true
listen: false
connect_publish: forward_only     # 公网不能按 SNI 直连，只能经 Forward
hostnames: [mysql.home.example.com]
upstream: 192.168.1.20:3306
```

```yaml
# Cloud: sites/home-db.example.com.yaml
domain: home-db.example.com
forward:
  target:
    type: connect
    name: mysql.home.example.com
  token_file: /etc/litegate/secrets/home-db-forward.token
```

```bash
litegate forward --remote https://home-db.example.com --local 127.0.0.1:3306 --token-file ./home-db-forward.token
```

数据路径：`Navicat → forward 客户端 ═443═▶ Cloud ═Connect═▶ Home → 192.168.1.20:3306`。
Home 仍不需要开放任何入站端口。Home 需要开启 `connect.client.publish_streams: true`。

## 4. 安全模型

| 边界 | 机制 |
| --- | --- |
| 谁能建隧道 | Forward：每个 Forward Site 一个 Token；Connect：每个 Peer 一个 Token，可叠加 mTLS 客户端证书。两者都用常量时间比较，Connect 在内存中只保留 Token 的 SHA-256 摘要 |
| 能去哪里 | Forward 的目标由服务端配置唯一决定，客户端不能选择主机或端口；SOCKS5 模式必须配置 `allowed_destinations`，且在解析后的 IP 上判定 |
| 能发布什么 | Connect Peer 只能注册 `allowed_domains` 内的域名；与 Cloud 本地 Site、保留域名、其他 Peer 冲突时拒绝（状态 `conflict`） |
| 离线时 | 域名保留归属，状态变为 `offline` 并直接拒绝连接，不会回落到 Cloud 的泛域名站点 |
| 明文可见性 | Connect 发布的 Site 在 Home 终止 TLS，Cloud 只转发加密字节；Forward 公网段由 TLS 加密，数据库原生 SSL 可原样穿透 |
| Token 轮换 | Connect 的 Token 文件每行一个 Token，可新旧并存实现零中断轮换。Forward 每个 Site 只有一个 Token：替换后已建立的连接不受影响，新连接需要客户端换上新 Token；v3 会话在轮换后对新连接返回 403，存量连接跑完后会话才关闭 |

## 5. 传输协议：Forward v3

Forward 客户端默认使用 **v3**（`transport: auto`）：

| | v2（WebSocket） | v3（HTTP/2 多路复用） |
| --- | --- | --- |
| 连接模型 | 每个本地连接一条独立 WSS | 每个 Cloud 一条长连接，每个本地连接是其中一个流 |
| 新建连接的开销 | TCP + TLS + WebSocket 握手（带 target 时还要 SOCKS5） | 一个 HTTP/2 HEADERS 帧（带 target 时再加 SOCKS5 往返） |
| 存活检测 | WebSocket Ping | HTTP/2 PING（30 秒空闲探测、15 秒超时），本地应用暂停读取不会被误判断开 |
| 流控 | 整条连接 | 每个流独立 |
| 被拒绝时 | 连接被关闭 | 返回明确状态码和原因 |
| 经过代理 | 大多数 L7 代理/CDN 支持 | 需要代理放行自定义 Upgrade |

Connect 在 Cloud 与 Home 之间一直是 HTTP/2 多路复用，v3 让 Forward 也采用了同一套传输实现。

**`auto` 的回退规则**：以下情况自动改用 v2，并在 10 分钟后重新尝试 v3。

- 服务端是尚未升级的旧版本；
- 设置了 `HTTPS_PROXY` 等代理环境变量；
- 前面的 SLB、WAF、CDN 不放行 v3 的 Upgrade（返回 400、403、502 等）。

服务端明确拒绝时**不回退**，而是直接报错：`429`（会话数超限）和 `503`（目标不可用）。需要
固定协议时使用 `--transport v2` 或 `--transport v3`。服务端无需任何配置，v2 与 v3 同时支持。

**会话上限**：每个客户端 IP 默认最多 32 个 v3 会话，每个站点最多 256 个。正常情况下一个客户端
对每个 Cloud 只保持一个会话，上限只用于防止持有合法 Token 的客户端堆积空闲会话。

**已知限制**：

- v3 的所有流共用一条 TCP 连接，网络丢包时会互相拖慢。单条连接长时间跑满带宽的大批量传输，
  可以用 `--transport v2` 让它独占连接。
- 方向性关闭：客户端可以只关闭发送方向并继续接收响应；服务端一侧先结束发送时，整个流随之结束
  （与 Connect 相同）。
- 只承载 TCP，不支持 UDP / QUIC。

## 6. 与其他工具的边界

多路复用、反向隧道本身都不是新技术。LiteGate 的差异在于**隧道和网关是同一个程序**：穿透进来
的流量直接进入完整的 Site、证书、WAF、认证、限流和访问日志链路。下表用于判断该选哪个工具，
而不是说谁更好。

| 工具 | 更适合 | 与 LiteGate 的主要区别 |
| --- | --- | --- |
| frp | 成熟的通用内网穿透，支持 UDP、KCP/QUIC 等多种传输 | frp 只转发字节，TLS 证书、WAF、认证需另行搭建；LiteGate 由 Home 网关持有证书并直接套用 Site 策略，Cloud 端还有域名归属与冲突管控 |
| Cloudflare Tunnel | 不想维护 VPS，需要全球边缘和 DDoS 防护 | Cloudflare 在其边缘终止 TLS；LiteGate Connect 在 Home 终止 TLS，Cloud 看不到明文，入口 VPS 由自己掌控 |
| SSH 端口转发（`-L` / `-R`） | 临时、一次性的访问 | SSH 客户端可自行选择转发目标，需要为使用者开系统账号；Forward 的目标由服务端绑定，Token 与账号体系分离 |
| Tailscale / WireGuard | 整网互通、访问任意内网 IP、UDP、点对点 | 每台访问设备都要安装客户端并加入网络；Connect 的访客只需浏览器，Forward 只暴露指定服务而不是整个网络 |

## 7. 排错

### Forward 客户端常见错误

| 现象 | 含义与处理 |
| --- | --- |
| 握手 `HTTP 404` | 最常见的是 Token 错误：为避免被探测，Token 错误、未使用 HTTPS 与路径不对都统一返回 404。其次检查域名是否确实配置了 `forward:` 且暴露在当前入口 |
| 握手 `HTTP 429` | 超过 v3 会话上限，检查是否有客户端在循环重建会话 |
| `HTTP 503 (target unavailable)` | 目标 Stream 不存在或未就绪；目标是 connect 时，检查 Home 是否在线 |
| `HTTP 503 (target has reached max_sessions)` | 目标 Stream 的 `max_sessions` 已满 |
| `HTTP 403` | 会话建立后 Token 被轮换、站点被删除或不再暴露在该入口；客户端会自动用新握手重新鉴权 |
| `server rejected destination` | SOCKS5 目的地不在 `allowed_destinations` 内，或目标拒绝连接；此类错误不会切换到其他 Cloud 重试 |

### Status 看板上的 Connect 面板

| 字段 | 含义 |
| --- | --- |
| ROLE | 本节点角色：Cloud（接受 Home 接入）或 Home（主动拨出） |
| TUNNEL HEALTH | Cloud 上是"在线 Peer 数 / 已配置 Peer 数"；Home 上是"已连接的上行会话数 / 配置的 `sessions`"。同时是 Cloud 和 Home 时两者都显示 |
| PUBLISHED HOSTNAMES | 已注册域名，分为 `ready`、`pending`（通常是 Home 证书未就绪）、`conflict`（与 Cloud 本地路由冲突） |
| ACTIVE DATA FLOWS | 当前反向数据流数量，上限为 Peer 的 `max_connections` |
| REVISION | `epoch` 在新的 Home 实例（例如 Home 进程重启）接入时递增，单纯断线重连不变；`generation` 随 Home 发布内容变化递增 |

Connect 各状态的详细处理见 [Connect 配置与上线](connect.md) 第 9 节。

## 8. 相关文档

- [LiteGate Connect 配置与上线](connect.md)：Cloud/Home 全部字段、多 Cloud、mTLS、迁移、Token 轮换
- [Stream 配置](../03-configuration/stream-config.md)：Forward Site、SOCKS5、客户端 `mappings` 与 `transport`
- [云 RDS 安全代理到本地](../../rds-forward-guide.md)：Forward 数据库场景的逐步教程
- [LiteGate Connect 设计文档](https://github.com/jamesleeon/LiteGate/blob/master/docs/zh-cn/litegate-connect-design.md)：协议与所有权模型（面向开发者）
