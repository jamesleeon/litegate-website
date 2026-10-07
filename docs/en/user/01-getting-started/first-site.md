# First Site Configuration Example

This guide sets up a gateway entrance for an application: start with the shortest form, then add features to the same file.

## Scenario Description
We want to set up a gateway entrance for `api.example.com` with the following requirements:
1.  **`/api/v1` path**: Routes to a backend microservice.
2.  **Root path `/`**: Hosts a React Single Page Application (SPA).
3.  **HTTPS**: Redirects HTTP to HTTPS.

---

## Shortest Form

Create a file at `sites/api.example.com.yaml`:

```yaml
site: https://api.example.com
/api/v1: 10.0.0.5:8080
spa: /var/www/my-app/dist
```

- `site: https://...` enables the HTTP → HTTPS redirect. Write `site: api.example.com` to serve plain HTTP without redirecting.
- `/api/v1: address` is shorthand for a path-prefix route; it is equivalent to `proxy: address` under that path.
- `spa:` at the site level is the fallback for every other path: it serves static files and falls back to `index.html` for unknown routes.

---

## Adding Features

To balance across several backends or strip the path prefix, turn the path key into a mapping and leave the rest unchanged:

```yaml
site: https://api.example.com
/api/v1:
  proxy: 10.0.0.5:8080, 10.0.0.6:8080   # several addresses, round robin by default
  strip_prefix: true                    # remove /api/v1 before forwarding
spa: /var/www/my-app/dist
```

For authentication, rate limits, CORS, caching, and reusable named services, see [Site Configuration](../03-configuration/site-config.md).

---

## How to Apply this Configuration?

1. Save the configuration above as `sites/api.example.com.yaml`.
2. LiteGate detects the file and hot-reloads it.
3. You can check the configuration first with `litegate -t`.
4. **Verify the console output**:
   - A log line showing the site loaded
   - If the domain resolves to this machine, a log line showing a certificate request for `api.example.com`

---

## Verification Steps

1. **Test API Proxying**:
   Run `curl https://api.example.com/api/v1/health`. It should return a response from your backend.
2. **Test Frontend SPA**:
   Visit `https://api.example.com/` in your browser. You should see your React application.
3. **Test HTTPS Redirection**:
   `curl -I http://api.example.com/` should return a redirect to `https://`.

> The legacy `domain:` format and `.lite.yaml` files still load without migration; use the `site:` format for new configuration.

---

## Next Steps
Next, you can dive deeper into the [detailed concepts of Sites and Routes](../02-concepts/sites-and-routes.md).
