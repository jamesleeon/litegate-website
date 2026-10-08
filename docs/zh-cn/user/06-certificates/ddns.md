# DDNS 动态域名解析

使用其他 DNS 服务商时，见 [添加 DNS 服务商](dns-providers.md)：兼容的 libdns 实现可以通过 `litegate build --dns` 按需编入，无需编写插件代码。

LiteGate 内置了 DDNS (Dynamic DNS) 功能，可以自动将网关的公网 IP 同步到 DNS 服务商的 A/AAAA 记录。默认内置阿里云、腾讯云和 Cloudflare；华为云及其它服务商通过第三方 DNS Provider 插件按需编译。

---

## 1. 使用场景

- 网关部署在动态 IP 的环境（如家庭宽带、NAT VPS）。
- 需要自动将已加载的 Site/Stream 精确域名指向当前网关 IP。
- 配合 Let's Encrypt DNS-01 验证，实现"自动 DNS + 自动证书"。
- 多个 LiteGate 节点共同发布同一个域名，每个节点写入自己的公网 IPv4/IPv6。

---

## 2. 启用配置

DDNS 配置嵌套在 `auto_cert.dns_providers` 的每个 Provider 下：

```yaml
auto_cert:
  enabled: true
  email: admin@example.com
  dns_providers:
    - name: "aliyun-main"
      type: "aliyun"
      enabled: true
      domains: ["*.example.com", "example.com"]
      ddns:
        enabled: true
        ipv4: ""               # 留空则自动检测公网 IPv4
        ipv6: ""               # 留空则自动检测公网 IPv6
        sync_a: true           # 同步 A 记录
        sync_aaaa: true        # 同步 AAAA 记录
        # domains 可选；省略时复用上层 domains 选择 Provider。
        # 这里的通配符也只做匹配，实际记录来自已加载的 Site/Stream 精确域名。
      config:
        access_key_id: "LTAI..."
        access_key_secret: "..."
```

---

## 3. 支持的 DNS 服务商

| 服务商 | type 值 | 所需 config 参数 |
| :--- | :--- | :--- |
| 阿里云 DNS | `aliyun` | `access_key_id`, `access_key_secret` |
| 腾讯云 DNSPod | `tencent` / `tencentcloud` | `secret_id`, `secret_key` |
| Cloudflare | `cloudflare` | `api_token` |

> [!TIP]
> 除上述内置服务商外，你可以通过 **DNS Provider 插件**接入任意 DNS 服务商（自定义 `type` 名），同一插件还可同时承担证书 DNS-01 质询。开发方式见 [DNS Provider 插件开发指南](../../dns-provider-plugin-guide.md)。

---

## 4. 自动检测 IP

当 `ipv4` 和 `ipv6` 字段留空时，LiteGate 通过以下方式自动检测公网 IP：

1. 调用公共 IP 检测 API（如 `https://api.ipify.org`）。
2. 获取成功后，与 DNS 记录中的值进行比较。
3. 如果不同，自动调用 DNS API 更新记录。

> [!TIP]
> 如果你的服务器有已知的固定公网 IP，建议直接填写 `ipv4` 字段以跳过自动检测。

---

## 5. 多节点 A/AAAA 记录

LiteGate 将 A/AAAA 按 **RRset（记录集合）** 管理。每个节点只确保自己的地址在集合中，不会把其它节点已经写入的地址覆盖掉。例如三个节点都加载了 `gateway.example.com` Site 后，最终记录为：

```text
gateway.example.com.  A     203.0.113.10
gateway.example.com.  A     203.0.113.11
gateway.example.com.  A     203.0.113.12

gateway.example.com.  AAAA  2001:db8::10
gateway.example.com.  AAAA  2001:db8::11
gateway.example.com.  AAAA  2001:db8::12
```

内置阿里云、腾讯云和 Cloudflare 会追加同名记录；第三方插件也应保留 RRset 中其它节点的地址。使用 Litemesh 或 Consul 作为证书存储时，LiteGate 还会按“Provider + 域名 + 记录类型”加分布式锁，避免多个节点同时进行读改写而丢失地址：

```yaml
litemesh:
  enabled: true
  roles:
    cert_storage: true   # 启用集群证书存储及 DDNS 分布式协调
```

每次同步都是幂等的；相同地址不会重复创建。LiteGate 会短暂缓存刚验证过的结果来合并启动阶段的重复请求，之后仍会重新查询 DNS，因此人工删除记录后能够自愈。

> [!IMPORTANT]
> 多 A/AAAA 是 DNS 轮询，不是健康检查负载均衡。递归 DNS 和客户端可能缓存故障节点的地址。需要秒级摘除、权重或主动健康检查时，应在 DNS 前增加支持健康探测的流量调度，或让多个地址都落到具备健康检查能力的 LiteGate 层。

> [!WARNING]
> 为避免误删其它节点仍在使用的地址，当前的集合模式不会自动删除一个节点曾经发布的旧 IP。节点公网 IP 发生永久变化或节点下线后，应从 DNS 控制台清理旧值。后续如需自动摘除，应使用带节点租约/所有权的 DNS Provider 插件。

---

## 6. 泛域名选择器与精确记录

当 `ddns.domains` 配置为 `*.example.com` 时，它只负责选择处理该域名范围的 DNS
Provider。LiteGate 扫描实际加载的 Site/Stream，并分别同步精确域名，例如
`refund.example.com`、`order.example.com`：

```yaml
ddns:
  enabled: true
  sync_a: true
  sync_aaaa: true
  domains:
    - "*.example.com"
```

上述配置不会创建字面量 `*.example.com` A/AAAA。即使证书 Provider 的 `domains` 包含
`*.example.com`，通配符也只用于证书范围和 Provider 匹配；同步请求本身含 `*` 时会被
直接跳过。底层记录写入接口也会拒绝任何通配 A/AAAA owner，防止其它调用路径绕过。

`*.local` 可以作为私有 DNS Provider 的匹配选择器，但仍只会发布实际加载的精确主机名。
公共 DNS 服务商通常不托管 `.local`，而且 `.local` 在终端系统上常用于 mDNS；纯内网环境
更建议使用组织控制的私有后缀，例如 `*.internal.example.com`。

---

## 7. 内网 DNS（LiteMesh KV → LiteDNS）

DDNS 把公网 IP 写到域名服务商；`dns_update` 则把本网关的内网 IP 按域名写入 LiteMesh KV，由 LiteDNS 应答内网客户端。同一个域名、同一张证书，内网直连网关。需要启用 litemesh。

```yaml
auto_cert:
  dns_update:
    enabled: true
    auto_service_host_sync: true       # 发布所有已加载站点/流的域名
    ip: ""                             # 留空自动检测出口网卡 IP
    key_prefix: "litedns/v1/records/"  # 与 LiteDNS 配置一致
    node_id: ""                        # 留空使用主机名
    record_ttl: 30
    heartbeat_interval: 30s            # KV TTL 为其 3 倍
```

详见 [内网 DNS 自动发布 - 多节点网关支持](../../dynamic-dns-multi-node.md)。
