# Service Registration and LiteGate Tags

Where to put tags in each registry. See the [Service Tags Guide](user/03-configuration/tag-dsl.md) for how to write them and the [Service Tag Reference](user/03-configuration/tag-reference.md) for every tag.

## Two kinds of tags

| Kind | Example | Across instances |
| :--- | :--- | :--- |
| Routing and resource tags | `litegate.http.host=orders.example.com`, `litegate.http.services.orders.timeout=30s` | Must be identical |
| Instance tags / metadata | `version=1.0.0`, `sid=c1`, `litegate.instance.weight=2` | May differ |

A Service selector matches the metadata an instance reports (such as `sid=c1`). When the registry cannot report metadata, write `litegate.instance.labels.sid=c1` instead.

## The simplest registration

Most services need a single tag:

```properties
litegate.http.host=orders.example.com
```

It forwards every request for `orders.example.com` on ports 80 and 443 to this service. For timeouts, retries, several routes and so on, use named resources:

```properties
litegate.http.routers.orders.match.hosts=orders.example.com
litegate.http.routers.orders.match.path_prefix=/api
litegate.http.services.orders.timeout=30s
litegate.http.services.orders.healthcheck.path=/healthz
```

## Where to write them

| Registry | Location | Notes |
| :--- | :--- | :--- |
| Litemesh | Service `meta` | Key/value pairs |
| Consul | Service `Meta`, or `key=value` entries in `Tags` | Both are read |
| Docker / Swarm | Container or service labels | Any `litegate.*` label opts in; `litegate.enable=false` opts out explicitly |
| Kubernetes | Service annotations; the Service needs the label `litegate.io/expose=true` | Write `litegate.*` directly, or the shorthands `litegate.io/host`, `litegate.io/path`, `litegate.io/prefix`, `litegate.io/strip-path`, which map to the shortcut |

Consul example:

```json
{
  "ID": "orders-1",
  "Name": "orders",
  "Port": 8080,
  "Meta": {
    "litegate.http.routers.orders.match.hosts": "orders.example.com",
    "litegate.http.routers.orders.match.path_prefix": "/api",
    "litegate.http.services.orders.healthcheck.path": "/healthz",
    "version": "1.0.0",
    "sid": "c1"
  }
}
```

Docker example:

```yaml
services:
  orders:
    image: orders:1.0
    labels:
      - "litegate.http.host=orders.example.com"
```

## Before going live

1. Every instance of a service carries identical routing and resource tags; values that differ per instance must be instance tags.
2. Never mix the 4 shortcut keys with named resources such as `litegate.http.routers.*`.
3. Confirm there are no diagnostics on the dashboard's service tag page or with MCP `preview_service_tags`.
