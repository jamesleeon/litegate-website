# Respond Action (Raw Responses)

The `respond` action allows LiteGate to return predefined response payloads directly to incoming clients without forwarding traffic to any backend upstreams. This is highly suitable for health check endpoints, API mock testing, maintenance banners, domain validations, and raw metadata serving.

---

## 1. Basic Health Check Pattern

Configure a lightweight status checking endpoint directly at the edge layer:

```yaml
routes:
  - name: health-check
    match:
      path_prefix: /status
    action:
      type: respond
      status: 200
      body: "OK"
      headers:
        Content-Type: text/plain
```

---

## 2. Returning Custom JSON Payloads

```yaml
routes:
  - name: mock-api
    match: { path_prefix: "/api/mock" }
    action:
      type: respond
      status: 201
      body: '{"message": "Mock Response Success", "code": 0}'
      headers:
        Content-Type: application/json
```

---

## 3. Parameter Reference

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `status` | int | **Required**. HTTP status code returned to the client (e.g., `200`, `403`, `503`). |
| `body` | string | **Optional**. Raw body payload string. |
| `headers` | map | **Optional**. Key-value mapping of HTTP response headers written to the client. |

---

## 4. Practical Operational Scenarios

- **Server Maintenance Banners**: When backends undergo planned maintenance, temporarily transition routes to `respond` mode, returning an HTTP `503 Service Unavailable` accompanied by a styled offline banner page or status JSON.
- **Custom Edge 404 Handlers**: Placing a low-priority wildcard route (`/`) configured with a `respond` action at the bottom of route definitions allows you to return friendly edge-level 404 pages.
- **Domain Verification Integrations**: When validating domain ownership for third-party platforms (e.g., SSL providers, WeChat integrations), serve specific validation keys or text files directly.

---

## Further Reading
- [Configuring Reverse Proxy Actions](./proxy.md)
- [Executing HTTP Redirections via Redirect](./redirect.md)
