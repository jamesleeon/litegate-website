# WebDAV Action (File Management Service)

LiteGate features an integrated high-performance WebDAV engine, enabling you to mount designated directories on your server directly as network drive shares. It supports cross-platform access (Windows, macOS, Linux) and integrates seamlessly with edge-level authentication pipelines.

---

## 1. Basic WebDAV Configuration

```yaml
domain: cloud.example.com
routes:
  - name: my-storage
    match:
      path_prefix: /dav
    action:
      type: webdav
      root: "/data/shared"   # Physical host directory exposed as WebDAV
      strip_prefix: "/dav"   # CRITICAL: Always strip the path prefix matches, otherwise WebDAV queries will fail
```

---

## 2. Permissions and Security Rules

> [!IMPORTANT]
> **Production Best Practice**: In production, always wrap your WebDAV actions inside an `authentication` middleware pipeline to prevent unauthorized file leaks or mutations.

```yaml
domain: cloud.example.com
routes:
  - name: dav-private
    match:
      path_prefix: /
    action:
      type: webdav
      root: "./private-data"
      auth:
        type: basic
        realm: "Private Storage"
        users:
          alice: "<sha256-hash>"     # generate with: litegate -hash "your-password"
        permissions:
          alice: "rw"                # rw (read-write) or ro (read-only)
```

---

## 3. Mounting WebDAV to Operating Systems

### Windows (File Explorer)
1. Open **This PC**, then select **Map network drive** at the top panel.
2. In the folder path input, enter the endpoint: `https://cloud.example.com/dav` (or your mapped directory path).
3. If protected by an authentication middleware, check **Connect using different credentials** and enter your credentials.

### macOS (Finder)
1. Open Finder, then press `Cmd + K` (or select **Go > Connect to Server...**).
2. Enter the target server URL: `https://cloud.example.com/dav` (HTTPS is highly recommended).
3. Click **Connect** and input your authentication username and password when prompted.

---

## 4. Troubleshooting & FAQ

### Unable to Mutate, Delete, or Rename Files?
- **Host Permissions**: Ensure that the process owner running LiteGate has read/write filesystem permissions on your configured `root` directory.
- **Prefix Alignment**: Check that your `strip_prefix` configuration is aligned and correctly matches the incoming routing path.

### Large File Uploads Timing Out?
- Adjust the global configuration network parameters: `http.write_timeout`.
- If running LiteGate behind a reverse proxy (e.g., Nginx), adjust client body size limits (such as Nginx's `client_max_body_size`).

---

## Further Reading
- [Configuring Basic Auth Pipelines](../05-middleware/authentication.md)
- [Serving Assets via the Serve Action](./serve.md)
