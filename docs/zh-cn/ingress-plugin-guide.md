# Ingress 入口插件

Ingress 插件在指定 HTTP 入口上、Site 域名匹配之前处理请求，适合标准正向代理或
其他需要自主识别请求的 HTTP 服务。Action 和 Middleware 继续服务于已匹配的站点路由。
插件仍采用编译期注册，公共契约位于 `pkg/plugin/ingress.go`。

## 执行位置

```text
入口标识与 Forward 目标约束
  → 全局 Ingress 治理和 IP 限制
  → 可信来源头处理与客户端 IP 解析
  → 当前 entrypoint 的 Ingress 插件链
  → 路径清理、控制端点、Site 匹配与 HTTPS 重定向
  → Site / Route 中间件 → Action
```

`ingress_plugins` 中的数组顺序就是执行顺序。每个绑定必须声明唯一 `name`、
注册 `type` 与非空 `entrypoints`；入口必须在全局 `entrypoints` 中存在。
不存在于构建产物中的插件使配置校验失败，避免配置意外落空。
空配置不接管任何流量；插件未配置时，普通请求无需获取插件生命周期锁。
插件无法接管原始 TCP/SNI；那属于 entrypoint transport routes。
通过 Forward 或 Connect 注入的内部请求始终进入原有站点授权流程，不执行入口插件。

## 最小插件

```go
package ping

import (
    "net/http"
    "github.com/jamesleeon/LiteGate/pkg/plugin"
)

type config struct { Path string `json:"path"` }
type handler struct { path string }

func (h *handler) Claim(r *http.Request, m plugin.IngressRequest) http.Handler {
    if r.Method != "GET" || r.URL.Path != h.path { return nil }
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        w.Write([]byte("pong from " + m.EntryPoint))
    })
}

func init() {
    err := plugin.RegisterTypedIngress("ping",
        func(cfg config) (config, error) { return cfg, nil },
        func(cfg config, deps *plugin.Dependencies) (plugin.IngressHandler, error) {
            return &handler{path: cfg.Path}, nil
        },
    )
    if err != nil { panic(err) }
}

```

配置使用单独的 `config` 对象，字段支持嵌套结构、列表与数值：

```yaml
entrypoints:
  tools:
    address: 127.0.0.1:9000
ingress_plugins:
  - name: local-ping
    type: ping
    entrypoints: [tools]
    config:
      path: /ping
```

插件用 `IngressConfig.Decode` 解析 JSON 标签；数据来自独立不可变快照，未知字段报错。
`Validate` 是必需的无副作用校验，不创建资源、不读取实时环境或发起网络访问。
`Factory` 是运行期初始化，可以读取密钥、构造 transport 或启动资源；每个绑定独立创建一次，
同一绑定的多个入口共享实例。Dependencies 提供日志、服务发现和共享插件配置视图。
插件可注册 `Manifest{Kind: "ingress", ...}`，供 CLI、Dashboard 和 MCP 查看。

## 请求与生命周期契约

- `IngressHandler.Claim(r, meta) http.Handler` 是唯一的请求接管接口，可并发调用。
  返回 nil 继续选路；返回 handler 后，宿主执行处理并统一记录日志、指标和 Dashboard。
  Claim 不接收 ResponseWriter，且不得修改请求或读取 body。
- 收到的是路径清理之前的请求目标。正向代理必须保留 absolute-form 的目标语义；
  不能按代理域名去匹配目的主机，也不能将普通路径误判为代理请求。
- HTTP/1 CONNECT 可以使用 `http.NewResponseController(w).Hijack()`；要保留返回 reader
  中预读的字节。HTTP/2/3 不使用 Hijack，需要通过协议支持的请求/响应流实现。
- Handler 必须在结束对连接的所有权之后才返回，不能启动后台隧道后立即返回。
  宿主通过原子调用计数排空旧实例；超过 `http.shutdown_grace`（未设置时 30 秒）则强制关闭。
- 可选 `IngressCloser.Close(context.Context)` 负责释放资源、取消任务和关闭持有的连接；
  实现应及时返回并遵守 Close 的截止时间。Dependencies.Context 由宿主管理，关闭时取消。成功更新后旧实例在调用排空或宽限期到期时关闭；进程关闭则立即调用 Close，
  此时可能与 Claim 及已接管请求的 handler 并发。每个实例只关闭一次。
- Factory 返回非 nil handler 和 error 时，宿主会关闭该部分初始化实例。
  Factory 自己若 panic 或无法返回实例，必须自行保障初始化资源不会泄漏。
