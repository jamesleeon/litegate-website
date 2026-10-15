<!-- GENERATED FILE — DO NOT EDIT.
     Source: internal/configdocs/docs/zh/circuit-breaker.md (package internal/configdocs)
     Regenerate: go generate ./internal/configdocs/...
     Edit the source instead; a drift test fails if this copy is edited directly. -->

# 熔断（V2 配置）

熔断是上游 Service 策略。限流控制进入网关的请求数量；熔断根据后端失败情况，暂时拒绝向故障实例发请求。本文使用 V2 站点与路径路由语法。YAML 的 `services` 是本站点的上游配置段，不要求使用服务注册中心：静态地址使用 `servers`，注册中心上游使用 `discovery`。两种来源都支持同一套熔断策略。

## 连续失败策略（兼容默认配置）

```yaml
site: api.example.com
services:
  payment:
    to: ["http://127.0.0.1:8080", "http://127.0.0.1:8081"]
    circuitbreaker:
      enabled: true
      timeout: 60
      maxrequests: 1
      tripthreshold: 3
/api/payment:
  service: payment
  rate_limit: 100
```

Service 键名为 `circuitbreaker`、`maxrequests`、`tripthreshold`，不使用下划线。路由通过 `service: payment` 引用配置，不需要写旧式 `routes[].action`。配置发现服务时，可将 `servers` 替换为 `discovery: {name: payment}`，二者不能同时配置。详见 [Service 配置](../03-configuration/services.md)。

| 参数 | 默认值 | 说明 |
|---|---|---|
| `enabled` | `false` | 是否启用 |
| `strategy` | `consecutive` | 连续失败策略；`failure_rate` 为窗口失败率 |
| `window` | `30` | 窗口秒数，范围 1–3600，仅窗口策略生效 |
| `minimumrequests` | `20` | 窗口内最少有效调用数，仅窗口策略生效 |
| `failureratio` | `0.5` | 失败比例阈值 (0,1]，仅窗口策略生效 |
| `slowthresholdms` | `0` | 慢调用阈值（毫秒），范围 0–3600000；0 禁用，严格超过阈值计为失败，适用于两种策略 |
| `tripthreshold` | `3` | 触发打开状态的连续失败次数 |
| `timeout` | `60` | 打开状态的持续秒数，不是请求超时 |
| `maxrequests` | `1` | 半开状态最多接受的探测请求数；累计连续成功达到该数后恢复 |

数值参数省略或为 0 时使用默认值。熔断状态保存在每个网关进程内，不通过 Redis 共享。底层按上游地址和熔断参数缓存状态：相同地址及相同参数的路由可以共享熔断器，不同端口分别统计；自定义 DNS 视图也分别隔离。最多缓存 2048 个条目，仅淘汰无有效失败历史且无在途请求的 Closed 条目。如果所有条目都在保护中，新键请求返回 503，直到有可安全淘汰的条目；已有熔断状态保持不变。

## 滑动窗口失败率

静态上游和注册中心上游均可显式选择 `failure_rate`。网关按实例统计最近一段时间内已完成的有效调用，样本数达到下限且失败率达到阈值后熔断。成功调用仍计入分母，不清空窗口内的失败。

### 不使用注册中心：静态上游 YAML

将配置放入站点 YAML 文件。下面的 `payment` 是本站点定义的上游名称，路由通过 `service: payment` 引用它。

```yaml
site: api.example.com
services:
  payment:
    to:
      - "http://127.0.0.1:8080"
      - "http://127.0.0.1:8081"
    timeout: 5s
    circuitbreaker:
      enabled: true
      strategy: failure_rate
      window: 30
      minimumrequests: 20
      failureratio: 0.5
      timeout: 30
      maxrequests: 1
/api/payment:
  service: payment
```

两个地址分别统计调用结果，某个地址熔断不会直接打开另一个地址的熔断器。只有一个后端时，`servers` 只保留一项即可。多个地址需要故障转移时，可另配 `retry: {attempts: 1}`，详见下方重试一节。

