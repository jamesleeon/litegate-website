# LiteGate 数据库安全访问方案

MySQL、PostgreSQL 等数据库协议通常不能直接靠 SNI 与 HTTPS 共用 443。以 MySQL 为例，客户端先等待服务端握手包，之后才可能用 SSLRequest 升级连接；连接首包不是带 SNI 的 TLS ClientHello。因此把 `db.example.com:443` 直接配置成 SNI Stream，绝大多数数据库客户端都会失败。

LiteGate 为此提供两种互补模式：

- 有固定可信来源 IP：使用独立端口的 L4 Stream，并配置 IP 白名单。
- 只能开放 443 或来源 IP 不固定：使用 `litegate forward`，在 HTTPS（默认 Forward v3 的 HTTP/2 流，必要时回退 WSS）内承载原始数据库字节流。

## Forward 的数据路径

```text
Navicat / DBeaver
        │  MySQL（默认明文，也可以启用 MySQL 自身 SSL）
        ▼
本地或局域网地址:3306
        │
litegate forward 客户端
        │  TLS 1.2+，复用 LiteGate 的 443 和现有证书
        ▼
LiteGate Forward 端点
        │  默认普通 TCP，或 Unix socket
        ▼
内网 MySQL / RDS
```

公网一段始终由 TLS 加密。LiteGate 到内网数据库默认是普通 TCP，这使 MySQL 无需证书配置，也是内网最易落地的方式。如果在 Navicat 中启用 MySQL SSL，MySQL 的 SSLRequest 和加密数据会原样穿过 Forward 隧道，LiteGate 不终止也不解析数据库 TLS。

> Forward Stream 不能同时启用 `tls.enabled`。Stream TLS 要求连接一开始就是 Raw TLS，与 MySQL/PostgreSQL 的协议内 TLS 升级不兼容。

## 服务端配置

Forward 是站点能力，不需要修改 `config.yaml`。创建域名对应的站点文件；域名必须由
`websecure` 的现有证书覆盖。例如已有 `*.example.com` 泛域名证书时，可以直接使用
`forward.example.com`，不会为 Forward 再申请一张证书。

```yaml
# sites/forward.example.com.yaml
domain: forward.example.com
forward:
  stream: rds-mysql
  token_file: /etc/litegate/secrets/forward.token
```

这里无需显式配置 `entrypoints`。没有全局 `entrypoints` 段时，LiteGate 仍会根据 `http.https_port`（默认 443）自动提供 `websecure`；Forward 本身只接受 TLS。仅在部署了多个入口并需要限制暴露范围时，才添加 `entrypoints: [websecure]`。

Token 至少 32 字节。推荐由 LiteGate 直接生成并以安全权限保存：

```bash
sudo litegate forward token --output /etc/litegate/secrets/forward.token
```

然后创建一个只供 Forward 使用的 Stream：

```yaml
# streams/rds-mysql-forward.yaml
name: rds-mysql
listen: false
protocol: tcp
upstream: 172.16.0.25:3306
enabled: true

max_sessions: 100
idle_timeout: 7200
ip_restriction:
  allow_ips:
    - 203.0.113.0/24
```

`upstream` 也可以是 `unix:///run/mysqld/mysqld.sock`，或者改用 `service_name` 和服务发现。Forward 会进入完整的 Stream 数据面，因此负载均衡、服务发现、IP 限制、会话上限、超时和指标仍然生效。`forward.example.com.yaml` 已经把该域名唯一绑定到 `rds-mysql`；客户端不能选择其他 Stream 或传入任意目标地址。

## 客户端使用

把服务端的 token 安全复制到运行客户端的机器，然后执行：

```bash
litegate forward \
  --remote https://forward.example.com \
  --local 127.0.0.1:3306 \
  --token-file ./forward.token
```

Navicat 中填写：

```text
主机：127.0.0.1
端口：3306
用户名/密码：数据库原有凭据
```

也可以通过环境变量传递 Token，避免把秘密放在命令行和进程列表中：

```bash
export LITEGATE_FORWARD_TOKEN='至少 32 字节的随机值'
litegate forward --remote https://forward.example.com --local 127.0.0.1:3306
```

### 在常开虚拟机上提供局域网入口

默认地址是 loopback。若要让局域网内其他电脑的 Navicat 连接一台常开虚拟机，直接明确填写该虚拟机的局域网 IP：

```bash
litegate forward \
  --remote https://forward.example.com \
  --local 192.168.50.20:3306 \
  --token-file ./forward.token
```

这时 Navicat 连接 `192.168.50.20:3306`。LiteGate 会打印局域网暴露警告；务必用虚拟机防火墙把 3306 限制到可信局域网网段。不要使用 `0.0.0.0:3306`，除非确实需要监听全部网卡并已配置防火墙。