- 未提交的候选实例会关闭，已发布实例在候选失败时保留。绑定未改变时不重建，
  仅更新 Site 不会打断或重建入口插件。
- 处理后的请求不会进入 Site 的中间件或证书授权检查。访问日志、指标和 Dashboard 由宿主记录，按 `ingress:<binding name>` 聚合，CONNECT 时长记录为流生命周期而非普通请求延迟。认证、目标策略和限流由插件实现。
- 绑定通过 `reflect.DeepEqual` 比较。仅改变 `password_env` 所指环境变量的值不会重建实例；需改变绑定配置或重启才能加载新密码。
- 钩子在全局 IP 规则和 IDS 之后、Site 选择之前。宿主已剥离权威信任头，非可信连接的 `X-Forwarded-Proto` / `X-Forwarded-Host`，及非可信选路客户端的 `X-Selector-Sid`，并注入来源和转发协议元数据。宿主 `Server` 和 `Alt-Svc` 响应头在插件拒绝接管后才设置。

完整参考实现见 [forward_proxy](https://github.com/jamesleeon/LiteGate/blob/master/examples/plugins/ingress/forwardproxy/README.md)，
它包含真实 HTTP、HTTPS CONNECT、缓冲字节、半关闭、DNS 地址校验和关闭测试。
公开实现源码位于 `pkg/plugins/forwardproxy`，标准 CLI 已空导入注册；Dashboard、
CLI 和 MCP 使用同一份注册表与 Manifest 展示它，类型为 `ingress`。
入口插件的执行阶段与 action/IDS 不同，但沿用相同的编译注册和公共 SDK 体系。
使用 `litegate -hash '你的密码'` 生成 bcrypt 哈希并配置 `password`，或使用
`password_env` 读取原始密码，两者不能同时配置。`hosts` 约束 TLS SNI 而非目标 Host。

## SDK 工具与正向代理安全约定

`RegisterTypedIngress[T, P]` 使用严格 JSON 解码到 T，再通过 `prepare func(T) (P, error)` 显式生成准备结果，交给 `factory func(P, *Dependencies) (IngressHandler, error)`。实例构建时只解码和准备一次；独立配置预检仍独立准备并丢弃结果，prepare 不应有副作用。时长字段可声明为 `plugin.Duration`，接受 `"10s"` 等正数时长。
`IngressRequest` 包含 EntryPoint、ClientIP、ServerName、原始 RequestURI 与协议主/次版本。
`proxyutil.Tunnel(ctx, w, r, backend, idle)`（导入 `pkg/plugin/proxyutil`） 接管已授权且已拨号的连接，统一处理 HTTP/1 Hijack、HTTP/2/3 流、双向复制和取消。半关闭仅在 HTTP/1 劫持连接上保留；HTTP/2/3 下载结束即停止上传并返回，及时发送流结束信号。调用者负责关闭 backend，ctx 应有最大生命周期截止时间。

共用网站入口时必须配置 `hosts` 或开启 `probe_resistance`，否则正常站点的 absolute-form HTTP/1 请求也可能收到 407。`hosts` 限制 TLS SNI；明文入口应使用独立入口或 probe_resistance。
成功 bcrypt 认证缓存请求认证头的 SHA-256 摘要 5 分钟，命中时续期，使用常量时间比较；缓存仅存一项，每实例最多同时进行两次 bcrypt 验证，等待并发槽位受请求 Context 约束且最多 100ms，超时返回 407（probe_resistance 下继续网站选路）。
通配域名规则默认拒绝本机网卡地址、NAT64 `64:ff9b::/96`、`240.0.0.0/4` 和 `198.18.0.0/15`；有意访问这些目标须显式配置 IP/CIDR，deny 规则始终优先。
DNS 解析与每个地址拨号各有独立 dial_timeout，整个请求仍受 max_duration 约束；所有 DNS 答案在拨号前统一校验。

Dependencies.Context 仅向 ingress 插件注入；其他插件类型得到 nil。
网卡地址快照缓存 30 秒后按需刷新。云主机的 1:1 NAT 弹性公网 IP 可能不在网卡上，网卡检查无法识别回连该 IP；应把网关公网 IP 加入 `denied_destinations`。
绑定不变时会复用实例；仅修改 `shutdown_grace` 不会更新该实例已保存的退役宽限期，需改变绑定或重启使新值生效。
