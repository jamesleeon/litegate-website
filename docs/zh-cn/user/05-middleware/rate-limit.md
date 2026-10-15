<!-- GENERATED FILE — DO NOT EDIT.
     Source: internal/configdocs/docs/zh/rate-limit.md (package internal/configdocs)
     Regenerate: go generate ./internal/configdocs/...
     Edit the source instead; a drift test fails if this copy is edited directly. -->

# 限流（V2 配置）

限流是路由治理能力，控制请求吞吐率以防止上游过载。LiteGate 支持四种限流算法：
- **令牌桶 (`token_bucket`，默认)**：允许平滑突发流量（Burst），维持长期平均速率，适合核心 API 的流量整形与防雪崩。支持任意 `<= 1s` 与 `> 1s` 窗口，统一按 `rate / window` 补充令牌。
- **滑动窗口计数器 (`sliding_window`)**：采用 Cloudflare 平滑加权近似计数，$O(1)$ 空间复杂度。对于均匀请求能平滑跨窗口过渡，但作为近似算法，最坏情况下（上一窗口末尾和下一窗口末尾集中突发）任意滑动区间的峰值仍可能接近 200%。适合中高频 API 流量整形与通用防刷。
- **精确滑动日志 (`sliding_window_log`)**：记录窗口内精确请求时间戳，严格保证任意连续滑动窗口内的请求总数不超过设定上限，适合金融/计费配额与关键高安全等级配额限制（Redis 端基于 ZSET 实现）。
- **固定窗口 (`fixed_window`)**：离散时间窗口内重置计数器，开销极小，适合粗粒度基础频次限制。

本文示例使用 `site:`、路径路由和 `use:` 的 V2 语法。

## 路由共享额度与客户端 IP 额度

```yaml
site: api.example.com
/api:
  proxy: localhost:8080
  rate_limit: 100
/upload:
  proxy: localhost:8080
  rate_limit: {rate: 10, key: ip}
/quota:
  proxy: localhost:8080
  rate_limit: {rate: 60, key: ip, algorithm: sliding_window, window: 1m}
```

`rate_limit: 100` 按站点和路由共享 100 QPS，等价于 `{rate: 100, key: route}`。`key: ip` 为每个客户端 IP 分配独立额度。普通配置只支持 `route` 和 `ip`，不支持请求头、API Key 或租户表达式。

IP 使用网关解析的客户端地址；转发头只在全局 `trusted_proxies` 的信任范围内生效。按 IP 的本机缓存最多保留 100000 个客户端桶；容量耗尽后，新客户端共享该路由的备用桶，已有客户端继续使用自己的桶。

| 字段 | 默认值 | 说明 |
|---|---|---|
| `rate_limit` | `0`，关闭 | 数字限额，或 `{rate: 正数, key: route/ip, algorithm: ..., window: ...}` |
| `rate_limit_key` | `route` | 独立字段写法，与映射中的 `key` 二选一（`route` 或 `ip`） |
| `rate_limit_algorithm` | `token_bucket` | 限流算法：`token_bucket`、`sliding_window`、`sliding_window_log` 或 `fixed_window` |
| `rate_limit_window` | `1s` | 窗口长度（如 `500ms`、`1s`、`10s`、`1m`，必须为整数毫秒，最小 1ms）。全算法支持，定义配额或填充周期 |
| `rate_limit_policy` | `static` | `static` 或 `adaptive`（自适应调节仅支持 `token_bucket` 且仅支持默认 1s 窗口） |

在令牌桶算法下，无论配置大于、等于还是小于 1 秒的 `window`（如 `{rate: 10, window: 500ms}` 或 `{rate: 100, window: 1m}`），令牌桶容量自动设定为 `ceil(rate)`，并以 `rate / window.Seconds()` 匀速补充令牌（例如 500ms 补满 10 个即 20 QPS；1 分钟补满 100 个即 1.67 QPS），既允许客户在窗口初期瞬时打满突发，又严格控制长期流入速率。未指定 `window` 时默认为 1 秒 QPS 模式（支持小数 QPS，例如 `0.5` 表示平均每两秒一个请求，突发容量为 QPS 向上取整）。滑动窗口与固定窗口在配置 `window` 后以窗口周期为准。额度不足立即返回 **429 Too Many Requests**。

