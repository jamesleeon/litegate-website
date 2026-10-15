# Litemesh 服务发现

先在全局 config.yaml 配置服务目录，再在站点 YAML 中通过 discovery.name 引用注册服务。注册服务不等于必须由标签生成路由；可以使用下面的显式 YAML 路由，或使用资源标签生成路由。

```yaml
service_discovery:
  catalogs:
    - enabled: true
      provider: litemesh
      url: "http://127.0.0.1:8787"
```

站点 YAML：

```yaml
site: api.example.com
services:
  orders:
    discovery:
      name: orders
    timeout: 5s
    circuitbreaker:
      enabled: true
      strategy: failure_rate
      window: 30
      minimumrequests: 20
      failureratio: 0.5
/orders:
  service: orders
  rate_limit:
    rate: 100
    key: ip
    algorithm: sliding_window_log
    window: 1m
```

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

注册服务名应与 discovery.name 一致。不要同时用 YAML 和自动标签定义相同路由。发现更新时间取决于提供者和连接状态，本文不承诺固定传播时延或自动链路加密；认证和传输安全需要另行配置。

[发现概览](./overview.md) · [限流](../05-middleware/rate-limit.md) · [熔断](../09-advanced/circuit-breaker.md)

## KV 站点热重载排查

直接新增站点时，启用 `litemesh.roles.config_watch`，确认 namespace 和 `keys.config_prefix` 与写入位置一致。站点 key 应是前缀下的直接子项，并以 `.yaml` 或 `.yml` 结尾；不支持嵌套目录。

监听通过 SSE 接收变更。旧格式通知会在约 300ms 后回查 KV，内联值通知直接交给加载器；路由重载在首个触发后的 500ms 窗口内合并事件。这些是合并等待时间，不是端到端延迟保证。回查或快照读取失败会重试，网络、解析和路由构建仍会影响生效时间。证书与 DNS 检查在路由发布后异步执行；新 HTTPS 域名的证书签发仍可能需要额外时间。

日志中查看 `Litemesh KV Config Change Detected`、`Failed to load config from Litemesh KV`、`Litemesh KV event fetch failed, will retry`、`Failed to read published KV snapshot; will retry event` 和 `Hot reload failed`。YAML 校验失败需要修正内容。

若站点前缀下存在 `_release.json`，配置由发布快照管理，独立 YAML key 不再参与运行时加载。通过 Dashboard / 发布流程更新快照；不要删除快照来绕过发布规则。详见 [配置发布控制](../../release_control_guide.md)。

### 区分 KV、路由和 DNS 延迟

- `Litemesh KV Config Change Detected`：网关已收到站点变更。
- `Hot reload completed; routes published`：监听器与路由已更新，`duration` 是本轮重载耗时。
- `Auto DNS Sync: published record`：公网 DNS 提供商已接受对应记录写入。
- `Public DNS sweep completed`：本轮公网 DNS 检查结束；仍需查看失败日志或 DDNS 状态，不能据此认定所有记录都写入成功。

配置 watcher 在 SSE 保持在线时也会每约 30 秒进行一次完整对账，补齐漏通知的新增、更新和删除。该间隔不包含网络与加载耗时。公网 DDNS 同步失败后，除后续重载外，还有每 5 分钟的定期检查；内部 DNS heartbeat 默认每 30 秒刷新，记录 TTL 默认 30 秒。公网提供商的 TTL 不同，例如阿里云／腾讯云写入 A/AAAA 时使用 600 秒。

在域名访问异常时，用网关实际 IP 绕过解析，检查是否返回这个站点预期的内容：

```bash
curl --noproxy "*" --resolve app.example.com:80:192.0.2.10 http://app.example.com/
curl --noproxy "*" --resolve app.example.com:443:192.0.2.10 https://app.example.com/
```

替换域名和 IP；HTTPS 保留证书校验，证书尚未签发时会失败。仅看到通用跳转或默认页面不能证明目标路由正确。若指定 IP 的请求已返回预期内容，而普通域名请求仍异常，继续检查 DNS 解析结果、DNS 提供商记录及代理/CDN。新域名之前的 NXDOMAIN 也可能被缓存，详见 [RFC 2308](https://www.rfc-editor.org/rfc/rfc2308)。重启网关不会清除外部解析器缓存。
