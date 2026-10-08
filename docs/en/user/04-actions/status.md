# Status Action (System Status Dashboard)


The `status` Action enables the gateway to render a premium, responsive system status monitoring dashboard directly to users or administrators. It automatically collects traffic metrics, QPS, latency, live metrics, and historical health status for all sites and proxy routes within the gateway, without the need to deploy complex third-party stacks like Prometheus and Grafana.

It also supports multi-tenant security isolation and structured JSON output for third-party scrapers.

---

## 1. Quick Start

Simply set the route action type to `status` to enable the dashboard on that path:

```yaml
routes:
  - name: "system-status"
    match:
      path: "/status"
    action:
      type: "status" # Set type to status
```

Accessing this route (e.g., `http://example.com/status`) will render the system status dashboard.

---

## 2. Configuration Parameters

The `status` Action offers custom parameters to fine-tune the dashboard title, scope, template, and backend instance visibility:

```yaml
action:
  type: "status"
  title: "LiteGate Platform Status" # Custom dashboard title
  host: "self"                     # "self" to filter by current host, or "*" for all sites
  show_instances: false            # Whether to render detailed backend physical instances
  template: "./site/status.html"   # Optional path to a custom template
  template_root: "./site"          # Optional path to template partials root
  template_debug: false            # Enable debug mode (reload template every request)
  template_production: true        # Enable production mode (cache compiled template)
```

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `title` | string | `"LiteGate System Status"` | Custom title displayed at the top of the status page. |
| `host` | string | `""` (Show All) | Specifies the site domain to monitor. Setting it to `"self"` restricts the metrics to the current host requested (ideal for multi-tenant isolation). You can also provide a specific domain (e.g., `"api.example.com"`). Leave blank (or `"*"` ) to show all sites. |
| `show_instances` | bool | `false` | When true, renders detailed information for backend server instances under proxy routes (requires Litemesh/Consul service discovery). |
| `template` | string | `""` | Optional. Path to a custom HTML template. If blank, LiteGate renders its built-in modern glassmorphism style dashboard. |
| `template_root` | string | `""` | Optional. The root directory for template partials (similar to the `template` action). |
| `template_debug` | bool | `false` | Enable template debugging (disables caching, reloads template on every request). |
| `template_production`| bool | `true` | Enable template production mode (pre-compiles and caches template to bypass disk I/O, boosting concurrent performance). |
| `template_kv_mode` | bool | `false` | Load the custom template from litemesh / Consul KV (instead of local disk). See "Distributed Custom Template" below. |
| `template_kv_provider` | string | `""` | KV provider: `litemesh` or `consul`. |
| `template_kv_prefix` | string | `""` | KV prefix the template partials live under; `template` then holds the main template key suffix relative to this prefix. |
| `template_kv_namespace` | string | `""` | Optional multi-tenant KV namespace isolation; empty uses the client default namespace. |

### 📦 Distributed Custom Template (`template_kv_mode`)

The status page's custom template shares the same loading engine as the [`template` action](./template.md), so it **also supports distributed loading from litemesh / Consul KV**: the template lives in KV, clustered nodes need no local file distribution, compilation is in-memory, changes hot-reload on KV updates, and a failed fetch falls back to the last cached build.

```yaml
action:
  type: "status"
  title: "LiteGate Platform Status"
  host: "self"
  template_kv_mode: true
  template_kv_provider: "litemesh"
  template_kv_prefix: "litegate/tmpl/status-a/"
  template: "status.html"   # main template key suffix relative to the prefix
```

The resource boundaries (≤100 partials / ≤1MB each / ≤10MB total) and the security note (KV write access equals a code-deploy privilege) are the same as the `template` action; in KV mode the file-loading form of `{{ markdown "x.md" }}` is unavailable (inline only).

---

## 3. Multi-Tenant Isolation (`host: "self"`)

In a multi-tenant gateway deployment, you may want to prevent users of Site A from viewing traffic and health statistics of Site B.
By setting `host` to `"self"`:
- The gateway dynamically inspects the `Host` header of the incoming HTTP request.
- The dashboard will **only show metrics associated with that specific domain**.
- Statistics of other sites are completely hidden, maintaining zero-trust isolation.

---

## 4. Backend Instances Visibility (`show_instances: true`)

If a route uses a `proxy` action and resolves targets dynamically via service discovery (such as Litemesh or Consul), it is backed by physical endpoints (IP+Port).
- By default, the public status page only presents route-level aggregated metrics to hide backend physical topology.
- Setting `show_instances` to `true` exposes **individual backend endpoints** under the route dashboard. This reveals their health check status, real-time latencies, and a list of recent request samples, making it ideal for internal troubleshooting dashboards.

---

## 5. Auto-Negotiation JSON API

The `status` page supports built-in content negotiation. When LiteGate detects either of the following, it bypasses HTML rendering and returns **200 OK + `application/json`** structured metrics data:
1. The request query contains `?format=json` (e.g., `/status?format=json`).
2. The request headers contain `Accept: application/json`.

This is useful for scraping metrics with external systems (e.g., Zabbix, PromQL scrapers) or building custom monitoring wallboards.

### Example JSON Output:
```json
[
  {
    "domain": "api.example.com",
    "domain_id": "api_example_com",
    "title": "LiteGate API Gateway",
    "status": "Operational",
    "total_requests": 158249,
    "daily_requests": 1240,
    "error_requests": 2,
    "latency_avg": 12.5,
    "status_dist": {
      "200": 1238,
      "502": 2
    },
    "routes": [
      {
        "route_name": "get-users",
        "requests": 980,
        "errors": 0,
        "latency": 8.4
      }
    ]
  }
]
```

---

## Enable Automatically via Service Tags

Besides a hand-written site config, a Router can set `litegate.http.routers.<name>.observability.status.enabled=true`; use `.path` and `.showinstances` for the related options. See the [Service Tag Reference](../03-configuration/tag-reference.md). The tag form only covers quick enablement; for a custom title / `host: self` / custom template, use the hand-written config described above.

---

## See Also
- [Template Action](./template.md)
- [Service Registration Guide (tag-driven routing)](../../service_registration_guide.md)
- [Metrics observability](../08-observability/metrics.md)
- [Observability Dashboard](../08-observability/dashboard.md)