按 IP 限流复用入口解析的客户端地址，不直接读取请求头。只有直连地址属于 `real_ip.trusted_proxies`（或受文件权限保护的 Unix 入口）才解析 XFF；多条同名头作为完整链从右向左解析，使用第一个非受信 IP，并统一 IPv4/IPv6 表示。遇到边界上的非法或空地址时回退到直连地址。前置代理必须覆盖客户端提交的 XFF，或在完整链右侧追加它实际观察到的客户端 IP；若代理原样透传客户端自报地址，网关无法鉴别。不要把公网客户端所在网段或 `0.0.0.0/0`、`::/0` 配置为受信代理。

## 限流算法与选型指南

| 算法标识 | 算法名称 | 特性与优势 | 典型适用场景 |
|---|---|---|---|
| `token_bucket` | 令牌桶（默认） | 允许合理突发容量（Burst），有令牌则立即放行，额度不足返回 429，不排队，长期平均速率受控 | 网关通用防护、高并发 API 防雪崩 |
| `sliding_window` | 滑动窗口计数器 | 跨窗口线性平滑加权估算，非精确时间戳；最坏情况峰值仍可能接近 200%，$O(1)$ 极低内存占用 | 分钟/小时级通用配额、高并发防暴力调用 |
| `sliding_window_log` | 精确滑动日志 | 严格记录时间戳，杜绝任意滑动区间的超额请求（无临界毛刺）；高精度保证严格配额 | 计费计量、SaaS 阶梯配额、金融交易接口 |
| `fixed_window` | 固定窗口 | 简单时间切片与计数器，到期清零重置，计算最轻量 | 短信/验证码限制、粗粒度防刷 |

```yaml
site: api.example.com
/sms/send:
  proxy: localhost:8080
  rate_limit: {rate: 5, key: ip, algorithm: fixed_window, window: 1m}
/openapi:
  proxy: localhost:8080
  rate_limit: {rate: 1000, key: ip, algorithm: sliding_window, window: 1h}
/billing:
  proxy: localhost:8080
  rate_limit: {rate: 100, key: ip, algorithm: sliding_window_log, window: 1m}
```

## 多条路由共享总额度

定义命名 `ratelimit` middleware，并通过 `use` 引用：

```yaml
site: api.example.com
middlewares:
  total-budget:
    type: ratelimit
    config: {qps: "50", key: route, algorithm: sliding_window, window: 1s}
/api:
  use: total-budget
  proxy: localhost:8080
  rate_limit: 10
/assets:
  use: total-budget
  proxy: localhost:8080
```

同一站点引用 `total-budget` 的路由共同使用 50 QPS；`/api` 额外受到自己的 10 QPS 限制。命名 middleware 与路由额度使用独立桶，即使名称相同也不会混用。`config.key: ip` 可改为按客户端 IP 共享。命名 middleware 支持 `qps`、`key`、`algorithm` 和 `window`。

一条请求只执行匹配到的路由；在 catch-all 路由上配置限流，不会自动保护其他具体路由。全站总额度应通过同一个命名 middleware 应用到需要保护的所有路由。不要在同一路由重复引用同一个 middleware。

## 自适应限流与热更新

```yaml
site: api.example.com
/api/compute:
  proxy: localhost:8080
  rate_limit: 100
  rate_limit_policy: adaptive
```

自适应策略使用主机 **CPU** 负载，不使用内存指标：CPU 高于 80% 时，每次调整降低当前速率 20%；低于 50% 时提高 10%。调整周期为两秒，CPU 由独立采样器采集。下限为 `min(上限, max(1, 上限 × 10%))`，因此小于 1 QPS 的配置仍不会超过上限。自适应限流仅支持 `token_bucket` 算法，且仅支持默认 1s 窗口（省略 `rate_limit_window`）。

修改 QPS 或算法并重载配置后，LiteGate 会自动平滑更新或替换限流器。自适应只在本机运行，不能与 `key: ip` 组合，也不会使用 Redis。

## Redis 分布式额度与故障降级

在网关全局配置中启用 Redis（不是站点文件）：

```yaml
redis:
  enabled: true
  mode: standalone
  address: localhost:6379
  db: 0
```

