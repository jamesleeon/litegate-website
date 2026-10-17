# Cookbook: Common Scenarios

Don't want to read the field reference? Find the recipe closest to what you need, copy it, and change the domain and addresses.

Every recipe is a complete site file followed by "send this request → get this result". **The recipes are executed one by one by automated tests** (`internal/router/cookbook_test.go`), so the docs and the program behave the same.

## I want to…

| I want to… | See |
|---|---|
| Forward a domain to one backend | [Reverse proxy one backend](01-basics.md#1-reverse-proxy-one-backend) |
| Load-balance several backends and drop failed nodes | [Load balancing + health checks](01-basics.md#2-load-balancing--health-checks) |
| Host a static website | [Static website](01-basics.md#3-static-website) |
| Serve by IP + port without a domain | [Serve by port only](01-basics.md#4-serve-by-port-only-any-host) |
| Enable HTTPS and redirect HTTP to it | [Enable HTTPS](01-basics.md#5-enable-https) |
| Health check endpoint, maintenance page | [Respond directly](01-basics.md#6-respond-directly-health-checks-maintenance-pages) |
| Deploy a Vue / React frontend + backend API | [SPA + API](02-paths.md#1-spa-frontend--backend-api) |
| Send different paths to different services | [Split by path](02-paths.md#2-split-backends-by-path) |
| Public path differs from backend path | [Strip or replace a prefix](02-paths.md#3-strip-or-replace-a-prefix) |
| Accept both `/GoApi` and `/goapi` | [Case-insensitive paths](02-paths.md#4-case-insensitive-paths) |
| Redirect www to the apex, old URLs to new ones | [Redirects](02-paths.md#5-redirects) |
| Match one exact path, split by method | [Exact paths and complex conditions](02-paths.md#6-exact-paths-and-complex-conditions) |
| Block scanner requests like `/xmlrpc.php`, `*.sql` | [Named matchers](06-matchers.md#1-block-scanners-split-writes-from-reads) |
| Give a complex condition a name | [Named matchers](06-matchers.md) |
| Send traffic with a given header to a canary | [Combined conditions](06-matchers.md#2-writing-conditions) |
| Let a frontend call the API cross-origin | [CORS](03-governance.md#1-enable-cors-for-an-api) |
| Add security response headers, pass headers to the backend | [Request / response headers](03-governance.md#2-security-response-headers--headers-for-the-backend) |
| Stop an API from being flooded | [Rate limiting](03-governance.md#3-rate-limiting) |
| Rate-limit a login API per IP | [Per-IP rate limiting](03-governance.md#3-rate-limiting) |
| Remove `Server` and stop forged identity headers | [Delete request / response headers](03-governance.md#31-hide-backend-details-block-forged-identity-headers) |
| Allow the admin area only from the internal network | [IP allow list](03-governance.md#4-admin-area-from-the-internal-network-only) |
| Add unified login to apps that have none | [Authelia / Forward Auth](../05-middleware/forward-auth.md) |
| Share one policy across several APIs | [Snippets](03-governance.md#5-share-one-policy-across-apis-snippets) |
| Frontend from files / KV, backend from service discovery | [Discovery + site file merge](05-discovery.md) |
| Don't return the SPA index when the API service is down | [Placeholder route](05-discovery.md#2-keep-the-spa-from-swallowing-api-requests-when-the-service-is-down) |
| A file browser that requires login to browse, preview and download | [File browser + SSO](07-file-browser.md) |
| A load error I don't understand | [Common errors](04-pitfalls.md) |

## Cheat sheet

```text
site: domain | :port | domain:port   site (https is off by default; write https: true when needed)
proxy / file_server / spa / respond / redirect   actions, exactly one per route
/path:   prefix match by path segment   ~/path:   same, case-insensitive
routes: [{match: {...}, ...}]      exact paths, methods, headers and other conditions
matchers: {name: {...}}            name a condition; routes write match: "@name" (quotes required)
cors / rate_limit / ip_restriction / request_headers / response_headers / strip_prefix
                                   governance, written next to the action
snippets: + import:                reuse governance within a file
```

For every field, see the [site configuration reference](../03-configuration/site-config.md).
