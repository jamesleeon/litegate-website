# Circuit Breaker

LiteGate features an enterprise-grade Circuit Breaker middleware built on the highly efficient [Sony gobreaker](https://github.com/sony/gobreaker) library. When downstream microservices undergo persistent performance degradation or outages, the circuit breaker intercepts cascading failures by immediately failing fast at the edge layer, protecting the rest of your system architecture.

---

## 1. How It Works

The circuit breaker maintains a state machine with three distinct runtime phases:

```
Closed (Normal) ── Consecutive Failures >= Threshold ──> Open (Tripped)
      ▲                                                      │
      │                                                Cooldown Timeout
      │                                                      ▼
   Success ────────────────────────────────────────── Half-Open (Probing)
```

- **`Closed` (Normal Operation)**: The circuit is healthy. All ingress traffic is forwarded directly to downstream backends as normal.
- **`Open` (Tripped/Failing Fast)**: Downstream failures have exceeded the defined threshold. The gateway immediately blocks all subsequent requests to this route at the edge, returning `503 Service Unavailable` without placing any load on the backend.
- **`Half-Open` (Probing)**: After the cooldown timeout expires, the gateway enters a probing state. It permits a limited number of test requests (`max_requests`) to pass through. If these requests succeed without error, the circuit breaker resets to the **Closed** state; if any request fails, the breaker trips back to **Open** for another cooldown period.

---

## 2. Configuration Settings

Enable the circuit breaker parameters inside the route's `action` block:

```yaml
routes:
  - name: payment-api
    match:
      path_prefix: /api/payment
    action:
      type: proxy
      upstream: ["10.0.0.5:8080"]
      circuit_breaker:
        enabled: true
        trip_threshold: 3     # Trip breaker after 3 consecutive failures
        timeout: 60           # Wait in the Open state for 60 seconds before probing
        max_requests: 1       # Allow exactly 1 probe request during Half-Open phase
```

---

## 3. Parameter Specifications

| Parameter | Type | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `enabled` | bool | `false` | Activates the circuit breaker for the matched route. |
| `trip_threshold` | int | `3` | The number of consecutive request failures required to trip the breaker from **Closed** to **Open**. |
| `timeout` | int | `60` | The cooldown duration (in seconds) that the breaker remains in the **Open** state before transitioning to **Half-Open** to probe the backend. |
| `max_requests` | int | `1` | The maximum number of concurrent probe requests permitted to pass through when the breaker is in the **Half-Open** state. |

---

## 4. Production Best Practices

1. **Prioritize Critical APIs**: Deploy circuit breakers on high-risk, critical paths such as payment processing, checkout, and inventory endpoints to isolate downstream microservice failures.
2. **Set Sensible Failure Thresholds**: Setting `trip_threshold` too low (e.g. `1` or `2`) can cause accidental triggers due to transient network spikes. We recommend setting this parameter to `3` or `5`.
3. **Synergy with Health Checks**: Pair the circuit breaker with active gateway `health_check` routines. While the circuit breaker immediately intercepts incoming traffic to prevent request queues from back-pressuring, active health checks can independently verify upstream node recovery.
4. **Alarms and Telemetry**: Monitor circuit breaker trip events on your Web Dashboard or set up SRE alerts in centralized log aggregators to immediately investigate tripped states.