静态路由额度和命名 middleware 额度自动使用 Redis，按 IP 的额度同样跨节点共享。四种算法均支持 Redis 集群分布式模式：
- **`token_bucket`**：毫秒级原子补充令牌（Hash：`tokens`、`last_update`），TTL 随补满时长动态延展。
- **`sliding_window`**：Cloudflare 加权滑动窗口原子计算（Hash：`curr`、`prev`、`win`），$O(1)$ 空间。
- **`sliding_window_log`**：基于 Redis ZSET 存储请求时间戳毫秒滑动日志，保证严格任意窗口配额。
- **`fixed_window`**：原子 `INCR` 与窗口毫秒 `PEXPIRE`。Lua 脚本显式将完整键传入 `KEYS[1]`，原生兼容 Redis Cluster 跨 Slot 分片路由。

Redis 请求预算为 200 毫秒，同一 Redis 客户端最多 64 个并发限流操作。连续失败达到 3 次后，依赖熔断 5 秒；冷却后只允许一个恢复探测。Redis 出错、依赖熔断或并发容量耗尽时，自动退回每个网关节点对应算法的本机限流器。

**降级后不再保证严格的集群总额度**：多个节点各自拥有本机额度。本机备用桶也不跟踪成功的 Redis 请求，切换时可能出现额外突发。该依赖熔断与后端 Service 熔断是两套独立机制。

## 状态保留生命周期与 Redis 时间源同步

1. **状态保留时长（TTL）**：本机限流器缓存与 Redis 存储状态不仅考虑窗口周期，还综合考虑令牌补满时间（`burst / fill_rate`），统一设定为 `max(600s, max(window, fill_time) * 2)`。对于小数额度长窗口（如 `rate: 0.1, window: 1h`，需 10 小时补满），状态保留时长达到 20 小时（72000s），彻底避免闲置提前清理导致的额度重置。
2. **Redis 统一时间源与集群路由**：
   - Redis 分布式滑动日志与限流脚本内部直接调用 `redis.call('TIME')` 获取统一的服务器时间戳，消除多网关节点间服务器本地时钟漂移（Clock Skew）造成的放行偏差。
   - 固定窗口的 Lua 脚本将完整窗口 key 显式作为 `KEYS[1]` 传入，完全兼容 Redis Cluster 分片路由。
3. **算法切换与并发热更新安全**：Redis 存储键统一采用 `gate:ratelimit:<algo>:<window_ms>ms:<key>` 命名空间隔离。在热更新中将算法或窗口修改时，各算法使用完全独立的 Redis 键空间，杜绝算法切换复用旧键引起的状态冲突。并发热更新时通过键级串行化保证全局只初始化单个新桶实例。

## 同时限制并发请求

```yaml
site: api.example.com
/upload:
  proxy: localhost:8080
  rate_limit: {rate: 10, key: ip}
  limit_conn: 20
  limit_conn_key: ip
```

`rate_limit` 控制吞吐，`limit_conn` 控制在途请求数。并发超限返回 **503** 和 `Retry-After: 5`。更多上游保护配置见 [熔断](../09-advanced/circuit-breaker.md)。


## 注册服务的限流与熔断

在 orders 服务的每个实例上注册相同的资源标签。限流按客户端 IP，在一分钟滑动日志窗口内最多放行 100 次请求；熔断按后端地址分别统计最近 30 秒完成的调用，至少 20 个样本且失败率达到 0.5 时打开。限流 window 接受时长（1m）或整数毫秒；熔断 window 使用整数秒（30）。实例注销在发现更新到达网关后才从候选集中移除，传播期间的调用仍可能失败；后端实际失败仍应计入熔断。不要混用命名资源和快捷标签。

```properties
litegate.http.routers.orders.match.hosts=api.example.com
litegate.http.routers.orders.match.path_prefix=/orders
litegate.http.routers.orders.service=orders
litegate.http.routers.orders.middlewares=orders-limit
litegate.http.middlewares.orders-limit.ratelimit.qps=100
litegate.http.middlewares.orders-limit.ratelimit.key=ip
litegate.http.middlewares.orders-limit.ratelimit.algorithm=sliding_window_log
litegate.http.middlewares.orders-limit.ratelimit.window=1m
litegate.http.services.orders.circuitbreaker.enabled=true
litegate.http.services.orders.circuitbreaker.strategy=failure_rate
litegate.http.services.orders.circuitbreaker.window=30
litegate.http.services.orders.circuitbreaker.minimumrequests=20
litegate.http.services.orders.circuitbreaker.failureratio=0.5
```

