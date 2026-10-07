# Local CA (Self-Signed, Self-Trusted)

The Local CA lets LiteGate **act as its own certificate authority**: it generates a local Root CA and signs leaf certificates on demand for local/internal domains. This is ideal for `localhost`, `*.test`, and internal domains that **public CAs cannot issue for**, giving local development real green-lock HTTPS. Equivalent to Caddy's `tls internal`.

> Difference from ACME / On-Demand TLS: ACME certs are issued by public CAs (Let's Encrypt, etc.) and trusted by browsers automatically; Local CA certs are self-signed, so you must **import its Root CA into the system/browser trust store once** to avoid warnings.

---

## 1. Enabling

In `config.yaml`:

```yaml
tls:
  local_ca: true                       # Enable the Local CA
  local_ca_domains:                    # Domains allowed for signing (optional)
    - ".localhost"
    - ".test"
    - "my-app.internal"
  local_ca_trust: false                # Auto-install into the system trust store (see section 4)
```

Once enabled:

- The first start generates `local_root_ca.crt` and `local_root_ca.key` in the certs directory (default `./certs`);
- When a request hits an allowed domain, the gateway signs that domain's leaf certificate in memory and completes the HTTPS handshake.

---

## 2. Field Reference

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `local_ca` | bool | `false` | Enable on-demand signing via the Local CA |
| `local_ca_domains` | string[] | `[".localhost", ".test"]` | Allow-list of signable domains. A leading `.` means suffix match; no dot means exact match (and its subdomains) |
| `local_ca_trust` | bool | `false` | Whether to auto-install the Root CA into the system trust store **on first generation** |

> `localhost`, `127.0.0.1`, and `::1` are always allowed without explicit configuration.

---

## 3. Domain Allow-List Matching

- `.localhost` — matches any subdomain such as `app.localhost`, `api.localhost`;
- `my-app.internal` — matches `my-app.internal` exactly, and its subdomains like `x.my-app.internal`;
- Domains not in the list are **never** signed by the Local CA (public domains still go through ACME).

This restriction ensures that even if the Root CA private key leaks, the impact is confined to local/internal domains.

---

## 4. Trusting the Root CA

Browsers do not trust a self-signed CA by default. Two ways to make them trust it:

### Option A: Automatic (`local_ca_trust: true`)
LiteGate attempts to install the Root CA into the system trust store **on first generation**:

- Windows: `certutil -user -addstore ROOT` (user store, no admin needed)
- macOS: `security add-trusted-cert` (may prompt for authorization)
- Linux: copies to `/usr/local/share/ca-certificates/` and runs `update-ca-certificates` (requires root)

> ⚠️ **Security note**: installing a Root CA into the system trust store grants it the power to sign certificates for any site. **Only enable `local_ca_trust` on your own development machine** — never on shared/staging/production hosts. This action runs only when the CA is first generated, not on every startup.

### Option B: Manual
Keep `local_ca_trust: false` and import `./certs/local_root_ca.crt` into your system/browser trust store yourself. This is recommended for shared teams as it is more controllable.

---

## 5. Typical Use: Local Development HTTPS

```yaml
tls:
  local_ca: true
  local_ca_domains: [".localhost"]
  local_ca_trust: true        # Dev machine only
```

```yaml
# sites/app.localhost.yaml
site: https://app.localhost
proxy: 127.0.0.1:3000
```

Then `https://app.localhost` is trusted HTTPS with no certificate warning.

---

## Security Notes

- The Root CA private key is stored at `./certs/local_root_ca.key` with `0600` permissions — do not leak it or commit it to a repository.
- Signing is protected by a **rate limit (5/s)** and **cache eviction**, preventing CPU/memory exhaustion from many distinct SNI values.
- The Local CA is for local/internal use only; for public-facing sites use [Auto-Cert (ACME)](./auto-cert.md) or [On-Demand TLS](./on-demand-cert.md).

---

## Further Reading
- [Auto-Cert](./auto-cert.md)
- [On-Demand TLS](./on-demand-cert.md)
