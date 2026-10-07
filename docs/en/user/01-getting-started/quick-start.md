# Quick Start

This guide will help you spin up LiteGate and configure your first site in 5 minutes.

## Prerequisites

- LiteGate installed ([Installation Guide](./installation.md)).
- A usable domain name (for HTTPS testing; you can use `localhost` for local tests).

---

## Step 1: Zero-Config Startup

LiteGate supports plug-and-play out of the box. Run directly in your terminal:

```bash
litegate
```

You should see output similar to the following:
- `INFO: HTTP Server listening on :80`
- `INFO: Loaded 0 sites from ./sites`

> The Dashboard is **off by default**. To enable it, set `dashboard.enabled: true` in `config.yaml` (default port `9999`).

---

## Step 2: Create Your First Site (Hello World)

Create a directory named `sites` in the current folder, and create `hello.yaml` within it:

```bash
# Create directory and write the YAML configuration
mkdir -p sites
```

Write the following to `sites/hello.yaml`:

```yaml
domain: localhost
routes:
  - name: welcome
    match:
      path_prefix: /
    action:
      type: respond
      status: 200
      body: "Hello, LiteGate! Your gateway is ready."
      headers:
        Content-Type: text/plain; charset=utf-8
```

**LiteGate automatically detects file changes and loads configurations in real-time, without requiring any restart.**

---

## Step 3: Test Access

Access the site via `curl` or your browser:

```bash
curl http://localhost/
# Expected output: Hello, LiteGate! Your gateway is ready.
```

---

## Step 4: Configure Static File Hosting (SPA)

Assuming you have a frontend project built in a `dist` directory:

```yaml
# sites/web.yaml
domain: web.local
routes:
  - name: frontend
    match:
      path_prefix: /
    action:
      type: serve
      root: ./dist
      index: index.html
      spa: true            # Supports Single Page Application (SPA) routing fallbacks
      compress: true       # Enables Gzip/Brotli compression
```

---

## Step 5: Reverse Proxy to a Backend Service

Forward incoming requests to a Go or Java backend running on port `8080`:

```yaml
# sites/api.yaml
domain: api.example.com
routes:
  - name: user-service
    match:
      path_prefix: /api/v1
    action:
      type: proxy
      upstream: ["localhost:8080"]
      strip_prefix: true # Strips the /api/v1 prefix before forwarding the request
```

---

## Step 6: Enable Automatic HTTPS

As long as your machine has a public IP address and the domain name points to this machine, automatic HTTPS only takes one line of configuration:

```yaml
domain: example.com
force_https: true # Automatically requests SSL certificates and redirects all HTTP traffic to HTTPS
routes:
  - name: secure-app
    match:
      path_prefix: /
    action:
      type: proxy
      upstream: ["localhost:3000"]
```

---

## Next Steps

- Understand the [Core Concepts of Sites and Routes](../02-concepts/sites-and-routes.md).
- Discover the [Multiple Action Types](../README.md#4-action) (e.g., WebDAV, Markdown Rendering).
- Add [Authentication Protection](../05-middleware/authentication.md) to secure your APIs.
