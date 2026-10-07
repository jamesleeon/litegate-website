# 443 端口 L4 SNI 分流与 L7 组合实战

同一个 TCP/443 上，按 TLS ClientHello 里的 SNI（和 ALPN）决定连接去哪：一部分原样透传给其他程序，一部分由 LiteGate 终止 TLS 后转成四层字节流，其余进入 LiteGate 自己的 HTTPS 站点。本文从 caddy-l4 的常见写法出发，给出 LiteGate 的对应配置和更多组合玩法。

机制细节、热更新和排错见[同一个 443 承载 HTTPS 与 L4 TCP](shared-443-l4-stream.md)，字段定义见 [Entrypoints](../03-configuration/entrypoints.md) 和 [Stream 配置参考](../03-configuration/stream-config.md)。

## 1. 从 caddy-l4 迁移：四层透传服务与网站共用 443

caddy-l4 的典型配置：

```caddyfile
layer4 {
    :443 {
        @tls-regexp tls sni_regexp ^a.example.com$
        route @tls-regexp {
            proxy localhost:444      # a.example.com 流量转给后端四层服务
        }
        @tls-any tls
        route @tls-any {
            proxy localhost:1234     # 其他流量转给 caddy 自己的 HTTPS
        }
    }
}
```

LiteGate 的等价配置：

```yaml
# config.yaml
entrypoints:
  websecure:
    address: ":443"
    tls: true
    routes:
      - name: a-service
        match:
          sni: a.example.com
        handle:
          proxy: tcp://127.0.0.1:444
```

不需要写"其他流量"那一条：没有命中任何路由的连接直接进入 LiteGate 内置的 HTTPS 管道，由 `sites/` 中的站点处理。

| | caddy-l4 | LiteGate |
|---|---|---|
| 其余流量进入网站 | 再 `proxy` 到本机 1234，多一跳 TCP | 同一进程内交给 HTTPS，没有第二跳 |
| 网站看到的客户端 IP | 1234 端要额外开启 PROXY protocol 才是真实 IP | 天然是真实 IP |
| 域名匹配 | 需要自己写正则 | 精确、`*.` 通配、正则、ALPN 四种，按固定优先级 |
| 改路由 | 重载配置 | 原子热更新，不重绑 443 |
| 四层治理 | 另写 matcher | 交给命名 Stream：ACL、负载均衡、服务发现、会话上限、指标 |

## 2. 三种处理方式怎么选

一个 SNI 命中后，交给谁处理有三种写法：

| 写法 | TLS | 能力 | 适用 |
|---|---|---|---|
| 入口路由 `handle.proxy` | 原样透传，后端自己握手 | 单一目标（TCP 或 Unix Socket），可选 PROXY protocol | 最简单的透传，如自建 TCP/TLS 代理、自带证书的服务 |
| 入口路由 `handle.stream: <name>` | 由该 Stream 决定 | Stream 的全部能力 | 需要手工控制匹配条件（正则、ALPN）又要 Stream 能力 |
| Stream 自己写 `entrypoints` + `hostnames` | 由该 Stream 决定 | Stream 的全部能力，自动生成路由和证书域名 | **推荐**：域名只写一次 |

没有命中的连接 → L7 HTTPS 站点。

## 3. 组合玩法

### 3.1 透传：证书留在后端

就是第 1 节的写法。后端从第一个字节开始执行 TLS，必须自己持有该域名的证书。

后端怎么拿证书需要提前考虑：80 端口由 LiteGate 占用，后端无法直接完成 HTTP-01 验证；443 上该域名已被透传，TLS-ALPN-01 也只能由后端自己应答。常见做法是让后端使用 DNS-01，或者改用下一种方式，由 LiteGate 统一管证书。

后端支持 PROXY protocol 时，可以把真实客户端地址传过去：

```yaml
        handle:
          proxy: tcp://127.0.0.1:444
          proxy_protocol: 2     # 后端必须开启对应解析，否则会把头当成数据
```

