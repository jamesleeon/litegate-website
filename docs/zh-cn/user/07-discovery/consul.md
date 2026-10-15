# Consul 服务发现

先在全局 config.yaml 配置服务目录，再在站点 YAML 中通过 discovery.name 引用注册服务。注册服务不等于必须由标签生成路由；可以使用下面的显式 YAML 路由，或使用资源标签生成路由。

```yaml
service_discovery:
  catalogs:
    - enabled: true
      provider: consul
      url: "http://127.0.0.1:8500"
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