`services.payment.timeout: 5s` 是请求超时；`circuitbreaker.window: 30` 是统计窗口秒数；`circuitbreaker.timeout: 30` 是熔断打开后等待探测的秒数。后两项填写整数，不写 `30s`。每个后端在窗口内至少有 20 次有效调用且失败率达到 50%，才会触发熔断；低流量下样本不足时不会打开。

### 使用注册中心：YAML 引用发现服务

将同一份配置中的 `servers` 替换为以下内容，熔断参数保持相同：

```yaml
discovery:
  name: payment
```

`discovery` 位于 `services.payment` 下，与 `servers` 二选一；不能同时填写。注册中心里的服务名称写在 `discovery.name`，可以与本地上游名称不同。

### 使用注册中心：注册标签

参数同样可通过服务注册标签设置：

```text
litegate.http.services.payment.circuitbreaker.enabled=true
litegate.http.services.payment.circuitbreaker.strategy=failure_rate
litegate.http.services.payment.circuitbreaker.window=30
litegate.http.services.payment.circuitbreaker.minimumrequests=20
litegate.http.services.payment.circuitbreaker.failureratio=0.5
```

这个例子在至少 20 次有效调用、失败比例达到 50% 时打开。客户端取消和客户端 `grpc-timeout` 不计入分子或分母，熔断快速拒绝也不计入。网关自身超时、网络错误和配置定义的失败状态码计为失败。每次实际访问上游的重试分别计入对应实例，按完成时间记账；每个网关进程独立统计。

窗口采用固定数量的 64 个时间分片及一个边界分片，内存不随请求量增长。部分过期的分片保留至其中最后一个样本到期，因此旧样本最多多保留不到 `window / 64` 秒（30 秒窗口约 0.47 秒），不会提前丢弃仍在窗口内的样本。空闲时也会在下一次记账或监控快照中清理过期样本。

`failure_rate` 与 `consecutive` 择一，窗口策略下 `tripthreshold` 不参与触发。旧配置未填写 `strategy` 时保持连续失败策略；窗口参数必须配合 `strategy: failure_rate` 使用。半开阶段仍采用有限探测，任一失败重新打开；恢复 Closed 时清空旧窗口，重新收集样本。

注册中心注销实例由服务发现处理，不属于熔断失败样本。熔断用于隔离仍被发现、但实际调用持续异常的实例。

旧式 action / middleware 的对应字段为 `strategy`、`window_seconds`、`minimum_requests`、`failure_ratio`。

## 状态与失败判定

- **Closed**：正常转发；按所选策略满足连续失败阈值或窗口失败率阈值后进入 Open；连续失败策略下成功响应重置连续失败计数。
- **Open**：不向该实例发请求；等待 `timeout` 秒后进入 Half-Open。
- **Half-Open**：接受有限探测请求，额外请求快速拒绝；任一失败重新打开，连续成功达到 `maxrequests` 后关闭。

默认将网络错误和 HTTP 5xx 响应计为失败。触发失败的上游 HTTP 响应仍会传给客户端，例如连续失败阈值为 3 时，第三次 500 会计入熔断并返回原来的 500。后续请求遇到已打开或半开额度耗尽的熔断器才快速拒绝。

客户端取消请求和客户端设置的 `grpc-timeout` 到期不会计为后端失败；这类结果采用中性记账，不计成功或失败，不重置连续失败计数；半开探测取消后释放额度，但不推进恢复。网关自身超时仍计为失败。WebSocket 等 Upgrade 请求的拨号和 HTTP 握手也受熔断保护，已建立隧道中的数据传输不参与统计。这里只统计 HTTP RoundTrip 结果；HTTP 200 中的业务错误、响应体读取错误及 gRPC trailer 状态不属于这里的 HTTP 状态码判定。

## 熔断响应与重试

普通 HTTP 请求在最终错误为熔断快速拒绝时返回 **503 Service Unavailable**；其他上游错误通常返回 502，超时返回 504。原生 gRPC / gRPC-Web 使用对应协议错误响应，熔断快速拒绝为 `grpc-status: 14`。