### 3.2 终止：LiteGate 管证书，后端收明文

后端只需要处理明文 TCP（或者支持关闭自身 TLS 监听）时，让 Stream 终止 TLS：

```yaml
# streams/tunnel.yaml
name: tunnel
listen: false
entrypoints: [websecure]
hostnames: [tunnel.example.com]
protocol: tcp
upstream: tcp://127.0.0.1:10000
enabled: true
tls:
  enabled: true
  auto_cert: true        # 与 HTTPS 站点共用证书池，已有 *.example.com 时直接复用
```

`hostnames` 同时决定 SNI 路由和证书域名。证书的申请、续期与 HTTPS 站点完全一致，后端不再关心证书。

### 3.3 一个 SNI，多个后端

透传同样可以做负载均衡或服务发现，只是要写成 Stream：

```yaml
# streams/tls-pool.yaml
name: tls-pool
listen: false
entrypoints: [websecure]
hostnames: [api-tls.example.com]
protocol: tcp
enabled: true
lb_policy: round_robin
backends:
  - {upstream: 10.0.0.11:8443}
  - {upstream: 10.0.0.12:8443}
```

也可以用 `service_name` 从 Consul、LiteMesh 等注册中心动态获取后端，实例上下线不需要改配置，详见 [Stream 配置参考](../03-configuration/stream-config.md#动态发现上游)。

### 3.4 同一个域名，按协议拆分（ALPN）

浏览器发出的 ClientHello 带 `h2` / `http/1.1`，其他客户端可以带自己的 ALPN。于是同一个域名可以一半走网站、一半走四层：

```yaml
entrypoints:
  websecure:
    address: ":443"
    tls: true
    routes:
      # PostgreSQL 17+（sslnegotiation=direct）→ 数据库
      - name: pg
        match:
          sni: db.example.com
          alpn: postgresql
        handle:
          stream: pg
```

- 浏览器打开 `https://db.example.com` → ALPN 不匹配 → 进入 L7 站点（比如数据库的 Web 管理界面）；
- `psql "host=db.example.com sslnegotiation=direct"` → 进入 `pg` Stream。

自研客户端只要在 TLS 配置里设置一个自定义 ALPN（如 `myproto/1`），就能用同样的方法与网站共用域名和证书。

### 3.5 通配与正则：批量接入

```yaml
entrypoints:
  websecure:
    address: ":443"
    tls: true
    routes:
      # 每个租户一个子域，全部透传给租户集群的入口
      - name: tenants
        match:
          sni: "*.tenant.example.com"
        handle:
          proxy: tcp://10.1.0.10:443

      # 编号节点：node-1.example.com、node-23.example.com ...
      - name: nodes
        match:
          sni_regex: 'node-[0-9]+\.example\.com'
        handle:
          stream: node-pool
```

`sni_regex` 自动做完整匹配并忽略大小写，不需要写 `^`、`$`。优先级固定为：**精确域名 → 最长通配 → 正则 → 仅 ALPN**。因此可以用一条宽泛的通配兜底，再用精确域名把个别子域拉回来：

```yaml
      - name: tenant-special
        match:
          sni: vip.tenant.example.com     # 精确优先，覆盖上面的 *.tenant.example.com
        handle:
          proxy: tcp://10.1.0.20:443
```

### 3.6 收紧公网入口

```yaml
entrypoints:
  websecure:
    address: ":443"
    tls: true
    on_non_tls: reject    # 首包不是 TLS（扫描器、明文协议）直接断开
    on_no_sni: reject     # 按 IP 访问、不带 SNI 的连接直接断开
    inspect:
      timeout: 5s
      per_ip_pending: 16  # 同一来源 IP 同时处于握手检查中的连接数上限
```

四层服务本身的访问控制写在 Stream 上：

```yaml
# streams/admin-tunnel.yaml
ip_restriction:
  allow_ips: ["203.0.113.0/24"]
max_sessions: 200
idle_timeout: 600
```

HTTP 站点则继续使用 WAF、认证、限流等 L7 中间件。一个 443 端口上，两类流量各自用各自的治理手段。

### 3.7 前面还有一层四层负载均衡

LiteGate 位于云 LB、HAProxy 之后时，让入口接收 PROXY protocol 恢复真实地址。SNI 分流、L7 站点和透传后端都会用恢复后的地址：

```yaml
entrypoints:
  websecure:
    address: ":443"
    tls: true
    proxy_protocol:
      accept: true
      required: true
      trusted: [10.0.0.0/8]   # 只信任 LB 的地址段
    routes:
      - name: a-service
        match: {sni: a.example.com}
        handle:
          proxy: tcp://127.0.0.1:444
          proxy_protocol: 2   # 再把恢复出的地址传给后端
```

### 3.8 内网服务按 SNI 走隧道

Cloud 端的 LiteGate 可以把某个 SNI 通过 Connect 隧道交给内网 Home 节点，内网不需要开放任何入站端口。这类路由由 Connect 注册动态产生，不用写在 `routes` 里，详见 [LiteGate Connect 配置与上线](connect.md)。

## 4. 优先级速查

一个新连接按以下顺序决定去向：

1. 首包不是 TLS → `on_non_tls`（`http` 交给 HTTPS 服务返回错误 / `reject` 直接断开）；
2. 没有 SNI → `on_no_sni`；没有被拒绝时，只有"仅 ALPN"路由还能命中，否则进入 L7；
3. Connect 控制面域名 → Connect；
4. 精确域名（同一域名下，ALPN 命中的路由优先于不带 ALPN 的）；
5. 最长的 `*.` 通配；
6. `sni_regex`，按配置顺序；
7. 仅 ALPN 的路由；
8. 都没命中 → L7 HTTPS 站点。

Stream `hostnames` 生成的路由参与第 4、5 步。在相同模式上，显式写在 `routes` 里的规则优先。

## 5. 注意事项

- **`default` 只能是 `http`。** 没有"其余全部转给另一个程序"的开关。不要用 `sni_regex: '.+'` 充当兜底：L7 站点不在 SNI 路由表里，这条正则会把本该进入网站的连接也吞掉。需要把一批域名交给旧服务时，列出它们的精确域名或通配。
- **域名不要在 L4 和 L7 两边重复。** 同一个 SNI 既是 Stream `hostnames` 又是 HTTPS 站点域名时，L4 先接管，站点收不到流量。LiteGate 会在启动和热更新时输出冲突日志，但不会替你选择。同一域名确实要两边都用，请按 3.4 用 ALPN 拆分。
- **HTTP/3 不参与分流。** 它跑在 UDP/443，由独立 Listener 处理；这里说的全部是 TCP/443。
- **ECH 与无 SNI。** 客户端开启 ECH 后网关只能看到外层 SNI；直接按 IP 连接的客户端没有 SNI，只能靠 ALPN 或 `on_no_sni` 处理。
- **首包必须是 TLS。** 明文 SSH、原生 MySQL TLS、旧版 PostgreSQL 的 SSLRequest 都无法按 SNI 分流，替代方案见[协议限制](shared-443-l4-stream.md#9-协议限制)。
- **一旦有路由，所有连接都要先过 ClientHello 检查**，包括最终进入网站的连接。CDN 回源或企业 NAT 出口共用同一个 IP 时，按实际握手峰值调高 `per_ip_pending`。

## 6. 相关文档

- [同一个 443 承载 HTTPS 与 L4 TCP](shared-443-l4-stream.md)
- [Entrypoints（监听入口）](../03-configuration/entrypoints.md)
- [Stream 配置参考](../03-configuration/stream-config.md)
- [Auto-Cert](../06-certificates/auto-cert.md)
- [Forward 与 Connect：内网穿透总览](forward-and-connect.md)
