# Service Discovery + Site Files: Automatic Merge (Hybrid)

A backend registers with litemesh / Consul carrying tags such as:

```text
litegate.http.host=stock.example.com
litegate.http.pathprefix=/apiv2
```

LiteGate then generates an `/apiv2` route for `stock.example.com`. If `sites/` also has a site file for the **same domain**, the routes from both are merged into one site (shown as Hybrid in the Dashboard) with no extra configuration.

There are only three merge rules:

1. **Longer paths win.** The catalog's `/apiv2` is more specific than the file's `/`, so `/apiv2/...` goes to service discovery and everything else to the file.
2. **For the same path, the file wins.** If the file also defines `/apiv2`, the catalog's `/apiv2` does not take effect (the status page reports it as shadowed).
3. **When every instance goes away, the catalog route is removed** and requests fall back to the file's routes.

---

## 1. Frontend (KV publishing) + backend (service discovery)

Frontend assets are published through KV and backend API instances register themselves. The site file only describes the frontend:

<!-- case: hybrid-kv-spa -->
```yaml
site: stock.example.com
spa:
  root: /home/litegate/www/stock
  kv_mode: true                          # sync the frontend bundle from KV
  kv_provider: litemesh                  # litemesh / consul / http
  kv_key: litegate/config/front/stock
  keep_versions: 3                       # local versions to keep
```

Site files already using the legacy format (`domain:` + `routes:`) remain supported and compile to the same routes as above; switching formats does not require republishing the frontend bundle.

---

## 2. Keep the SPA from swallowing API requests when the service is down

The configuration above has a trap: when **all** `stock` instances deregister (mid rolling deploy, a crash), the `/apiv2` route disappears and `/apiv2/quote` falls through to the SPA fallback, returning `index.html` with **200**. The frontend then fails parsing HTML as JSON, with an error unrelated to the real cause.

Add a placeholder route with priority -1: it yields to the catalog route while the service is online and returns a clear 503 when it is not.

<!-- case: hybrid-placeholder -->
```yaml
site: stock.example.com
/apiv2:
  priority: -1             # below catalog routes (default 0); only applies when the service is absent
  respond:
    status: 503
    content_type: application/json
    body: '{"error":"service unavailable"}'
spa: ./dist
```

```check
# While the service is not registered
GET http://stock.example.com/apiv2/quote     => 503 "service unavailable"
GET http://stock.example.com/settings        => 200 "<h1>dist</h1>"
```

Once the service registers, `/apiv2/quote` is forwarded to its instances by the catalog route; when all instances leave again, it returns to 503. This switch is covered by the test `TestHybridPlaceholderYieldsToCatalogRoute`.

> Without `priority: -1`, the file wins on the same path and the catalog route never takes effect.

---

## 3. Do site file settings apply to catalog routes?

| Written at the top of the site file | For catalog routes |
|---|---|
| `https: true` | Applies (either side enabling it redirects the whole site to HTTPS) |
| `ip_restriction` | Applies (site-level access control) |
| `max_request_body_size`, `error_pages` | Apply |
| `use`, `request_headers`, `response_headers` | **Do not apply**; they cover only routes defined in this file |
| `cors`, `auth`, `rate_limit` and other route governance | **Do not apply**; they belong to specific routes |

Configure auth, rate limits and CORS for catalog routes through service tags; see the [service tag guide](../03-configuration/tag-dsl.md).

---

## 4. When merging does not happen

- **The site has a non-standard port.** `site: stock.example.com:8443` and the tag `stock.example.com` are different sites and are not merged. Ports 80 / 443 are the exception and count as the same site.
- **The domains are not identical.** Merging matches the full domain: `stock.example.com` and `www.stock.example.com` are unrelated, and a wildcard site `*.example.com` does not merge with a service for a specific domain.
