# Redirect Action (HTTP Redirection)

The `redirect` action enables LiteGate to execute instant HTTP-level redirections directly at the edge layer. It is commonly applied during domain migrations, protocol upgrades (HTTP-to-HTTPS forcing), or routing path restructures.

---

## 1. Domain Migration Pattern

Instantly steer all incoming traffic on an old domain `old.com` permanently to a new domain name:

```yaml
domain: old.example.com
routes:
  - name: domain-migration
    match:
      path_prefix: /
    action:
      type: redirect
      location: "https://new.example.com{path}" # The {path} variable retains the original request path
      status: 301 # HTTP 301 Moved Permanently
```

---

## 2. Enforcing Protocol Upgrades (HTTP -> HTTPS)

Under the hood, enabling the site parameter `force_https: true` compiles down to an automated implicit `redirect` action.

### Manual Configuration Example
```yaml
domain: web.local
routes:
  - name: force-ssl
    match: { path_prefix: "/" }
    action:
      type: redirect
      location: "https://web.local{path}"
      status: 307 # HTTP 307 Temporary Redirect
```

---

## 3. Parameter Reference

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `location` | string | **Required**. Target URL to redirect to. Supports dynamic variables such as `{path}` and `{host}`. |
| `status` | int | **Required**. HTTP status code. Common values: `301`, `302`, `307`, `308`. |

---

## 4. Practical Steering Configurations

### Path Replacements
Redirecting legacy endpoints (such as `/old-api`) downstream to modern ones (e.g., `/api/v2`):
- **Target Value**: `https://{host}/api/v2{path}`
- **Security Check**: Ensure your routing path matching prefix combines logically with variables defined in `target`.

---

## Further Reading
- [Configuring Reverse Proxy Upstreams](./proxy.md)
- [Utilizing Redirects in Routing Priority Pipelines](../02-concepts/routing-priority.md)
