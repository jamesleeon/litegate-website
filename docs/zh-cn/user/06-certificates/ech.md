# ECH：隐藏网站的 TLS ClientHello

ECH（Encrypted ClientHello）加密浏览器到 LiteGate 的 ClientHello。公网只能看到对应组的 `public_name`，LiteGate 解密后仍按实际网站域名选择证书、TLS 策略和路由。网站继续使用普通 ACME 证书，不需要申请特殊的 ECH 证书。

## 如何配置 ECH：服务端、DNS 与客户端

完整链路是：LiteGate 加载 ECH 密钥并发布网站的 HTTPS DNS 记录 → 客户端解析器保留记录中的 `ech` 参数 → 浏览器取得配置并加密 ClientHello → LiteGate 解密后按原网站域名提供服务。服务端开启并不会强制所有客户端使用 ECH。

### 1. 服务端准备

- 使用支持 ECH 的 LiteGate 构建，在真正终止客户端 TLS 的节点配置 ECH。前面的 CDN 或 TLS 终止代理也必须支持相应功能，否则这里的配置不作用于浏览器连接。
- 开启 `auto_cert.enabled`，配置可用的 Aliyun/Cloudflare DNS 提供商，确保其 `domains` 覆盖隐藏网站和公共名称，凭据允许管理 HTTPS 记录。
- `websecure` 监听 TCP 443，站点允许 TLS 1.3。隐藏网站有直接指向 LiteGate 的 A/AAAA 记录；公共名称使用有效证书。
- 持久化并备份证书/ECH 状态目录。单节点可显式使用 `storage: file`；共享密钥部署参见下方 KV 配置。已有部署不要随意更改存储模式或删除密钥。

### 2. 旧单组配置仍兼容

已有配置无需迁移，例如以下主配置块继续有效（保留已有的 `auto_cert`、DNS 提供商和站点配置）：

```yaml
ech:
  enabled: true
  public_name: ech.example.com
  dns_provider: aliyun-main
  domains:
    - litemesh.example.com
    - dashboard.example.com
```

`public_name` 是外层可见名称；`dns_provider` 对应 `auto_cert.dns_providers[].name`；`domains` 是需要隐藏的实际网站。列出的每个域名都必须有本地 HTTPS 站点，包括最终从 Consul/LiteMesh KV 加载的站点。这种写法不要求在每个站点再加 `ech: true`。

旧配置不填写 `storage` 时继续使用兼容的自动选择：启用 Consul/LiteMesh `config_watch` 时使用相应 KV，否则使用文件。不会因为示例推荐 `storage: file` 就自动改用本地存储。保留原密钥、状态和 KV 前缀；迁移规则见“多组、KV 与升级”。

新部署可使用下方 `groups` 配置，并在站点选择公共名称。不能将 `groups` 与根级旧 `public_name`、`dns_provider`、`domains` 混用。旧全局 `domains` 列表不会被站点 `ech: false` 取消；从列表移除需修改主配置并重启。

### 3. 启动并检查 DNS

主 ECH/DNS 提供商配置变化需要重启。先执行语法检查，再启动服务：

```bash
litegate -t -config config.yaml
litegate -config config.yaml
```

KV 模式下 `-t` 不拉取远端站点，只检查可见本地配置并提示延后完整 ECH 校验。运行时要等初始 KV 快照到齐且合法才发布；不要把 `-t` 成功当作所有远端站点已验证。

日志应出现 `ECH keys loaded` 和每个域名的 `ECH HTTPS record published`。若看到 `invalid_keys` 或发布失败，先处理具体的 KV key、证书或 DNS 错误。

```bash
# 默认 dig 查 A，必须显式查询 HTTPS 才能看到 ECH 配置。
dig app.example.com HTTPS
# 直接检查自己的解析器，替换地址和端口。
dig @192.168.50.110 -p 53 app.example.com HTTPS
```

预期回答是类型 65 的 `HTTPS 1 . alpn="h2" ech="..."`；启用 HTTP/3 时 ALPN 包含 h3。`ech` 是公开配置，Base64 不是 DNS 传输加密；不能仅凭查到这个记录判断浏览器实际使用了 ECH。

### 4. 客户端配置

推荐让浏览器通过自己的 DoH 解析器获取配置，例如 `https://dns.example.com/dns-query`。这个地址必须提供标准 DNS wire-format DoH（GET 的 `dns=` 参数或 POST 的 `application/dns-message`）及有效 HTTPS 证书；浏览器使用的是这个端点，不是 `?name=...&type=65` JSON 测试地址。

