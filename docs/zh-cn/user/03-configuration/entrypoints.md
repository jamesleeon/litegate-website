# Entrypoints（监听入口）

Entrypoint 是全局共享的网络监听器。站点通过名称引用入口，从而把 socket 绑定与 HTTP Host 路由分开配置。

```yaml
# config.yaml
entrypoints:
  web:
    address: ":80"
  websecure:
    address: ":443"
    tls: true
  internal:
    address: ":8080"
    interface_name: "enp10s0"
```

## TCP SNI 分流与 HTTPS 共用 443

`websecure` 可以在 LiteGate 终止 TLS 之前按 ClientHello SNI 分流原始 TCP
连接。存在显式 `routes` 或 attached Stream 路由时才检查 ClientHello；没有
任何路由时由空 SNI Mux 的快速路径直接交给 HTTPS。未匹配的连接继续进入原有
HTTPS/HTTP2 服务，HTTP/3 仍由同地址的 UDP Listener 独立提供。

完整实战参见[同一个 443 承载 HTTPS 与 L4 TCP](../09-advanced/shared-443-l4-stream.md)。

```yaml
entrypoints:
  websecure:
    address: ":443"
    tls: true
    default: http
    on_non_tls: reject
    on_no_sni: reject

    inspect:
      timeout: 5s
      max_pending: 2048
      per_ip_pending: 16

    routes:
      - name: a-service
        match:
          sni:
            - a.example.com
            - "*.proxy.example.com"
          sni_regex:
            - 'svc-[0-9]+\.example\.com'
        handle:
          proxy: tcp://127.0.0.1:444
          proxy_protocol: 2

      - name: local-tls-service
        match:
          sni: tcp.example.com
        handle:
          proxy: unix:///run/local-tls-service.sock

```

`match.sni` 既可写单个字符串，也可写列表，并支持 `*.example.com` 后缀
匹配；`match.sni_regex` 接受一个或多个 Go/RE2 正则表达式，自动执行完整
域名匹配且忽略大小写。优先级固定为精确域名 → 最长通配后缀 → 正则，
正则之间按配置顺序匹配。这里不接受 `*` 作为默认规则，未匹配行为由显式
的 `default: http` 表达。正则在加载配置时预编译，每条最长 512 字节、
每个路由最多 32 条、每个入口最多 256 条，无效表达式会直接拒绝配置。
该优先级也适用于自动生成的 attached Stream 路由：显式精确/泛域名规则可在
相同模式上覆盖自动规则，但显式正则仍低于自动生成的精确/泛域名规则。

路由命中后 LiteGate 不终止 TLS，ClientHello 和后续字节会原样发送给
`handle.proxy`。目标可以是 `tcp://host:port`、裸 `host:port`，或同机的
`unix:///absolute/path.sock`。Unix Socket 目标必须使用静态绝对路径，不支持
HTTP Unix upstream 中的 `{host}` 模板；该后端接收到的仍是未解密的完整 TLS 流。
可选的 `handle.proxy_protocol: 1` 或 `2` 会先向后端发送
客户端来源信息；如果入口本身经 PROXY protocol 接入，会继续传递其中恢复的地址。
如果使用 `handle.stream`，连接会交给 `streams/` 中同名的 L4 Stream，复用其
TLS 终止或透传、ACL、服务发现、负载均衡、PROXY protocol 和指标能力；此时
PROXY protocol 应配置在 Stream 上，而不是入口路由上。
更推荐直接在 Stream 中配置 `entrypoints: [websecure]` 和 `hostnames`，LiteGate
会自动生成 `handle.stream` 路由；`hostnames` 同时作为自动证书域名，因此无需
在 Entrypoint 和 `tls.domains` 中重复声明域名。显式 `handle.stream` 保留用于
手工覆盖和兼容已有配置。
新增、删除或修改 `routes` 都会原子替换路由快照，不重绑公网端口；即使启动时
没有任何路由，首次加入附着 Stream 也可直接热更新。`on_non_tls` 可选 `http`（交给
HTTPS 服务生成错误响应）或 `reject`（直接关闭），默认为 `http`。
`on_no_sni` 使用相同取值，控制合法 TLS ClientHello 未携带 SNI 时的行为；
公网入口建议设为 `reject`，需要兼容旧客户端时保留默认的 `http`。

### 按 ALPN 匹配

`match.alpn` 把路由限定为 ClientHello 中提供了所列 ALPN 协议之一的连接
（精确匹配、区分大小写）。可与 `sni`/`sni_regex` 组合，也可单独使用：

```yaml
entrypoints:
  websecure:
    routes:
      # PostgreSQL 17+ 直连 TLS（sslnegotiation=direct）与 Web 界面共用域名：
      # PG 客户端进数据库，浏览器仍走 HTTPS。
      - name: pg-direct
        match:
          sni: db.example.com
          alpn: postgresql
        handle:
          stream: pg
      # 仅 ALPN 时匹配任意 SNI，也包括未携带 SNI（按 IP 连接）的客户端。
      - name: pg-any
        match:
          alpn: postgresql
        handle:
          proxy: tcp://10.0.0.5:5432
```

规则：

- 优先级仍为精确域名 → 最长通配 → 正则，仅 ALPN 的路由排在最后。同一 SNI
  模式下，ALPN 命中的路由优先于不带 ALPN 的路由；ALPN 未命中的路由会被跳过，
  继续匹配下一类，最终回落到 HTTPS。
- 每个（SNI, ALPN）组合只能有一个归属。不带 ALPN 的路由可以与 ALPN 路由共用
  同一 SNI，但两条路由不能以同一协议声明同一 SNI。显式 ALPN 路由不会抑制 Stream
  `hostnames` 自动生成的路由，该 Stream 仍是其他协议的兜底。
