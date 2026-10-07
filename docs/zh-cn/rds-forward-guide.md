# 将云 RDS 数据库安全代理到本地

本文介绍如何通过 LiteGate Forward，把只能在云内网访问的 MySQL RDS 安全映射到开发者电脑或局域网常开虚拟机。Navicat、DBeaver、MySQL CLI 和应用程序仍然连接普通的本地 TCP 端口，不需要支持 WebSocket。

## 1. 数据路径

```text
Navicat / DBeaver / mysql
        │
        │ MySQL TCP
        ▼
127.0.0.1:3306 或局域网虚拟机:3306
        │
        │ litegate forward
        │ TLS 1.2+（默认 Forward v3：HTTP/2 多路复用；必要时自动回退 WSS）
        ▼
https://forward.example.com:443
        │
        │ LiteGate L4 Stream
        │ 云内网 TCP
        ▼
RDS 内网地址:3306
```

公网只暴露 LiteGate 的 HTTPS 443，不需要公开 RDS 的 3306。Forward 域名在服务端唯一绑定一个命名 Stream，客户端不能指定任意主机、端口或其他 Stream。

## 2. 准备条件

开始前确认：

- LiteGate 能通过云内网连接 RDS 地址和端口。
- RDS 安全组只允许 LiteGate 所在主机或网段访问 3306。
- `forward.example.com` 已解析到 LiteGate 或其前置 SLB。
- LiteGate 的 HTTPS 证书能够覆盖该域名，例如现有的 `*.example.com` 泛域名证书。
- 若有前置 SLB、WAF 或 CDN：最好放行任意 HTTP/1.1 Upgrade（Forward v3 使用 `Upgrade: litegate-forward.v3`）；至少要支持 WebSocket Upgrade，客户端会自动回退到 v2。
- 服务端和客户端都能安全读取同一份随机 Token。

先在 LiteGate 主机验证内网连通性：

```bash
nc -vz mysql-prod.example.rds.aliyuncs.com 3306
```

如果这里无法连接，应先检查 RDS 白名单、安全组、路由和 DNS，Forward 无法绕过云内网访问策略。

## 3. 生成 Forward Token

由 LiteGate 直接生成并安全保存 Token：

```bash
sudo litegate forward token --output /etc/litegate/secrets/rds-forward.token
```

该命令使用系统密码学安全随机源生成 32 字节 Token，自动以 `0700` 创建缺失的父目录，并以 `0600` 独占创建 Token 文件。为避免意外破坏仍在使用的凭据，如果目标文件已存在，命令会拒绝覆盖。LiteGate 如果以非 root 用户运行，必须确保该服务用户能够读取生成的文件。

Forward Token 用于授权客户端建立隧道；TLS 负责传输加密，两者不能互相替代。不要把 Token 写进命令行参数、Git 仓库或普通日志。

## 4. 配置服务端 Stream

在 LiteGate 的 `streams_dir` 下创建：

```yaml
# streams/rds-mysql.yaml
name: rds-mysql
listen: false
protocol: tcp
upstream: mysql-prod.example.rds.aliyuncs.com:3306
enabled: true

max_sessions: 100
idle_timeout: 7200

# 可选：限制哪些公网来源能够通过隧道访问该 Stream。
# 前置 SLB/CDN 时必须先正确配置 real_ip.trusted_proxies。
ip_restriction:
  allow_ips:
    - 203.0.113.10/32
    - 198.51.100.0/24
```

关键字段：

| 字段 | 说明 |
| :--- | :--- |
| `listen: false` | Stream 不自行开放数据库端口，只接受 Forward 分发。 |
| `protocol: tcp` | MySQL 使用 TCP。 |
| `upstream` | RDS 的内网 Endpoint 和端口，不要填写公网 Endpoint。 |
| `max_sessions` | 限制并发数据库隧道数，避免连接耗尽。 |
| `idle_timeout` | LiteGate 数据库业务流空闲超时；连接池场景应结合 RDS `wait_timeout` 调整。 |
| `ip_restriction` | 可选的第二层来源限制，不能代替 Token。 |

Forward 专用 Stream 不应配置：

- `port`
- `entrypoints`
- `hostnames`
- `tls.enabled`

公网链路已经由 TLS 加密；若需要数据库内容端到端加密，应在 Navicat、DBeaver 或 MySQL 客户端中开启 MySQL SSL，而不是开启 Stream TLS。

## 5. 配置 Forward 域名站点

在 LiteGate 的 `sites_dir` 下创建：

```yaml
# sites/forward.example.com.yaml
domain: forward.example.com

forward:
  stream: rds-mysql
  token_file: /etc/litegate/secrets/rds-forward.token
```

通常不需要写 `entrypoints: [websecure]`。即使 `config.yaml` 没有 `entrypoints` 段，LiteGate 也会根据 `http.https_port`（默认 `443`）自动提供 `websecure`。Site 省略 `entrypoints` 表示使用可用入口，而 Forward 自身强制 TLS，不会在明文 HTTP 上建立隧道。只有配置了多个入口，并且希望明确限制该域名只能由 `websecure` 接入时，才需要加上这行。

