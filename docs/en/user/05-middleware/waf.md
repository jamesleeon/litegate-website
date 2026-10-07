# WAF (Web Application Firewall)

LiteGate includes a lightweight **Web Application Firewall (WAF)** that inspects requests at the edge and blocks common exploits before they reach your backend. It is configured **on a route's `action`**.

---

## 1. Detected Threat Patterns

By default the WAF scans for and can block these patterns:

- **SQL Injection (SQLi)**: database keywords such as `SELECT`, `UNION`, `DROP`, or inline comments.
- **Cross-Site Scripting (XSS)**: injection vectors such as `<script>`, `onerror`, `onload`, or `javascript:` pseudo-protocols.
- **Path Traversal**: payloads such as `../`, `..\\`, or requests targeting `/etc/passwd`.
- **OS Command Injection**: shell keywords such as `eval()`, `exec()`, `sh -c`, or redirection operators.

---

## 2. Configuration

Add a `waf` block under the route's `action`:

```yaml
routes:
  - name: app
    match:
      path_prefix: /
    action:
      type: proxy
      upstream:
        - "localhost:8080"
      waf:
        enabled: true
        block_mode: true       # true = reject with 403; false = log/metric only
        sensitivity: medium    # low | medium | high
```

| Field | Type | Purpose |
| --- | --- | --- |
| `enabled` | bool | Turn the WAF on for this route. |
| `block_mode` | bool | `true` rejects matching requests with `403`; `false` only logs/records metrics (audit mode). |
| `sensitivity` | string | Detection aggressiveness: `low`, `medium`, or `high`. |

---

## 3. Detection Response

When `block_mode: true` and a threat is detected:

1. The client receives an HTTP **`403 Forbidden`**.
2. The gateway records the detection in logs and metrics for monitoring.

With `block_mode: false`, requests are not blocked — detections are only logged/recorded, which is useful for tuning before enforcement.

---

## 4. Best Practices

1. **Roll out in audit mode first**: run with `block_mode: false` for a while to find false positives, then switch to `block_mode: true`.
2. **Tune sensitivity**: start at `medium`; raise to `high` for sensitive endpoints, lower to `low` if legitimate traffic trips the rules.
3. **Combine with rate limiting**: pair the WAF with [rate limiting](./rate-limit.md) to throttle automated scanners at the edge.
