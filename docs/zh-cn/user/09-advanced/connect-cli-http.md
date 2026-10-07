# 使用 CLI 发布内网 HTTP 服务

`litegate connect http` 适合把 NAS、审计系统、开发服务等单个 HTTP/HTTPS 上游快速发布到公网。Home 主动连接 Cloud，无需开放入站端口，也无需在 Home 配置 LiteGate Site。

## 工作方式

```text
浏览器 --HTTPS--> Cloud LiteGate --Connect 隧道--> CLI --HTTP/HTTPS--> 内网上游
```

公网 TLS 在 Cloud 终止。Dashboard 因此会分别展示：

- **Registration**：Cloud 是否接受了域名注册，以及隧道是否在线；
- **Cloud TLS**：Cloud 是否已有可用于该域名的证书。

只有两项都正常，公网 HTTPS 才真正可用。CLI 显示注册成功不等于证书一定已就绪。

## 1. 配置 Cloud

先生成 Token：

```bash
litegate connect token --output /etc/litegate/secrets/home-connect.token
```

在 Cloud 主配置中授权 Peer：

```yaml
connect:
  server:
    enabled: true
    hostname: connect.example.com
    path: /_litegate/connect/v1
    peers:
      home:
        token_file: /etc/litegate/secrets/home-connect.token
        allowed_domains:
          - "*.home.example.com"
        max_sites: 20
        max_connections: 512
        sessions: 2

auto_cert:
  enabled: true
  email: ops@example.com
  on_demand:
    enabled: true
    max_certs_per_hour: 10
    max_certs_per_day: 50
```

`allowed_domains` 是 Peer 的授权边界。CLI 每次只能注册一个**精确域名**，不能注册通配域名；上例中的通配写法只用于约束允许的域名范围。

## 2. 配置 DNS 和证书

把 `connect.example.com` 和要发布的 `audit.home.example.com` 都解析到 Cloud。

Cloud 可通过以下方式提供证书：

| 方式 | 适用场景 | Dashboard 显示 |
| --- | --- | --- |
| 预装精确或 SAN 证书 | 已有企业证书 | `ready · exact` |
| 预装 `*.home.example.com` 泛域名证书 | 同一后缀下服务较多，推荐 | `ready · wildcard` |
| 开启 on-demand，使用 HTTP-01 | 少量精确域名、Cloud 的 80/443 可从公网访问 | `eligible/issuing`，成功后为 `ready` |
| 开启 on-demand，并配置匹配的 DNS Provider | 需要 DNS-01 或 Cloud 不能接受 HTTP-01 | 显示 `dns-01:<provider>` |

开启 `auto_cert.on_demand.enabled` 后，Cloud 在接受新的 CLI HTTP 注册后会异步预签发缺少的证书，不必等第一位访客触发。注册 ACK 不会等待 ACME；签发仍受每小时/每日限流保护。若已有精确、SAN 或泛域名证书，则不会重复申请。

仅启用 Connect 不会自动开启 on-demand。未开启时必须预装证书，否则 Dashboard 显示 `missing`。

## 3. 在 Home 运行 CLI

安全地把 Cloud 上的 Token 文件复制到 Home，然后运行：

```bash
litegate connect http \
  --remote https://connect.example.com \
  --name home \
  --token-file ./home-connect.token \
  --domain audit.home.example.com \
  --upstream http://192.168.50.247:8090
```

常用选项：

| 选项 | 含义 |
| --- | --- |
| `--sessions 2` | 持久隧道数量 |
| `--max-connections 128` | 每条 Session 的最大并发请求数 |
| `--host-header preserve` | 默认；向上游保留公网 Host |
| `--host-header upstream` | 使用 `--upstream` 的 Host |
| `--host-header audit.internal` | 使用明确的虚拟主机名 |
| `--cert-file` / `--key-file` | Cloud 启用 mTLS 时使用的客户端证书和私钥 |

也可使用 `LITEGATE_CONNECT_REMOTE`、`LITEGATE_CONNECT_NAME`、`LITEGATE_CONNECT_TOKEN_FILE` 和 `LITEGATE_CONNECT_TOKEN`。Token 不支持明文命令行参数，避免泄露到 shell 历史和进程列表。

## 4. 在 Dashboard 确认结果

打开 **Connect Network**，展开对应 Peer 和 hostname：

| 状态 | 含义 |
| --- | --- |
| Registration `ready` | 域名已被 Cloud 接受；再结合 Peer 在线状态判断隧道是否可用 |
| Cloud TLS `ready` | 证书已加载，可查看覆盖方式、来源、验证方式和过期时间 |
| Cloud TLS `eligible` | 已授权自动签发，任务即将开始 |
| Cloud TLS `issuing` | ACME 正在签发 |
| Cloud TLS `failed` | 签发失败；展开可查看错误 |
| Cloud TLS `missing` | 没有证书，且未启用可用的自动签发 |

建议最后从公网验证：

```bash
curl -v https://audit.home.example.com/healthz
curl -N https://audit.home.example.com/events
```

## 限制与排障

- CLI HTTP 支持普通请求、上传下载、长轮询和 SSE，不支持 WebSocket/HTTP Upgrade；这类服务使用完整的 [LiteGate Connect](connect.md) Site 模式。
- 默认向上游发送公网 Host；若上游启用了 Host 白名单，请设置 `--host-header upstream` 或明确值。
- Cloud 会丢弃客户端伪造的 `Forwarded`、`X-Forwarded-*` 和 `X-Real-IP`，再用可信代理解析出的来源地址重建转发头。
- `failed` 且显示 HTTP-01 错误时，检查公网 80/443、DNS 和 ACME challenge 路径；显示 DNS-01 时检查对应 Provider 权限。
- 普通的 CLI 离线不会撤销注册：Cloud 会保留 hostname 所有权，证书续期授权也继续有效。只有该 hostname 被后续 registration 明确移除/替换，或 Cloud 的持久 Registry 状态丢失时，按需证书才会失去这项 Connect 续期授权；重新注册会再次触发预签发。
- Peer 离线时 Cloud 保留域名所有权并返回 503，不会把请求回落到 Cloud 的本地泛域名 Site。
- `failed` 详情会显示 ACME 返回的原始错误，可能包含内部域名、Provider 或网络信息。Dashboard 和对应状态接口应只对受信管理员开放。
