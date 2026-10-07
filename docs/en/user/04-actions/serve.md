# Serve Action (Static File Serving)

The `serve` action represents LiteGate's built-in high-performance static resource and file hosting engine. It natively accommodates routing requirements for modern frontend frameworks (such as Vue, React, Next.js, and Svelte) while incorporating optimized content compression and browser caching pipelines.

---

## 1. Basic Configuration

To bind a target domain's root path directly to a physical host directory:

```yaml
action:
  type: serve
  root: "./www/dist"      # Physical path containing static assets
  index: "index.html"      # Fallback default entry index file
  compress: true           # Activates intelligent Gzip/Brotli compression
```

---

## 2. Modern Frontend SPA Support (Single Page App)

In React, Vue, or Angular applications, virtual client-side paths (e.g., `/user/profile`) do not map to physical files on the disk. By declaring the `spa` parameter, LiteGate intercepts 404 queries, falling back execution to the entrypoint `index.html` where client-side routing grids take over.

```yaml
action:
  type: serve
  root: "./my-app/build"
  index: "index.html"
  spa: true                # Critical: activates SPA router integration and 404 fallback steering
```

---

## 3. Advanced Configurations

### Browser Cache Policies
Direct browser caching periods by declaring:
```yaml
  cache_control: "public, max-age=3600" # Sets standardized Cache-Control headers
```

### Intelligent Content Compression
With `compress: true`, LiteGate negotiates Zstandard, Brotli, or Gzip using the client's `Accept-Encoding` quality values. A fresh `.zst`, `.br`, or `.gz` sidecar is served when available; otherwise dynamic compression is used. Sidecars are not served when compression is disabled.

### Directory Browsing

Directory listings are disabled by default. Enable them explicitly for a download directory:

```yaml
action:
  type: serve
  root: "./downloads"
  browse: true
```

Use the dedicated `list` action when you need a customized listing page.

### Sandbox Path Protections & Security
The `serve` engine confines all opens to the configured root, including through symbolic links. Hidden paths such as `.git` and `.env` are unavailable by default, while `.well-known` remains available for ACME. `index` and `not_found_file` must be relative paths inside the root.

Static serving accepts only `GET`, `HEAD`, and `OPTIONS`; other methods return `405 Method Not Allowed`.

---

## 4. Practical Implementation: Hugo Static Blogs

```yaml
domain: blog.example.com
routes:
  - name: blog-content
    match:
      path_prefix: /
    action:
      type: serve
      root: "/opt/hugo-output"
      index: "index.html"
      compress: true
```

---

## 5. try_files

`try_files` tries a list of candidates in order, serving the first physical file that exists; if none exist, the last entry is used as a **fallback target** via an internal redirect. This is the standard pattern for PHP front controllers (WordPress/Laravel clean URLs) and any case where unknown paths should route to an entry script.

```yaml
action:
  type: serve
  root: "/var/www/html"
  try_files:
    - "{path}"            # first try the physical file for the request path
    - "/index.php"        # none exist -> fall back to the entry script (internal redirect)
```

- **Placeholders**: `{path}` / `{uri}` expand to the current request path.
- Leading entries are checked as **regular physical files**; directories do not count as file matches. If the **last entry begins with `/`** it is used as a fallback URI via an internal redirect (which re-runs route matching and can hit, e.g., a FastCGI route for `/index.php`). Internal redirects preserve the client-visible URI and query string for front controllers such as WordPress and Laravel.
- **Loop protection**: more than 5 internal redirects returns `508 Loop Detected`, preventing infinite loops.

> For a simple SPA fallback, `spa: true` is enough; `try_files` is for the more general "clean URL → entry script" pattern.

---

## Further Reading
- [Configuring SSL Certificates & HTTPS Forcing](../06-certificates/auto-cert.md)
- [Exposing Documentation Portals via Markdown](./markdown.md)
