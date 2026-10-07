# LiteGate 双 Forward 辨析：`Forward` (资产映射隧道) 与 `Forward Proxy` (正向代理)

LiteGate 中有两个名字带有 “Forward” 的网络能力：
1. **`Forward`**（内置能力 / `site.forward` / `litegate forward` CLI）
2. **`Forward Proxy`**（入口插件 / `pkg/plugins/forwardproxy`）

许多开发者和运维初次接触时容易混淆，甚至误以为它们是同一个功能的两种叫法。**实际上，这是两个应用场景、网络拓扑、客户端要求和安全模型完全不同的独立机制。**

本文深入对比两者的本质区别、典型场景与配置范式，帮助你在架构选型时做出正确的决策。

---

## 一、一句话定位与架构走向

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 场景 1：LiteGate Forward（私有资产映射隧道）                                          │
│ 定位："我去安全使用云端/内网的私有孤岛资产"（如云 RDS 数据库、Redis、内部 RPC）        │
│                                                                                        │
│ 本地工具 (Navicat) ──TCP──▶ litegate forward CLI ══TLS 443 (Token)══▶ 云端 LiteGate    │
│ (127.0.0.1:3306)            (专属客户端, 主动拨出)                  │ (绑死单一Stream) │
│                                                                     ▼                  │
│                                                                云内网 RDS MySQL 3306   │
└────────────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 场景 2：Forward Proxy（通用 HTTP/HTTPS 正向代理插件）                                 │
│ 定位："我把 LiteGate 当作出网跳板，去访问外部互联网或任意授权网站"                     │
│                                                                                        │
│ 任意终端 (浏览器/curl) ──HTTP CONNECT (Bcrypt)──▶ LiteGate ──TCP/TLS──▶ 外部互联网 API │
│ (无需安装 LiteGate, 设代理即可)                     (Ingress 插件)    (github.com, 微信等)│
└────────────────────────────────────────────────────────────────────────────────────────┘
```

- **`Forward`** 是 **端到点（Point-to-Point）的私有隧道**：客户端必须运行 `litegate forward` 命令行工具，且**目标被服务端死死锁死在特定的私有 Stream 上**（比如只能访问指定的那台内网数据库，客户端无权请求任意其他地址）。
- **`Forward Proxy`** 是 **点到面（Point-to-Any）的通用跳板**：客户端就是普通的浏览器、curl 或企业爬虫，使用标准的 HTTP `CONNECT` 协议，**目标由客户端动态指定**（如访问 `github.com`、`api.openai.com`），由服务端 ACL 白名单控制可访问范围。

---

## 二、全方位核心对比矩阵

| 对比维度 | LiteGate Forward (资产映射隧道) | Forward Proxy (通用正向代理插件) |
| :--- | :--- | :--- |
| **功能定位** | **内网私有资产穿透堡垒**<br>把云端隔离环境里的数据库/TCP服务安全映射到本地 | **出网代理与网络跳板**<br>让局域网客户端或爬虫以 LiteGate 为出口访问公网或第三方服务 |
| **客户端要求** | ⚠️ **必须运行 `litegate` 客户端**<br>运行 `litegate forward` 守护进程监听本地端口 | ✅ **零客户端安装**<br>任意标准浏览器、curl、开发框架只要设置 `HTTP_PROXY` 即可 |
| **访问目标控制** | 🔒 **服务端强制绑定（强受限）**<br>服务端配置文件直接绑定到指定 Stream（如 `10.0.0.25:3306`），客户端根本没有指定目的地的参数，杜绝被当作跳板渗透 | 🌐 **客户端自主声明（ACL 防护）**<br>客户端在请求中指定目标（如 `CONNECT target.com:443`），由服务端 `allowed_destinations` 做白名单过滤 |
| **通信与协议层** | **L4-over-L7 私有长连接**<br>在公网 443 HTTPS 握手后升级为专用二进制长连接通道，双向保活 | **L7 标准 HTTP 代理协议**<br>解析标准 HTTP/1.1、HTTP/2、HTTP/3 的 `CONNECT` 隧道与绝对 URL 请求 |
| **认证方式** | 🔑 **预共享强 Token 文件**<br>使用 `litegate forward token` 离线生成的专属鉴权文件（0600 权限），无 Token 无法建立链路 | 👤 **标准 HTTP Basic 认证**<br>通过 `Proxy-Authorization` 头传递账密，服务端采用抗时序攻击的 Bcrypt 哈希校验 |
| **配置承载位置** | `sites/*.yaml` 中的 `forward:` 块 + `streams/*.yaml` | `config.yaml` 全局的 `ingress_plugins` 数组 |
| **防探测机制 (Anti-Probe)** | 非法请求或未携带 Token 的握手直接掐断或返回 404/自定义伪装响应 | `probe_resistance: true`：未通过认证的请求**绝不返回 407**（避免暴露自己是代理），直接穿透回底层的普通静态站点 |
| **是否建议开 ECH** | ❌ **不适用**（客户端是专用 CLI） | ❌ **坚决不要开启**（见前文：会导致防火墙阻断、客户端无法协商连入） |

---

## 三、场景深度剖析与配置对照

### 场景 1：研发团队安全直连云端内网数据库（使用 `Forward`）

#### 为什么必须选 `Forward`？
企业的云 RDS 数据库（MySQL/PostgreSQL/Redis）通常只开在 VPC 私网内，严禁将 3306 端口暴露到公网。
- 如果使用传统的 SSH 隧道，需要给每个人分配云服务器的 Linux 账号，权限太大；
- 如果使用通用正向代理（Forward Proxy），一旦密码泄露，黑客可以直接用该代理作为跳板扫描整个云 VPC 内网！
- **LiteGate `Forward` 完美解决了这个问题**：它是一个**目标绑死**的隧道，客户端即便拿到 Token，也**只能连接这一台指定的数据库**，无法触碰内网其他任何机器。

#### 配置实战：

**1. 服务端配置**
```yaml
# streams/rds-mysql.yaml
name: rds-mysql
protocol: tcp
enabled: true
listen: false                  # 不对外开端口，纯由 Forward 引用
upstream: 10.0.0.25:3306       # 云内网私有 RDS 地址
idle_timeout: 600
```

```yaml
# sites/db-tunnel.example.com.yaml
domain: db-tunnel.example.com
forward:
  stream: rds-mysql            # 严格锁死目标！客户端不可更改！
  token_file: /etc/litegate/secrets/rds.token
```

```bash
# 服务端生成并分发安全 Token
litegate forward token --output /etc/litegate/secrets/rds.token
```

**2. 客户端使用**
开发者本地只需执行：
```bash
litegate forward \
  --remote https://db-tunnel.example.com \
  --local 127.0.0.1:3306 \
  --token-file ./rds.token
```
本地数据库工具（Navicat / DBeaver）直接连接 `127.0.0.1:3306` 即可，体验如同数据库部署在本机。

---

### 场景 2：内网无公网 IP 服务器/爬虫统一出网（使用 `Forward Proxy`）

#### 为什么必须选 `Forward Proxy`？
在私有化机房或金融隔离区中，大量业务服务器没有公网 IP，但它们需要：
- 调用微信支付/支付宝的公网 API；
- 访问公网 SaaS（如 GitHub、第三方短信服务、AI 大模型 API）；
- 定时抓取多个公网网站的数据。

因为目标网站是**成千上万个不固定的域名**，你不可能去写几千个 `stream.yaml` 做固定端口映射。此时需要的是**标准的 HTTP/HTTPS 正向出网代理**。

#### 配置实战：

在公网边界的 LiteGate 机器上配置 `config.yaml`：

```yaml
# config.yaml
entrypoints:
  websecure:
    address: ":443"

ingress_plugins:
  - name: my-forward-proxy
    type: forward_proxy            # 启用正向代理插件
    entrypoints: [websecure]       # 挂载在 443 端口上
    config:
      hosts: [proxy.example.com]   # 仅在此域名匹配时触发
      username: crawler_ops
      password_env: LITEGATE_PROXY_PASSWORD # 环境变量中存放代理密码
      probe_resistance: true       # 开启防探测保护
      allowed_ports: [80, 443]     # 限制只能代理 Web 流量
      allowed_destinations:        # 目标白名单
        - "*.github.com"
        - "*.wechat.com"
        - "api.openai.com"
```

#### 客户端使用：
内网机器完全不需要安装 LiteGate，直接使用标准环境变量：
```bash
export https_proxy="https://crawler_ops:YourPassword@proxy.example.com:443"

# curl 或 Python 爬虫直接畅通无阻访问公网
curl https://api.github.com/zen
```

---

## 四、常见误区与避坑指南

### 误区 1：我能用 `Forward Proxy` 代替 `Forward` 来连数据库吗？
**技术上可以（通过 HTTP CONNECT 443），但安全架构上极度危险！**
- 如果你允许客户端通过 `Forward Proxy` 自由连回内网的 3306，任何拿到代理账号的人，都可以把目标写成 `10.0.0.1:22`、`10.0.0.2:80`，把你的代理直接当成内网渗透跳板。
- 而 `Forward` 是在数据模型层把域名和目标 Stream 静态绑死的（Zero Trust 最小权限原则）。

### 误区 2：我能用 `Forward` 代替 `Forward Proxy` 来上网吗？
**不现实。**
- `Forward` 的设计目标是“基础设施资产映射”。要用它上网，你必须使用带 `mappings` 的 SOCKS5 Stream，并且客户端必须一直挂着 `litegate forward` 命令。对于普通浏览器和临时脚本而言，远不如直接配个 `HTTP_PROXY` 来得自然。

### 误区 3：Forward 与 Connect 又是什么关系？
- **Forward**：从外面访问里面（客户端向云端发起，把云端的私网资产拉到本地电脑）。
- **Connect**：从里面发布到外面（无公网 IP 的内网机器主动向云端建连，把自己的内网站点“发布”到公网上供所有人访问）。
- *详见 [Forward 与 Connect：内网穿透总览](user/09-advanced/forward-and-connect.md)*。

---

## 五、选型决策流程图

当你面临网络打通需求时，请按照以下流程决策：

```text
你需要打通网络连接
      │
      ▼
访问目标是固定的私有资产 (如云 RDS, Redis, 内部后台) 
还是外部互联网任意网站 (如公网 API, 爬虫目标, 查资料)？
      │
      ├─► [固定私网资产] ──► 客户端愿意/可以运行命令行工具吗？
      │                       │
      │                       ├─► [是] ──► 🌟 选择 LiteGate Forward
      │                       │           (Token 强鉴权, 锁死 Stream, 极致安全)
      │                       │
      │                       └─► [否] ──► 考虑 LiteGate Connect
      │                                   (把内网资产直接反向发布为带认证的 Web 站点)
      │
      └─► [动态/公网多目标] ──► 🌟 选择 Forward Proxy (正向代理插件)
                                 (标准 HTTP CONNECT, 零客户端安装, 配合 ACL 与防探测)
```