该配置建立固定绑定：

```text
forward.example.com → rds-mysql → RDS 内网 Endpoint:3306
```

Forward Site 不需要配置普通 HTTP `routes`。隧道使用保留路径：

```text
/_litegate/forward/v1
```

客户端只提交域名和凭证，不能在 URL 或请求体中更换数据库目标。

新增配置后观察 LiteGate 日志，确认 Site 和 Stream 已成功加载。配置支持热加载；如果当前部署没有启用文件 Watcher，则按现有部署方式重载或重启 LiteGate。

## 6. 配置真实客户端 IP

LiteGate 直接暴露 443 时无需额外配置。若前面存在 SLB、WAF 或 CDN，只信任实际代理节点：

```yaml
# config.yaml
real_ip:
  trusted_proxies:
    - 10.0.1.10/32
    - 10.0.2.0/24
```

不要配置 `0.0.0.0/0`。否则外部请求可能伪造 `X-Forwarded-For`，绕过依赖客户端 IP 的 Stream 白名单。

## 7. 将 Token 安全复制到客户端

客户端也需要相同 Token。将其保存为只允许当前用户读取的文件：

```bash
chmod 600 ./rds-forward.token
```

Windows 可以把文件放在当前用户专用目录，并确保目录和文件 ACL 不允许其他普通用户读取。

## 8. 在开发者电脑启动本地代理

默认监听本机回环地址：

```bash
litegate forward \
  --remote https://forward.example.com \
  --local 127.0.0.1:3306 \
  --token-file ./rds-forward.token
```

也可以通过环境变量提供 Token：

```bash
export LITEGATE_FORWARD_TOKEN='至少 32 字节的随机 Token'
litegate forward \
  --remote https://forward.example.com \
  --local 127.0.0.1:3306
```

Windows PowerShell：

```powershell
$env:LITEGATE_FORWARD_TOKEN = Get-Content -Raw .\rds-forward.token
litegate.exe forward `
  --remote https://forward.example.com `
  --local 127.0.0.1:3306
```

Forward 进程需要持续运行。默认的 Forward v3 对每个 Cloud 只保持一条 TLS 长连接，每个本地数据库连接是其中的一个 HTTP/2 流，因此连接池新建连接不再重复 TLS 握手；某个流中断时由数据库客户端或连接池重新连接，不影响其他连接。协议选择与回退规则见 [Forward 与 Connect 总览](user/09-advanced/forward-and-connect.md) 第 5 节。

## 9. 在局域网常开虚拟机启动代理

如果 Forward 客户端运行在一台常开虚拟机上，并希望局域网内其他电脑使用它，可以明确监听该虚拟机的局域网 IP：

```bash
litegate forward \
  --remote https://forward.example.com \
  --local 192.168.50.20:3306 \
  --token-file ./rds-forward.token
```

此时其他电脑连接 `192.168.50.20:3306`。LiteGate 会打印局域网暴露警告。还必须在虚拟机防火墙中将 3306 限制到可信网段，不建议监听 `0.0.0.0:3306`。

注意：Navicat 到局域网虚拟机这一段默认是普通 MySQL TCP。如果局域网也不可信，应在数据库客户端中启用 MySQL SSL，或者让 Forward 客户端直接运行在使用数据库的电脑上并监听 `127.0.0.1`。

## 10. 配置数据库客户端

### Navicat / DBeaver

本机运行 Forward 时填写：

```text
主机：127.0.0.1
端口：3306
用户名：RDS 数据库用户名
密码：RDS 数据库密码
```

Forward 运行在局域网虚拟机时，将主机改为虚拟机地址，例如 `192.168.50.20`。

### MySQL CLI

```bash
mysql \
  --host=127.0.0.1 \
  --port=3306 \
  --user=app_user \
  --password
```

### 本地端口已被占用

Forward 的本地端口不必与 RDS 端口相同：

```bash
litegate forward \
  --remote https://forward.example.com \
  --local 127.0.0.1:13306 \
  --token-file ./rds-forward.token
