# IP Restriction (Access Control List)

`ip_restriction` filters requests by source IP at the edge, letting you build a whitelist (`allow_ips`) or a blacklist (`deny_ips`) of addresses and CIDR subnets.

It is configured at the **site level** (top of the file, applies to the whole host) or at the **route level** (a sibling of `match` and `action`, applies to one route).

---

## 1. Fields

| Field | Type | Purpose |
| --- | --- | --- |
| `allow_ips` | list | Whitelist. If set, only these IPs/subnets are allowed; everything else gets `403 Forbidden`. |
| `deny_ips` | list | Blacklist. Matching IPs/subnets are rejected with `403`; all others pass. |

Both accept exact IPs and CIDR notation (e.g. `192.168.1.0/24`). If both are set, `deny_ips` is evaluated first.

---

## 2. Configuration Examples

### Route-level whitelist (restrict an admin panel)

```yaml
routes:
  - name: admin-panel
    match:
      path_prefix: /admin
    ip_restriction:
      allow_ips:
        - 127.0.0.1
        - 192.168.1.0/24
    action:
      type: proxy
      upstream:
        - "localhost:8080"
```

### Site-level blacklist (block bad actors across the whole host)

```yaml
domain: service.example.com
ip_restriction:
  deny_ips:
    - 1.2.3.4
    - 5.6.7.0/24
routes:
  - name: app
    match:
      path_prefix: /
    action:
      type: proxy
      upstream:
        - "localhost:8080"
```

---

## 3. Client IP Behind Proxies

When LiteGate runs behind a reverse proxy, load balancer, or CDN (Nginx, Traefik, AWS ALB, …), declare the fronting proxy ranges in `config.yaml`, otherwise the filter will see the proxy's IP instead of the real client IP:

```yaml
real_ip:
  trusted_proxies:
    - 10.0.0.0/8
```

---

## 4. FAQ

- **Requests rejected with 403**: expected firewall behavior. To serve a custom page instead, pair this with a `respond` action.
- **Locked yourself out after enabling a whitelist**: double-check your current public IP is included in `allow_ips`.