通过 MCP 生成时，先读取 `get_config_guide(topic="traffic")`，再运行 `preview_service_tags`：修复所有 error，确认 warning 后应用。YAML 配置先运行 `validate_site_config`，再运行 `save_site_config`。


## 大文件传输与请求体保护

`rate_limit` 限制请求次数；`bandwidth` 限制上传、下载的字节速率。普通代理和文件响应保持流式处理，不会把整个文件放进内存。

全局配置（`config.yaml`）：

```yaml
http:
  max_request_body_size: 67108864 # 默认 64MiB；0 表示不限大小
  body_buffer_budget: 67108864   # 默认 64MiB；0 使用默认预算
  bandwidth:
    total_upload: 20971520       # 当前进程所有路由合计 20MiB/s
    total_download: 52428800     # 当前进程所有路由合计 50MiB/s
```

站点配置：

```yaml
site: files.example.com
max_request_body_size: 1048576 # 站点默认 1MiB
bandwidth:
  total_download: 20971520    # 本站所有路由合计 20MiB/s

/upload:
  max_request_body_size: 4294967296 # 本路由允许 4GiB；显式 0 表示不限大小
  bandwidth:
    key: ip
    upload: 2097152               # 同一 IP 的并发上传合计 2MiB/s
    download: 4194304             # 同一 IP 的并发下载合计 4MiB/s
    total_upload: 10485760        # 本路由所有客户合计 10MiB/s
  limit_conn: 4
  limit_conn_key: ip
  proxy: http://127.0.0.1:8080

/:
  serve: ./public
```

所有速率使用整数，单位为 **字节/秒**，0 关闭该项限制。`key` 默认 `ip`，采用 LiteGate 已解析的可信客户端 IP，不直接相信客户端提交的转发头；`global` 让 `upload` / `download` 在该配置层所有请求之间共享。每个方向独立计量。同一 IP 的多个连接共享额度；IP 相同的 NAT 用户也共享额度。

全局、站点、路由额度同时生效。站点层额度跨该站点所有路由共享，路由层跨该路由所有连接共享。采用令牌桶，初始突发最多 32KiB（低于 32KiB/s 时最多一秒额度）；不能把它理解成每一毫秒都严格匀速。等待会响应请求取消和截止时间。限速增加传输时长，代理超时需要与文件大小和速率匹配；结合 `limit_conn` 限制长时间占用的请求。

请求体大小按“路由显式值 → 站点正数值 → 全局值”选择。站点的 0 继承全局；路由的显式 0 覆盖为不限大小。已知长度超限时不读取 Body，立即返回 413；chunked、未知长度请求在读取过程中按实际字节数限制。流式上传超限前的部分数据可能已经到达后端，后端需要自行保证失败上传的清理和提交原子性。响应已经开始发送后才发生的超限无法改写先前的状态码。

重试缓存只读取已知长度且小于 1MiB 的请求；大文件和未知长度请求保持流式转发，跳过重试和镜像。`disable_chunked` 需要缓存，仍限制为 2MiB，不适用于大文件上传。命名镜像中间件有独立的 4MiB 上限。

`body_buffer_budget` 是当前进程代理重试、`disable_chunked` 和命名镜像缓存的共享预算，按读取上限的三倍预留，覆盖缓冲区增长。异步重放或镜像完成后才释放预留。预算不足时跳过可选的重试缓存或镜像；必须缓存的 `disable_chunked` 返回 503。该预算不是整个进程的 RSS 上限，连接缓冲区、IDS、响应缓存和插件仍有各自的资源开销。

带宽限速适用于普通 HTTP 上传、代理响应、静态文件及缓存命中响应；下载按压缩后 HTTP Body 的字节数计量，不包括 TLS、HTTP 头等协议开销。WebSocket、CONNECT 和其他劫持连接的隧道数据不在本功能范围内。第一版额度仅在本实例共享，多实例不会共享带宽额度。

限速状态在路由重建后复用。空闲客户键五分钟后回收，当前进程最多保留 10,000 个客户键和 4,096 个配置层；达到容量上限返回 503 和 `Retry-After: 60`，避免无界增长。

升级后默认的 64MiB 请求体上限会影响未设置上限的大上传接口，请为这些路由显式配置合适的大小。