配置 Service 重试时，网关可以尝试其他实例，因此某个实例熔断不代表整条路由一定返回 503：

```yaml
site: api.example.com
services:
  payment:
    to: ["http://127.0.0.1:8080", "http://127.0.0.1:8081"]
    retry: {attempts: 1}
    circuitbreaker: {enabled: true, timeout: 30, maxrequests: 1, tripthreshold: 3}
/api/payment:
  service: payment
```

熔断快速拒绝没有把请求发到上游，故障转移不增加退避等待；重试仍受实例选择与请求重放规则约束。熔断与健康检查互补，可按需要配置 Service `healthcheck`。

## 自定义失败状态码的兼容写法

当前 Service 的 `circuitbreaker` 支持上表策略与参数。`failure_status_codes` 和 `ignore_status_codes` 属于旧式 action 字段，尚未暴露在 Service 上；需要时可在 V2 路由中使用显式 `action` 兼容块：

```yaml
site: api.example.com
/api/payment:
  action:
    type: proxy
    upstream: ["127.0.0.1:8080"]
    circuit_breaker:
      enabled: true
      trip_threshold: 3
      timeout: 60
      max_requests: 1
      failure_status_codes: [500, 502, 504]
      ignore_status_codes: [503]
```

忽略列表优先；配置失败列表后，只有该列表中的 HTTP 状态码计为失败，网络错误仍计为失败。不要把旧式字段名直接放入 Service `circuitbreaker`，也不要在同一路由叠加 Service 熔断和命名熔断 middleware。新配置优先使用 Service。

## 监控与排查

Dashboard 可查看上游熔断状态和失败计数；Prometheus 指标包括 `litegate_circuit_breaker_state`（0 正常、1 半开、2 打开）和 `litegate_circuit_breaker_trips_total`。排查时区分限流 429、并发限制 503、熔断 503 和上游实际返回的 503。搭配 [限流](../05-middleware/rate-limit.md) 控制持续吞吐与突发。

监控快照还提供 `strategy`、`window_seconds`、`minimum_requests`、`failure_ratio`、`window_requests`、`window_failures` 和 `window_failure_ratio`；窗口计数在状态切换后清零。

## 按延迟熔断

Service `circuitbreaker.slowthresholdms` 设置慢调用阈值（毫秒，默认 `0` 禁用，最大 `3600000`）。耗时严格超过阈值的调用，即使返回 HTTP 200，也计为熔断失败；原始响应仍返回客户端。网络错误及失败状态码继续计为失败，同一次调用只计一次。配合 `failure_rate`，按窗口内“失败或慢调用”的合并比例触发熔断：

```yaml
services:
  payment:
    servers: ["http://10.0.0.11:8080", "http://10.0.0.12:8080"]
    retry: {attempts: 1}
    circuitbreaker:
      enabled: true
      strategy: failure_rate
      window: 30
      minimumrequests: 20
      failureratio: 0.5
      slowthresholdms: 500
      timeout: 30
      maxrequests: 1
```

每个实例在窗口内至少完成 20 次有效调用，其中失败或超过 500ms 的调用占比达到 50% 时熔断。冷却 30 秒后允许探测；探测必须成功且不超延迟阈值才能恢复，慢探测会重新打开熔断器。客户端取消及客户端 `grpc-timeout` 仍采用中性记账。

延迟统计从 HTTP RoundTrip 开始到响应头返回，包含连接及等待响应头，不包含响应体读取或已建立的流式连接寿命。它不会中途终止慢请求，需要限制单次请求耗时仍应配置 Service `timeout`。支持 `consecutive` 策略，慢调用此时计入连续失败。

注册中心标签使用 `circuitbreaker.slowthresholdms`；旧式 Action / middleware 使用 `slow_threshold_ms`。监控快照包含 `slow_threshold_ms`，已有失败计数包含慢调用。熔断在发送前快速拒绝；负载均衡仍可能选到该实例，配合重试可尝试其他实例，全部不可用时返回 503。
