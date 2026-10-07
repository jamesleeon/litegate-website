# Proxy Action (反向代理)

`proxy` 是 LiteGate 最核心的 Action 类型，负责将入站请求转发到后端 upstream 服务。它支持多种发现协议、负载均衡策略和高可靠性配置。

---

## 1. 基础配置 (Static Upstream)

适用于后端 IP 固定或在配置文件中指定的场景。

```yaml
action:
  type: proxy
  upstream_type: static
  upstream:
    - "10.0.0.5:8080"
    - "10.0.0.6:8080"
  lb_policy: round_robin # 负载均衡：round_robin, ip_hash, weighted, weighted_round_robin, p2c, least_conn, cookie
```

### Unix socket HTTP upstream

普通 HTTP 后端也可以只监听 Unix socket。客户端到 LiteGate 仍可使用
HTTPS、HTTP/2 或 HTTP/3，LiteGate 到后端使用 HTTP/1.1：

```yaml
domain: app.localhost
routes:
  - match: { path_prefix: / }
    action:
      type: proxy
      upstream: ["unix:///run/apps/app.sock"]
```

通配站点可以把请求 Host 安全映射到同一目录中的 socket：

```yaml
domain: "*.localhost"
routes:
  - match: { path_prefix: / }
    action:
      type: proxy
      upstream: ["unix:///run/apps/{host}.sock"]
```

例如 `foo.localhost` 对应 `/run/apps/foo.localhost.sock`。`{host}` 只能出现一次
且必须位于文件名部分；请求 Host 必须是合法 ASCII DNS 名称，不能是 IP、路径或
包含转义字符，展开后也必须留在配置目录内且不超过 107 字节。Unix HTTP upstream
支持普通请求和 Upgrade/WebSocket，但目前不支持 upstream TLS、HTTP/2 或主动健康
检查。动态模板不能配置在 `*`、`0.0.0.0` 等全局兜底站点上；应使用明确的域名或
通配域名限制可选择的 Host。socket 目录中也应只放允许该站点访问的服务 socket，
文件及其父目录权限是最后一道安全边界。`action.host` 仅改写发给后端的 HTTP Host
头，socket 路径始终使用客户端原始请求 Host 选择。

---

## 2. 动态发现集成 (Service Discovery)

无需手动列出 IP，LiteGate 自动从发现中心获取实例。动态发现源支持 `litemesh`、`litedeploy`、`docker`、`consul` 和 `discovery`。其中 `discovery` 是连接 `camodns_discovery` 这类 blocking-query 外部聚合层的配置口径。

### Consul 集成
```yaml
action:
  type: proxy
  upstream_type: consul
  service_name: order-service
```

### Litemesh 集成
```yaml
action:
  type: proxy
  upstream_type: litemesh
  service_name: user-api
  mtls: true # 开启内部 mTLS 双向认证
```

### LiteDeploy / Docker / Discovery 集成
```yaml
action:
  type: proxy
  upstream_type: litedeploy # 也可以是 docker、external
  service_name: payment-api
```

> [!NOTE]
> 全局 `service_discovery.catalogs[].provider: discovery` 对应路由运行时的 `upstream_type: external`。如果服务通过标签自动生成路由，LiteGate 会在内部记录正确的发现源，通常不需要手写 `upstream_type`。

---

## 3. 高级转发参数

### 路径处理 (Strip Prefix)
如果路由匹配 `/api/v1`，但后端服务不带此路径，请启用剥离功能：
```yaml
  strip_prefix: true # 转发给后端时移除 match 中定义的匹配前缀
```

### 流式输出 (SSE / MCP)
对于实时推送或大文件下载场景，必须开启流式刷新：
```yaml
  flush_interval: -1 # 禁用缓冲区，实现即时刷盘 (适用于 SSE, WebSocket, MCP)
```

### 超时控制
```yaml
  timeout: 30   # 普通请求的整体超时；Upgrade 请求仅用于握手阶段
  retry: 1      # 不能为负数；非幂等请求只在确认尚未发送时重试
```

### 兼容不支持 chunked 的后端

`disable_chunked: true` 会先缓冲请求体并计算 `Content-Length`。当前单请求缓冲上限为 2 MiB；超过上限会返回 `413`，不会再静默退回 chunked。流量镜像只复制可安全重放的小请求体，未知长度或较大的流式请求会跳过镜像，主请求不受影响。

---

## 4. 健康检查 (Health Check)

LiteGate 会自动探测后端实例。

```yaml
  health_check:
    enabled: true
    path: "/health"      # 探测路径
    interval: 10s       # 探测周期
    timeout: 3s         # 超时时间
```

---

## 5. WebSocket 支持
LiteGate 默认支持 WebSocket 协议，只需确保后端服务正常开启 WS 即可。`timeout` 限制 Upgrade 建连和握手，不限制已建立隧道的存活时间；HTTPS/WSS upstream 同样支持 `root_ca`、SNI 和 mTLS 校验。

---

## 6. gRPC (`proto: grpc`)

设置 `proto: grpc` 即可把 gRPC 后端作为一等公民反代。网关会强制走 HTTP/2，并透传 gRPC trailer（`grpc-status`、`grpc-message`、`grpc-status-details-bin`）。

```yaml
action:
  type: proxy
  proto: grpc                 # gRPC over 明文 HTTP/2 (h2c)
  upstream:
    - "127.0.0.1:50051"
```

- **明文 (h2c)**：`proto: grpc` 默认以明文 HTTP/2 连后端，内网服务最常见。
- **TLS / mTLS**：开启 `mtls: true` 会自动升级为基于 TLS 的 HTTP/2（`grpcs`），无需额外开关。

```yaml
action:
  type: proxy
  proto: grpc
  upstream_type: litemesh
  service_name: order-grpc
  mtls: true                  # gRPC over mTLS（自动升级为 grpcs）
```

