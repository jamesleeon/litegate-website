# Consul Service Discovery

Configure a catalog in global config.yaml, then reference the registered service by discovery.name in a site YAML file. Registration does not by itself require automatic tag routing; use the following explicit YAML route or the resource tag model below.

```yaml
service_discovery:
  catalogs:
    - enabled: true
      provider: consul
      url: "http://127.0.0.1:8500"
```

Site YAML:

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

## Traffic protection on registered services

Register this identical resource tag set on every orders instance. Rate limiting admits at most 100 requests per client IP in a one-minute sliding log window. Circuit breaking tracks completed upstream outcomes independently per backend address over 30 seconds, opening at 20 samples and a failure ratio of 0.5. Rate-limit window accepts a duration (1m) or integer milliseconds; breaker window is integer seconds (30). Deregistration removes an instance after the discovery update reaches the gateway; requests during that propagation interval can still fail. Backend failures remain breaker samples. Do not mix named resources with shortcut tags.

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

For MCP generation, read `get_config_guide(topic="traffic")`, then run `preview_service_tags`: errors must be fixed; review warnings before applying. For YAML, run `validate_site_config` before `save_site_config`.

The registered service name must match discovery.name. Do not configure the same route in both YAML and automatic tags. Discovery update latency depends on the provider and connection; this guide promises no fixed propagation time or automatic transport encryption. Configure authentication and transport security separately.

[Discovery overview](./overview.md) · [Rate limiting](../05-middleware/rate-limit.md) · [Circuit breaker](../09-advanced/circuit-breaker.md)