- **Vivaldi**：设置 → 网络 → 开启“通过 HTTPS 查询 DNS / DNS Lookup Over HTTPS”，选择自定义提供商并填入自己的 DoH 地址。[官方说明](https://vivaldi.com/blog/tips/tip-739/)
- **其他浏览器**：在其安全 DNS/DoH 设置中选择自己的解析器；具体入口和 ECH 支持受版本、管理策略、代理设置影响。[Firefox 官方 ECH 说明](https://support.mozilla.org/en-US/kb/understand-encrypted-client-hello)
- **普通 UDP/TCP DNS**也能返回 HTTPS/ECH 记录，但系统 DNS 指向 CamoDNS 不保证浏览器会通过该路径获取并使用配置。DoH 不是 ECH 协议的硬性要求；需要实际验证客户端。普通 DNS 查询仍会明文暴露原域名，DoH/DoT 才加密 DNS 传输。

保存设置后完全退出并重启浏览器，继续访问原网站域名（例如 `https://app.example.com`），不要改为访问公共名称。

### 5. CamoDNS 的脚本与测试

自己的解析器必须保留网站 HTTPS 记录中的 `ech`。前置脚本若对 `qtype == "HTTPS"` 直接返回 `reject/noerror`，浏览器拿到的是空回答，无法启用 ECH。只测试两个域名时，在原来的 HTTPS 拦截分支内先放行白名单（根据脚本实际收到的域名格式调整）：

```javascript
if qtype == "HTTPS" {
    if domain == "app.example.com" || domain == "dashboard.example.com" {
        return { "action": "continue" }
    }
    return { "action": "reply", "mode": "reject", "reason": "noerror" }
}
```

修改后保存并清除脚本缓存；后置脚本也不能通过 `filter_type: ["HTTPS"]` 删除这些记录。限制类型 65 查询不等于阻止所有 HTTPS、HTTP/3 或其他 DoH 流量。

支持 JSON 查询的 CamoDNS 可用以下命令诊断；这不是通用 DoH 接口必需的功能：

```bash
curl 'https://dns.example.com/dns-query?name=app.example.com&type=65'
```

响应 `Question.type` 和 `Answer.type` 应为 65，数据包含 `ech`。如果 Question 是 1，先检查服务版本是否正确支持数字查询类型；这表示请求变成了 A 查询，不能直接归因于缓存混用。终端显示解密后的 JSON 明文是正常的。

### 6. 确认实际隐藏成功

浏览器开发者工具的安全面板若显示“已加密的 ClientHello：已启用”，可直接确认该连接使用 ECH。抓取新连接的 ClientHello，外层 `server_name` 应是 `ech.example.com`，原网站仍正常打开。服务端解密后的 ServerName、HTTP Host 以及浏览器地址栏仍是原网站名称，这是预期行为。

Wireshark 可先使用 `tls.handshake.extensions_server_name` 查看 SNI；只测试 TCP 时可以按目标 IP 和 `tcp.port == 443` 缩小范围。HTTP/3 使用 UDP 443，没有 TCP ClientHello 不表示失败。只有 `encrypted_client_hello` 扩展、TLS 1.3 或网页正常打开都不足以单独证明成功，扩展也可能是 GREASE 占位。

| 现象 | 优先检查 |
| --- | --- |
| HTTPS 查询是 NOERROR 空回答 | 前/后置脚本、解析器缓存、上游失败和本地覆盖 |
| JSON type=65 却返回 Question.type=1 | 查询类型解析是否支持数字 65，部署版本是否更新 |
| DNS 有 ech，抓包仍是原域名 | 浏览器实际 DNS 路径、策略、代理、缓存和已有连接 |
| ECH 等待或暂停，日志有 invalid_keys | 对应 KV key 的解析错误与初始同步状态 |
| 删除站点后旧 HTTPS 记录仍存在 | 是否仍列在全局 domains；校验失败时保留旧记录，不自动撤销 |

## 新配置：多组与站点选择

在主 `config.yaml` 中复用现有 DNS 提供商：

```yaml
auto_cert:
  enabled: true
  email: admin@example.com
  certs_dir: ./certs
  dns_providers:
    - name: aliyun-main
      type: aliyun
      enabled: true
      domains: ["*.example.com", "example.com"]
      config:
        access_key_id: "..."
        access_key_secret: "..."
    - name: cloudflare-main
      type: cloudflare
      enabled: true
      domains: ["*.example.net"]
      config:
        api_token: "..."

ech:
  enabled: true
  groups:
    - public_name: ech.example.com
      dns_provider: aliyun-main
    - public_name: ech.example.net
      dns_provider: cloudflare-main
  storage: file
  # KV 集群可改为：
  # storage: kv
  # kv:
  #   provider: litemesh  # 或 consul，复用对应连接和 namespace
  #   key_prefix: litegate/ech/mycluster/
  # key_prefix: litegate/ech/mycluster/
```

在需要启用的站点中指定公共域名，例如：

```yaml
site: app.example.com
ech: ech.example.com
https: true
proxy: 127.0.0.1:8080
```

| 字段 | 含义 |
| --- | --- |
| `enabled` | 默认关闭，显式开启 ECH |
| `groups[].public_name` | 客户端外层可见的公共域名，建议使用专用名称；必须是具体的 ASCII 域名 |
| `groups[].dns_provider` | 一个已启用的 `auto_cert.dns_providers[].name` |
| `domains` | 可选旧配置列表；新配置从站点 `ech: 公共域名` 收集，不需要重复填写 |
| `storage` | `file` 为单节点本地存储；`kv` 显式选择共享存储。兼容 `auto`，仅在 config_watch 开启时选 KV，也兼容旧 litemesh/consul 写法 |
| `kv.provider` | storage: kv 时必填，litemesh 或 consul，复用已有连接；不使用 DNS provider |
| `kv.key_prefix` | storage: kv 时必填；根级作为各组父目录，组级为精确前缀；实际键为 state 和 publisher |
| `key_prefix` | 可选 KV 前缀，组默认 litegate/ech/<public_name>/；根级前缀作为父目录，组级前缀为精确值，组间不得重复 |

内置支持 `aliyun` 和 `cloudflare`；其他服务商可通过声明 `https_records` 并实现 `plugin.HTTPSDNSProvider` 的 DNS 插件扩展，见 [插件开发指南](../../dns-provider-plugin-guide.md)。ECH 密钥、轮换、KV 同步及发布状态由 LiteGate 内部管理，插件只负责 HTTPS 记录 API。要求 `websecure` 监听 TCP 443，站点允许 TLS 1.3。ECH 配置和 DNS 提供商配置修改需要重启，站点内容仍可热加载。

Cloudflare 使用原有的 `api_token` 或 `token`，同名 A/AAAA 记录必须是 DNS only（关闭橙云代理）。阿里云自动识别 `example.com.cn` 等公共后缀；如使用委派子区域，可在提供商的 `config` 中设置 `zone: delegated.example.com`。

## DNS 和证书

1. 为启用 ECH 的每个网站预先建立指向 LiteGate 的 A/AAAA 记录，不能使用 CNAME。LiteGate 不通过 ECH 功能改动地址记录。
2. 确保 `public_name` 的证书可以正常申请。若现有证书配置中的通配符已经覆盖它，会复用该证书；否则会自动将它加入所选提供商的证书申请域名。DNS-01 申请不要求公共名称有 A/AAAA，但为这个名称也配置地址记录便于排查。
3. 启动后，先加载密钥并启动 HTTPS；公共名称的证书可用后，才发布网站的 HTTPS（类型 65）记录：

   ```text
   app.example.com. 600 IN HTTPS 1 . alpn="h2" ech="<ECHConfigList 的 Base64>"
   ```

提供商账户需要查询记录以及创建、更新、删除 HTTPS 记录的权限。DNS 平台或套餐必须支持 HTTPS 记录。已有的非 LiteGate 管理的 HTTPS 记录会触发报错，系统不会覆盖它；上线前请先检查并自行处理这些记录。

浏览器必须支持 ECH，并能取得包含 `ech` 的 HTTPS DNS 响应。若还要避免普通 DNS 查询暴露访问域名，客户端应使用可信的 DoH/DoT。服务端开启 ECH 不会强制所有客户端使用 ECH，普通 TLS 1.2/1.3 客户端仍能访问。

## 密钥与运维

各组密钥保存在 `auto_cert.certs_dir/ech/<public_name>/state.json`（未指定该目录时使用 `tls.certs_dir`），文件包含私钥，需要持久化和备份。在 Unix 上目录/文件权限分别为 0700/0600；Windows 请为证书目录配置合适的账户 ACL。本地恢复副本包含私钥；KV 中的状态使用 `auto_cert.storage_secret` 加密，所有同组节点必须使用相同、至少 32 字节的 secret。首次启用 KV 时，通过 CAS 导入现有本地密钥；不要删除状态重新生成。

每 7 天自动生成新密钥，先持久化并安装到 TLS，再更新 DNS。发布按域名单独记录结果：健康域名每 30 分钟检查，失败域名每分钟重试，不阻塞其他域名或正常轮换。旧密钥在不再被任何域名的已发布或未确认写入引用后保留 14 天；失败域名可能仍在使用的密钥不会删除。极长期故障耗尽 256 个配置 ID 时，会告警并推迟生成新密钥，现有密钥和健康域名仍可使用。重启复用已有密钥；状态损坏会报错，不能通过删除状态文件来简单修复。

KV 模式支持多个 TLS 终止节点共享密钥和发布状态，租约选出一个发布者，其他节点通过 KV watch / blocking query 接收变化，并在最多一个 5 秒周期内刷新密钥。轮换先写 KV，至少等待 15 秒后再发布 DNS，旧密钥继续保留。所有节点应使用相同 public_name、DNS 提供商、站点配置、key_prefix 和 storage_secret，并确认节点能正常同步 KV 后再接入流量。KV 初始化未完成或站点配置解析失败时暂停发布。每个节点仍需要独立持久化目录，不能共用本地目录；显式 storage: file 仅适用于单节点。网站前面若有 CDN、其他 TLS 终止器或 Connect/L4 透传，需在真正终止客户端 TLS 的服务上实现 ECH。`public_name` 在 LiteGate 的 443 SNI 分流中保留给本地解密，不会进入重叠的透传路由；不要将它用作 Connect 控制域名。

将站点 `ech` 改为 false、删除站点或更换组，可热加载并撤回该状态管理的 HTTPS 记录；旧 `domains` 列表仍兼容，列出的域名不会被站点 false 取消，需同时从旧列表删除并重启。修改 `public_name` 或 `dns_provider` 前，需要先撤回旧 HTTPS 记录并等待 DNS 缓存过期，再归档旧状态文件；否则启动会明确拒绝不匹配的状态。

关闭 ECH 时，可先停止该 KV 组所有实例，再运行 `litegate ech withdraw -config config.yaml`。该命令使用保存状态中的域名及原提供商身份，仅删除本实例密钥对应的 HTTPS 记录，保留私钥备份；需要配置中仍保留原提供商的凭据。全部删除成功才清除已发布域名状态，部分失败可重试。命令要求独占状态目录，避免运行中的实例再次发布记录。

撤销后等待至少一个 TTL（默认 600 秒，并考虑客户端缓存），再以 `ech.enabled: false` 启动。若必须在等待期间继续服务，可先在 DNS 控制台撤销记录并安排停用；运行中的 ECH 会在下次全面检查时重新发布，需在检查前完成停用。移除 ECH 配置不会自动撤销记录。更换公共名称或提供商时，使用原配置撤销并等待缓存过期，再归档旧状态文件。

发布成功且配置、协议和密钥未改变时，每 30 分钟全面核对一次 DNS；失败每分钟重试。启用 HTTP/3 后记录包含 `alpn="h2,h3"`。公共名称的证书申请域名仅在运行时派生，不会写回提供商的 `domains`。等待证书超过 5 分钟会产生 Warn 日志。

加载完成后检查每个隐藏域名的本地 HTTPS 站点，拒绝与 SNI 透传、L4 或 Connect 控制域名冲突，以及不允许 TLS 1.3 的策略。`public_name` 不能列入 `domains`。KV 站点尚未加载完成时暂停发布并记录原因，站点配置就绪后再发布。

站点校验使用只读元数据快照，不重新编译线上路由。仅匹配非 HTTP ALPN（例如 `mqtt`）的透传路由不会被误判为 HTTP 站点冲突；匹配 `h2` 或 `http/1.1` 的路由仍需避免覆盖隐藏域名。覆盖 `public_name` 的透传路由或 L4 流会产生 Warn，提示公共名称已保留给本地 TLS。

运行期站点变得不合法时，暂停后续 DNS 发布，**不会自动撤回已经发布的 HTTPS 记录**。同一校验错误或路由遮蔽告警最多每 30 分钟提醒一次，错误变化或恢复后再次失败会立即提醒。需要撤回时使用前述撤销命令；站点删除、发现服务消失等情况应结合告警排查，不能仅凭旧 DNS 记录判断服务仍然正常。

## 上线测试

抓包出现 `encrypted_client_hello` 扩展本身不代表 ECH 成功：浏览器也可能发送随机的 GREASE 占位扩展。若外层 ClientHello 的 `server_name` 仍是原网站域名（且不是配置的公共名称），这条连接没有隐藏原域名。先通过浏览器实际使用的 DNS/DoH 解析器查询网站的 HTTPS（类型 65）记录，确认包含有效 `ech`；再检查浏览器 ECH 策略、安全 DNS、代理或 hosts 覆盖，以及 DNS 缓存和已有连接。使用新的浏览器连接重新抓包，外层 SNI 应为所选组的 `public_name`。服务端握手后的 ServerName/HTTP Host 仍是原域名，这是正常的解密结果。

- 日志中应先出现 `ECH keys loaded`，证书可用并发布成功后，每个域名出现 `ECH HTTPS record published`。出现 `ECH publication failed` 时会显示具体原因并自动重试。
- 用 `dig app.example.com HTTPS` 检查返回 `ech="..."`；同时核对 A/AAAA 指向本实例。
- 用支持 ECH 的浏览器访问原网站，确认业务与证书正常。浏览器访问成功本身不能证明用了 ECH；可用支持 ECH 的 TLS 客户端或抓包确认外层 SNI 为 `ech.example.com`。
- 仓库自动化测试覆盖 HTTP/1.1、HTTP/2、HTTP/3 的实际 ECH 握手、内层站点 TLS 策略、未知密钥的认证重试、普通 TLS 1.2、重启恢复、轮换/部分 DNS 失败及 DNS 记录所有权。

协议与 DNS 记录说明可参阅 [Go TLS ECH 接口](https://pkg.go.dev/crypto/tls#EncryptedClientHelloKey)、[Caddy ECH 说明](https://caddyserver.com/docs/automatic-https#encrypted-clienthello-ech)及 [Cloudflare HTTPS 记录](https://developers.cloudflare.com/dns/manage-dns-records/reference/dns-record-types/#https)。


## 多组、KV 与升级

`site: app.example.net` 使用 `ech: ech.example.net`，由 cloudflare-main 发布；app.example.com 使用 ech.example.com，由 aliyun-main 发布。不限制隐藏域名与公共域名同后缀，但所选 DNS 提供商必须有权管理隐藏域名。多个组时 ech: true 会报错；只有一个组时可使用 true；false 关闭。每个隐藏域名只能属于一组，任何组的公共域名都不能作为隐藏域名。

每组独立管理密钥、发布状态及租约。KV 默认键为 `litegate/ech/<public_name>/state` 和 `litegate/ech/<public_name>/publisher`。不用额外配置连接或 Token，复用已有连接与 LiteMesh namespace；ACL 需要前缀读写及会话/锁权限。所有同组节点使用相同 storage_secret 和组配置。组级 storage/key_prefix 可覆盖根级默认值；根级 key_prefix 加公共域名后组成默认组前缀。

旧单组 public_name/dns_provider/domains 配置继续兼容，不能与 groups 混用，保留原 state.json 和 litegate/ech/default/。迁移到 groups 时，匹配公共域名和提供商的旧本地目录会继续复用。已有 KV 部署建议在对应组明确设置 `key_prefix: litegate/ech/default/` 继续使用已有共享状态，其他组使用自己的默认前缀。停止旧配置实例后再切换，保留状态及备份。新组配置须重启；站点选组可热加载，换组先撤回旧组的记录，再由新组发布。

撤回指定组：`litegate ech withdraw -config config.yaml -public-name ech.example.com`。不传 public-name 则撤回所有配置组。撤回前停止对应 KV 组的全部实例。删除组或修改公共域名/提供商/存储前缀前，先用原配置撤回并等待 DNS 缓存过期，然后归档该组本地与 KV 状态；不能删除密钥来清除发布错误。

## 显式选择共享存储

```yaml
ech:
  enabled: true
  storage: kv
  kv:
    provider: litemesh
    key_prefix: litegate/ech/production/
  groups:
    - public_name: ech.example.com
      dns_provider: aliyun-main
    - public_name: ech.example.net
      dns_provider: cloudflare-main
      # 本组也可覆盖 kv.provider 和 kv.key_prefix
```

对应第一组的实际键为 `litegate/ech/production/ech.example.com/state` 和 `litegate/ech/production/ech.example.com/publisher`。连接地址、凭据及 LiteMesh namespace 复用主配置中的 `litemesh` 或 `consul`；DNS provider 与 KV provider 是两项独立配置。单节点使用 `storage: file` 即可，不需配置 KV。显式选择 KV 但站点来自本地文件时会告警，所有共享节点的站点必须一致。

站点域名必须由所选 DNS provider 的 `domains` 明确覆盖（通配符只匹配一级）；不覆盖的站点在加载时被拒绝。转组时始终先撤回旧记录，只有仍被其他组占用的域名暂停新增并告警；其他域名正常发布。撤销失败的域名继续保留所有可能已发布的密钥，等待单独重试。