- 每条路由最多 16 个协议，每个 1–255 字节。
- ECH 会隐藏内层 ClientHello（包括 ALPN），路由只能看到外层值。

`timeout`、`max_pending`、`per_ip_pending` 和路由可以在线热更新；已有连接
继续使用接入时的预算。`inspect.dispatch_queue` 通常无需配置，默认与
`max_pending` 相同；由于它决定内部 channel 容量，修改它需要重启。检查并发
达到上限时 LiteGate 会暂停从 TCP listener 接收新连接，让内核 backlog
承担短时突发，而不是继续接收后立即关闭。可通过
`litegate_sni_inspect_pending`、`litegate_sni_dispatch_queue_depth`、
`litegate_sni_inspect_rejected_total` 和 `litegate_sni_inspect_duration_seconds`
观察检查器的容量与拒绝原因。

只要存在一条 SNI 路由，检查就会应用于该 `websecure` 入口的全部新连接，
包括最终交给普通 HTTPS Site 的连接。默认 `timeout: 5s`、`max_pending: 2048`、
`per_ip_pending: 16`；最后一项限制同一来源 IP 正在检查的 ClientHello 数量，
不是已建立连接数。首次进入检查模式时，LiteGate 会通过 Info 日志输出当前预算。
CDN、NAT 或企业统一出口场景应按握手峰值调整。

当前该能力只挂载在标准 `websecure` EntryPoint；普通 EntryPoint 不参与 SNI
分流，没有路由的 `websecure` 通过空 Mux 快速路径直接进入 HTTPS。

## 由外部四层代理接入

如果由 HAProxy、nginx stream 等程序负责公网 TCP/443 和四层分流，可以让
LiteGate 只监听 Unix socket，并接收入站 PROXY protocol。LiteGate 仍负责
证书、TLS 终止、域名与 HTTP 路由：

```yaml
entrypoints:
  websecure:
    address: unix:///run/litegate/websecure.sock
    tls: true

    unix:
      mode: "0660"
      group: nginx

    proxy_protocol:
      accept: true
      required: true
      trusted: local
      timeout: 2s
```

处理顺序固定为：PROXY protocol → SNI 检查 → TLS → HTTP。PROXY v1 和 v2
均受支持，建议外部代理发送 v2。`required: true` 会拒绝没有 PROXY 头的连接；
如果需要同时接受直接连接，可以省略该项，但通常不建议在明确的代理边界上
使用可选模式。

Unix socket 默认创建为 `0660`，缺失的父目录以 `0750` 创建。`unix.mode`
可覆盖文件权限，`unix.group` 可指定 Unix 用户组（Windows 不支持 group）。路径
必须为绝对路径且不超过 107 字节。真正的访问边界由 socket 文件和父目录权限
决定；LiteGate 不会修改进程全局 umask，只会在监听成功后立即设置最终权限。
它只会清理同路径的旧 socket，绝不会覆盖普通文件或仍在监听的 socket。

如果 nginx 以 HTTP 反代方式连接 Unix socket（HTTP 模块不能发送 PROXY 头），
LiteGate 会把该连接识别为本机 Unix 入口，采信 nginx 设置的
`X-Forwarded-For`、`X-Forwarded-Proto` 和 `X-Forwarded-Host`。因此必须限制
socket 和父目录权限，并让 nginx 覆盖这些请求头。若 PROXY protocol 已成功解析，
则连接改用头内的 TCP 来源地址，后续仍按普通 `trusted_proxies` 规则判断。

SNI 检查器无法从未携带 PROXY 头的 Unix 对端区分客户端 IP，因此这种连接只受
`max_pending` 总额度约束，不计入 `per_ip_pending`；携带 PROXY 头时照常按真实 IP
限额。可选 PROXY 模式会在第一个字节即可排除普通 TLS/HTTP 流量，只有以
`P` 或回车开头但信息不足的模糊前缀才会等待 `timeout`。

Unix stream socket 无法承载 UDP，因此这种模式下 LiteGate 不启动 HTTP/3。
如果仍需 HTTP/3，应由外部入口单独代理或终止 UDP/443。

TCP Entrypoint 也能接收入站 PROXY protocol，但必须把直接相连的代理 IP 或
CIDR 列入 `trusted`，例如：

```yaml
proxy_protocol:
  accept: true
  required: true
  trusted: [127.0.0.1/32, "::1/128"]
```

```yaml
# sites/internal-api.yaml
domain: internal-api.example.com
entrypoints: [internal]
routes:
  - match:
      path_prefix: /
    action:
      type: proxy
      upstream: ["http://127.0.0.1:9000"]
```

`interface_name` 使用 Linux `SO_BINDTODEVICE`，绑定的是网卡而不是它当前的 IP，因此适合 DHCP 地址变化的服务器。LiteGate 进程必须具有设置该 socket 选项所需的权限。在非 Linux 平台配置该字段会明确启动失败。

`web` 和 `websecure` 分别是标准 HTTP、HTTPS 入口。目前额外的自定义入口支持明文 HTTP；TLS 入口应使用 `websecure`。旧的 `http.port`、`http.https_port` 和站点 `port` 仍然兼容。未声明 `entrypoints` 的旧站点保持原有行为，可从所有入口匹配。

当标准入口使用 Unix socket 时，旧的 `http.port` / `http.https_port` 仍作为对外
端口和兼容元数据保留，但不再被当作 LiteGate 实际绑定的 TCP 端口。端口冲突检查
和监听器面板以 `entrypoints.*.address` 为准；Unix 监听器显示 socket 路径且端口为 0。

站点不能同时配置 `port` 和 `entrypoints`，引用未定义入口也会导致配置校验失败。