> gRPC 服务反射自动路由计划在后续阶段支持。

> [!NOTE]
> **gRPC status 14 重试限制**：网关仅在初始 Header 中返回错误状态时（Header-only 响应）才会触发重试。如果异常状态码（如 `grpc-status=14`）是在数据开始回写给客户端后才在 Trailer 中返回，由于响应体已开始传输，重试将无法进行。

---

## 7. Cookie 会话保持 (`lb_policy: cookie`)

`lb_policy: cookie` 让同一客户端在多次请求间固定命中同一后端，适合有状态会话与长连接。网关会下发一个标识后端的加密 Cookie，后续请求据此路由。

```yaml
action:
  type: proxy
  upstream:
    - "10.0.0.5:8080"
    - "10.0.0.6:8080"
  lb_policy: cookie
  sticky_cookie_name: "LG_STICKY_BACKEND"   # 可选，默认值即此
  sticky_cookie_ttl: 1800                    # 可选，秒（默认 1800 = 30 分钟）
```

- Cookie 值经 **AES-GCM 加密**（后端地址既不泄露也无法伪造），带 `HttpOnly`、`SameSite=Lax`，HTTPS 下带 `Secure`。
- 若粘连的后端不健康，网关回退到轮询并重新粘连。
- 即使只有 1 个后端也会种植 Cookie，确保后续扩容时已连客户端不漂移。

### 多节点一致性 (`sticky_key`)

默认每个进程用随机密钥，因此 A 节点下发的 Cookie 到 B 节点无法解密。多节点部署时，在 `config.yaml` 配一个共享的 32 字节 hex 密钥：

```yaml
sticky_key: "0102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f20"
```

---

## 8. URL Rewrite (`rewrite`)

`rewrite` 可以改写请求路径和查询参数。它在 **WAF、IP 策略、鉴权、限流等中间件之前**执行，因此安全控制审查的是改写后的最终 URI；LiteGate 同时在请求上下文中保留客户端原始 URI，供内部审计组件使用。

### 路径改写

```yaml
action:
  type: proxy
  upstream: ["127.0.0.1:8080"]
  rewrite:
    path:
      pattern: "^/old/(.*)$"   # Go 正则
      target: "/new/$1"        # $1、$2… 为捕获组
```

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `path.pattern` | string | 作用于解码后的 `URL.Path`；非法正则在加载期报错 |
| `path.target` | string | 必须是以 `/` 开头的路径，支持 `$1`/`$2` 捕获引用；不能包含 query 或 fragment |

旧版 `pattern` + `target` 写法继续兼容，但不能和 `path` 同时配置。

当配置了 `path` 时，rewrite 是一个原子操作：只有 `path.pattern` 匹配成功，才会同时执行路径和 query 改写。正则未命中时请求保持不变。纯 query 改写可以省略 `path`。

### 查询参数改写

```yaml
rewrite:
  path:
    pattern: "^/legacy/users/([^/]+)$"
    target: "/api/users/$1"
  query:
    remove: [legacy_debug]
    rename:
      old_appid: client_id
    set:
      source: litegate
      user_id: "$1"
      original: "{query.old_param}"
    add:
      tag: migrated
```

query 操作顺序固定为 `remove → rename → set → add`：

- `remove`：删除参数及其所有值；
- `rename`：保留源参数的所有值并覆盖同名目标；多个源不能重命名到同一目标；
- `set`：覆盖参数为一个值；
- `add`：追加一个值；
- `set/add` 的值支持路径捕获组和 `{host}`、`{path}`、`{header.X}`、`{query.x}` 等变量。请求提供的值只展开一次，不会被当作新的模板继续解释。

修改 query 后会按标准 URL 编码重新生成查询串，参数顺序和等价编码形式可能变化。如果第三方协议按原始 query 字节验签，应只改写 path，或让验签组件读取 `{original_uri}` / `{original_path}`。例如可以通过 action 的 `headers` 显式注入一个仅供可信后端使用的原始 URI 请求头。畸形 query 返回 `400`，改写后的 URI 超过 16 KiB 返回 `414`。

```yaml
headers:
  X-LiteGate-Original-URI: "{original_uri}"
```

### 单回调地址分流

下面的配置可以把第三方平台的一个回调地址分成主账号和子账号两个内部处理路径：

```yaml
routes:
  - name: taobao-sub-account-callback
    priority: 200
    match:
      rule: 'Path("/taobao/callback") && QueryPrefix("state", "sub.")'
    action:
      type: proxy
      upstream: ["127.0.0.1:8080"]
      rewrite:
        path:
          pattern: "^/taobao/callback$"
          target: "/oauth/taobao/sub-account/callback"

  - name: taobao-main-account-callback
    priority: 100
    match:
      rule: 'Path("/taobao/callback") && QueryPrefix("state", "main.")'
    action:
      type: proxy
      upstream: ["127.0.0.1:8080"]
      rewrite:
        path:
          pattern: "^/taobao/callback$"
          target: "/oauth/taobao/main-account/callback"
```

参与值匹配的 query 参数必须只有一个值；例如 `state=sub.x&state=main.x` 不会命中上述路由，避免网关与后端采用不同值。`state` 仍必须是随机、一次性、短期有效并与发起授权的会话绑定；前缀只负责分流，不能代替后端的 state 校验。推荐使用带签名的 `sub.<nonce>.<signature>`，或在服务端保存 `state → 授权类型` 映射。

> `rewrite` 只改当前路由内的路径，**不会重新触发路由匹配**（不同于 Nginx `rewrite ... last`）。需要"干净 URL 全部回退到入口脚本"（WordPress/Laravel、SPA）请用 [`try_files`](./serve.md#5-try_files)。
