# Circuit Breaker (熔断器)

LiteGate 内置了基于 [Sony gobreaker](https://github.com/sony/gobreaker) 的熔断器，可以在后端服务持续故障时自动切断流量，防止级联失败。

---

## 1. 工作原理

熔断器有三种状态：

```
Closed (正常) → 连续失败达到阈值 → Open (熔断)
                                      ↓ 超时后
                                   Half-Open (半开)
                                      ↓ 探测成功
                                   Closed (恢复)
```

- **Closed**: 正常状态，所有请求照常转发。
- **Open**: 熔断状态，所有请求直接返回 503 Service Unavailable。
- **Half-Open**: 半开状态，允许少量请求通过以探测后端是否恢复。

---

## 2. 启用配置

在路由的 Action 中启用：

```yaml
routes:
  - name: fragile-api
    match:
      path_prefix: /api/payment
    action:
      type: proxy
      upstream: ["10.0.0.5:8080"]
      circuit_breaker:
        enabled: true
        trip_threshold: 3     # 连续失败 3 次后触发熔断
        timeout: 60           # 熔断持续 60 秒
        max_requests: 1       # 半开状态时允许通过 1 个探测请求
```

---

## 3. 参数说明

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `enabled` | bool | `false` | 是否启用熔断器。 |
| `trip_threshold` | int | `3` | 连续失败多少次后触发熔断。 |
| `timeout` | int | `60` | 熔断持续时间（秒），超时后进入半开状态。 |
| `max_requests` | int | `1` | 半开状态时允许通过的探测请求数。 |

---

## 4. 最佳实践

1. **关键 API 优先**: 建议在支付、订单等核心交易链路上启用熔断器。
2. **合理设置阈值**: `trip_threshold` 设置过低可能导致误触发，建议 3-5 次。
3. **配合健康检查**: 熔断器与 `health_check` 配合使用，可以更快地摘除故障节点。
4. **监控告警**: 通过 Dashboard 或日志监控熔断事件，及时排查根因。