## TLS 边界

| 链路 | 默认行为 | 可选增强 |
| :--- | :--- | :--- |
| Forward 客户端 → LiteGate 443 | 强制 TLS 1.2+ | 使用受信任 CA、轮换 Token |
| LiteGate → 内网 MySQL | 明文 TCP | 在 Navicat 启用 MySQL SSL，端到端原样穿透 |
| LiteGate → Unix socket | 本机 Unix 字节流 | 通过 socket 属组和 `0660` 权限控制 |

Forward 不接受 `http://` 或 `ws://`，也不会提供跳过证书校验的客户端参数。公网传输不会降级为明文。

Forward v3 用 HTTP/2 PING 检测会话存活（空闲 30 秒探测、15 秒超时），PING 由协议栈应答，
本地应用暂停读取时健康连接不会被误判断开；回退到 v2 时每 20 秒发送 WebSocket Ping，避免空闲
隧道被 LB、CDN 或 NAT 静默回收。上游主动关闭时会立即结束对应隧道，
不会等待 `idle_timeout` 才通知本地数据库客户端。`idle_timeout` 仍控制数据库业务流的
空闲期限；连接池需要长期保留连接时应按数据库的 `wait_timeout` 合理调大。

CLI 客户端和 LiteGate 服务端都会发送心跳，因此任一方向长时间没有 SQL 流量也能维持
连接活性。心跳只能避免“空闲超时”；如果云负载均衡配置了连接的绝对最长存活时间，
到期后仍会断开，应在 SLB/CDN 上调整该限制或让数据库客户端具备重连能力。

### Token 文件轮换

`token_file` 在 Site 加载时读取并保存到不可序列化的运行时字段。仅替换外部 secret 文件
不会触发 `sites/` Watcher。轮换后需要触发该 Site 重载，例如：

```bash
sudo litegate forward token --output /etc/litegate/secrets/forward.token.new
mv /etc/litegate/secrets/forward.token.new /etc/litegate/secrets/forward.token
touch /etc/litegate/sites/forward.example.com.yaml
```

推荐先原子替换 Token，再触发 Site 重载。如果新 Token 文件不可读、为空或不足 32 字节，
新配置会被拒绝，不应把不完整的 secret 直接覆盖到正在使用的文件。客户端必须同步换用新
Token；现有已建立的隧道不会因 Token 轮换而被强制断开。v2 只在新建隧道时校验 Token；v3 在
每个新连接上都重新校验，旧会话上的新连接会收到 403，客户端随即用当前 Token 重新握手。

### 前置代理与真实客户端 IP

Forward 会把 Router 已解析出的真实客户端 IP 写入隧道连接的 `RemoteAddr()`，因此
Stream 的 `ip_restriction` 可以继续针对公网客户端生效。前面存在 SLB、WAF 或 CDN 时，
必须只信任实际代理节点：

```yaml
real_ip:
  trusted_proxies:
    - 10.0.1.10/32       # 内部 SLB 地址
    - 10.0.2.0/24        # 受控代理节点网段
```

不要把 `trusted_proxies` 配成 `0.0.0.0/0`。LiteGate 只应接受受信连接器提供的
`X-Forwarded-For`；否则外部调用者可以伪造客户端 IP。未正确配置时，Stream ACL 通常看到
的是 SLB/CDN 节点地址并安全地拒绝请求，但也会导致合法用户无法连接。

## 什么时候仍使用独立 Stream

办公室出口 IP 固定且允许开放独立端口时，直接 L4 Stream 更简单、开销也最低：

```yaml
name: mysql-office
port: 13306
protocol: tcp
upstream: 172.16.0.25:3306
enabled: true
ip_restriction:
  allow_ips: ["203.0.113.10/32"]
```

不要把 MySQL 的普通连接直接指向共享 443 的 SNI Stream。共享 443 的 Raw TLS/SNI 模式适合连接首包就是 ClientHello 的协议，例如 `rediss://`、gRPC、自带 Direct TLS 的 TCP 服务；数据库工具的通用访问优先使用 Forward。

## 当前安全边界

- Forward 使用全局静态 Bearer Token；适合小团队和受控运维环境。需要人员级身份、短期凭证和详细审计时，应在后续版本接入身份提供方或使用专业堡垒机。
- 默认的 v3 在一条 TLS 长连接上为每个本地数据库连接开一个独立流（v2 为每个连接一条 WSS 隧道）；单个连接中断后数据库会话不会自动恢复，由数据库客户端重新连接。
- `ip_restriction` 依据 LiteGate 解析出的真实客户端 IP 生效；前置负载均衡时应正确配置 `real_ip.trusted_proxies`。