```

数据库客户端随后连接 `127.0.0.1:13306`。

## 11. 是否开启 MySQL SSL

只使用 Forward 时：

```text
本地 Forward 客户端 → LiteGate 公网 443：加密
LiteGate → RDS 云内网：默认明文 MySQL
```

这已经能防止公网监听，但 LiteGate 主机和云内网链路仍是数据库 TLS 的信任边界。

在数据库客户端中启用 MySQL SSL 后：

```text
Forward TLS {
    MySQL TLS {
        SQL 与查询结果
    }
}
```

LiteGate 只转发 MySQL TLS 密文。生产环境建议下载对应云厂商提供的 RDS CA 证书，并在客户端启用证书验证；不要长期使用“不验证服务器证书”的兼容模式。

## 12. Token 轮换

服务端 `token_file` 在 Site 加载时读取。轮换时先原子替换文件，再触发 Site 重载：

```bash
sudo litegate forward token --output /etc/litegate/secrets/rds-forward.token.new
sudo mv /etc/litegate/secrets/rds-forward.token.new /etc/litegate/secrets/rds-forward.token
sudo touch /etc/litegate/sites/forward.example.com.yaml
```

其中 Site 路径应替换成部署所使用的实际 `sites_dir`。同步更新客户端 Token 并重启 Forward
客户端。Forward Site 只有一个 Token，没有新旧并存窗口；已建立的数据库连接不会被强制断开。
使用 v3 时，旧会话上的新连接会收到 403，客户端随即用当前 Token 重新握手。

## 13. 心跳与长连接

Forward v3 使用 HTTP/2 PING：连接空闲 30 秒后发送探测，15 秒内无响应即判定失活并重建会话。
PING 由协议栈直接应答，即使本地应用暂时不读取数据（例如大结果集写入慢速磁盘），健康的连接也不会
被误判断开。回退到 v2 时，客户端和服务端每 20 秒发送 WebSocket Ping 以保持 SLB、CDN 和 NAT 的
连接活跃，Ping 写入失败时关闭隧道。

心跳只检查传输链路是否存活，不会被视为数据库业务流量，也不会刷新 Stream 的 `idle_timeout`。即使 Ping/Pong 一直正常，超过 `idle_timeout` 没有实际数据库数据的隧道仍会被回收，并释放对应的 `max_sessions` 槽位。

这不能绕过云负载均衡的“绝对最长连接时长”。如果前置设备强制定期断开长连接，需要调整其配置，并确保 Navicat、应用连接池能够重连。

上游 RDS 主动关闭时，LiteGate 会立即结束对应的隧道（v3 结束该 HTTP/2 流，v2 发送 WebSocket Close），不会等满 `idle_timeout` 才让本地连接失效。

## 14. 常见问题排查

### 客户端提示证书错误

- 检查 `forward.example.com` DNS 是否指向正确入口。
- 检查 HTTPS 证书是否覆盖该域名。
- 检查系统时间和客户端 CA 信任库。
- Forward 不提供跳过证书验证的参数。

### 返回 404 Not Found

为避免被探测，Token 错误时服务端返回 404 而不是 401，所以先检查 Token：

- 服务端和客户端 Token 不一致。
- Token 文件带有意外空格或换行以外的额外内容。
- 服务端刚轮换 Token，但客户端仍使用旧 Token。

Token 正确时再检查配置：

- Forward Site 没有成功加载。
- `forward.stream` 名称与 Stream 的 `name` 不一致。
- Stream 不是专用 Forward Stream，例如仍配置了 `port`、`entrypoints` 或 Stream TLS。

### Upgrade 失败

默认的 `transport: auto` 在前置设备不放行 v3 Upgrade 时会自动回退到 v2（WebSocket），并在 10 分钟后
重试 v3。如果 v2 也失败：

- 前置 SLB/CDN 没有启用 WebSocket。
- 代理删除了 `Connection: Upgrade` 或 `Upgrade: websocket`。
- 代理只允许 HTTP/2 上游，但没有兼容 WebSocket Upgrade。
- 检查 LiteGate 的 `Forward WebSocket upgrade failed` 日志。

### 可以建立隧道，但无法登录数据库

- 在 LiteGate 主机执行 `nc -vz RDS_ENDPOINT 3306`。
- 检查 RDS 安全组和数据库账号来源限制。
- 确认使用的是 RDS 内网 Endpoint。
- 确认账号、密码、数据库名和 MySQL SSL 模式正确。

### 空闲一段时间后连接失效

- 检查 RDS `wait_timeout`。
- 检查 Stream 的 `idle_timeout`。
- 检查 SLB/CDN 的空闲超时和绝对连接时长。
- 数据库连接池应在借出连接前执行有效性检查，并支持失败重连。

## 15. 最小完整配置

服务端 Stream：

```yaml
# streams/rds-mysql.yaml
name: rds-mysql
listen: false
protocol: tcp
upstream: mysql-prod.example.rds.aliyuncs.com:3306
enabled: true
max_sessions: 100
idle_timeout: 7200
```

服务端 Site：

```yaml
# sites/forward.example.com.yaml
domain: forward.example.com
forward:
  stream: rds-mysql
  token_file: /etc/litegate/secrets/rds-forward.token
```

客户端：

```bash
litegate forward \
  --remote https://forward.example.com \
  --local 127.0.0.1:3306 \
  --token-file ./rds-forward.token
```

数据库工具：

```text
Host: 127.0.0.1
Port: 3306
Username/Password: RDS 原有凭据
```

更完整的安全边界和方案比较参见[LiteGate 数据库安全访问方案](database-proxy-solution.md)。
