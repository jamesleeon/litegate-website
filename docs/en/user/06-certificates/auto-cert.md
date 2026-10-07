# Auto-Cert (Automated Certificate Management)

LiteGate features an integrated high-performance ACME client that orchestrates the automated acquisition, deployment, and renewal of SSL/TLS certificates from trusted certificate authorities (such as Let's Encrypt or ZeroSSL). It serves as the primary component for enforcing secure HTTPS connections across all ingress routes.

---

## 1. Core Capabilities

- **Zero-Touch Renewals**: Certificates are checked daily and renewed when their remaining lifetime is at most `min(renew_days, total certificate lifetime / 3)` (`renew_days` defaults to 10), so short-lived certificates do not enter the renewal window immediately.
- **Multi-CA Support**: Beyond Let's Encrypt, LiteGate supports ZeroSSL, Google Trust Services, and any custom ACME service.
- **Cluster-Wide Sharing**: When operating under Litemesh grid configurations, certificates are persisted centrally in the distributed KV store rather than local drives. All gateway instances share the same certificate pool, preventing duplicate certificate acquisition that could trigger CA rate limits.
- **Flexible Verification Modes**: Supports straightforward **HTTP-01** challenges (requiring port 80 access), **TLS-ALPN-01** challenges (port 443, no port 80 or DNS credentials needed), and **DNS-01** challenges (enabling wildcard certificate acquisition).

---

## 2. Configuration Options

### HTTP-01 Challenge (Single Hostnames)
Best suited for deployments where port 80 is exposed publicly on the internet.

```yaml
domain: example.com
force_https: true # Activating HTTPS forcing implicitly activates Auto-Cert
routes:
  - name: my-app
    match: { path_prefix: "/" }
    action: { type: proxy, upstream: ["localhost:8080"] }
```

### TLS-ALPN-01 Challenge (Port 443, No Port 80 or DNS Needed)
Best suited when inbound port 80 is blocked by ISPs or cloud firewalls, or when you operate a pure HTTPS gateway and do not want to configure DNS provider API credentials. The ACME CA connects directly to port 443 and negotiates the `acme-tls/1` protocol.

```yaml
# config.yaml
auto_cert:
  enabled: true
  email: "admin@example.com"
  default_challenge: "tls-alpn"  # Set default challenge for non-DNS domains: "http" (default) or "tls-alpn"
```

The challenge is chosen per domain as follows: a domain matched by an enabled `dns_providers` entry always uses DNS-01; every other domain uses `default_challenge`. There is no per-domain override between HTTP-01 and TLS-ALPN-01.

> **Notes**:
> - Port 443 on the public host must route directly to LiteGate's HTTPS listener.
> - Per RFC 8737, TLS-ALPN does **not** support wildcard certificates (`*.example.com`). Use DNS-01 for wildcards.

### DNS-01 Challenge (Wildcards)
Best suited for securing wildcard domain subtrees (e.g. `*.example.com`) or environments lacking inbound port 80 routing.

First, register your DNS Provider globally in your `config.yaml`:

```yaml
auto_cert:
  enabled: true
  email: "admin@example.com"
  dns_providers:
    - name: "aliyun"
      type: "aliyun"
      enabled: true
      config:
        access_key_id: "LTAI..."
        access_key_secret: "..."
```

The domain-to-provider mapping lives in `config.yaml` under `dns_providers`:

```yaml
# config.yaml
auto_cert:
  enabled: true
  email: "you@example.com"
  dns_providers:
    - name: "aliyun-main"
      type: "aliyun"
      enabled: true
      domains: ["*.example.com", "example.com"]
```

---

## 3. Choosing a Certificate Authority (CA)

Let's Encrypt is used by default. Set `ca_provider` to switch to another authority; LiteGate automatically selects the matching ACME directory URL and stores a separate account key per CA (fully isolated from one another).

```yaml
auto_cert:
  enabled: true
  email: "you@example.com"
  ca_provider: "zerossl"   # letsencrypt(default) / zerossl / google / custom
```

| `ca_provider` | Built-in ACME URL | EAB Required |
| :--- | :--- | :--- |
| `letsencrypt` (default) | `https://acme-v02.api.letsencrypt.org/directory` | No |
| `zerossl` | `https://acme.zerossl.com/v2/DV90` | **Yes** |
| `google` | `https://dv.acme-v02.api.pki.goog/directory` | **Yes** |
| `custom` | Defined by `acme_url` | Depends on the service |

### EAB (External Account Binding)

ZeroSSL and Google Trust Services **require** EAB credentials. Obtain `eab_kid` / `eab_hmac` from the respective console and provide them together:

```yaml
auto_cert:
  enabled: true
  email: "you@example.com"
  ca_provider: "zerossl"
  eab_kid: "your-key-id"
  eab_hmac: "your-hmac-key"
```

> Note: Selecting zerossl/google/gts without EAB credentials will cause a configuration validation error at startup (missing eab_kid or eab_hmac).

### Custom ACME Services

For a private CA or step-ca, use `custom` together with `acme_url` (required):

```yaml
auto_cert:
  enabled: true
  ca_provider: "custom"
  acme_url: "https://ca.internal.example.com/acme/acme/directory"
  acme_ca_cert: "/etc/litegate/private-acme-root.pem"
  acme_headers:
    X-Lito-Token: "your-private-ca-token"
```

> [!TIP]
> **Custom CA Upgrade Migration Hint**
> - In newer versions, `custom` mode uses a SHA256 hash of the `acme_url` as a unique suffix (e.g., `custom_xxxx`) for CA metadata and account key isolation.
> - Upgrading a cluster from an older version (which used the literal `"custom"` identity) will trigger a CA provider mismatch error (`_cluster_ca_provider` mismatch) on startup.
> - **Solution**: Before upgrading, manually delete the `_cluster_ca_provider` key/file from your storage (Consul/Litemesh or the `_cluster_ca_provider.pem`/`_cluster_ca_provider.key` files inside `certs_dir`). The new version will then rebuild the metadata cleanly on start.
> - **Existing Certificate Re-issuance**: Changing only the `acme_url` will not automatically trigger a forced renewal of existing valid certificates. If you want to force re-issuing all existing certificates under the new custom ACME endpoint, simply delete their old certificate files (e.g., the `example.com.pem` and `example.com.key` files inside `certs_dir` on local disk, or the corresponding domain bundle key in Consul / Litemesh KV) manually while updating the configuration. The gateway will request new certificates on the next run.

---

## 4. Storage Security & Private Key Encryption

By default, locally stored certificates and ACME accounts are written to the directory specified by `certs_dir`:

```text
certs/
├── example.com.pem     # Standard fullchain certificate bundle
└── example.com.key     # Private key file
```

### Security Encryption for ACME Accounts

To prevent ACME registration account credentials from being stored in plaintext or unencrypted format inside shared Consul/Litemesh KV registries, it is highly recommended to configure a symmetric encryption key `storage_secret` in the `auto_cert` block of `config.yaml`:

```yaml
auto_cert:
  enabled: true
  certs_dir: "./certs"
  storage_secret: "a-secure-32-character-long-secret-key-here!" # Must be at least 32 bytes
```

- **Persistent Layer Encryption**: Once `storage_secret` is enabled, the global ACME account registration private key (stored under the key `_acme_account` for Let's Encrypt, or `_acme_account_<provider>` for other CAs such as `_acme_account_zerossl`, isolated per CA) as well as **individual domain certificate private keys** are automatically encrypted using the AES-256-GCM algorithm before being written to shared persistent storage (such as Consul or Litemesh KV registries). The encrypted binary payload starts with a magic header prefix: `LG_ENC_001`.
- **Fail-Closed Protection**: If `storage_secret` is defined but the encryption fails (e.g., due to an inadequate key length), LiteGate enforces a Fail-Closed policy, throwing an error and aborting the save operation rather than falling back to plain storage.
- **Seamless Plaintext Migrations**: If your gateway environment already stores older plaintext ACME keys or domain private keys, configuring `storage_secret` later triggers an automated migration. When LiteGate loads a plaintext file from storage, it encrypts the key immediately in memory and overwrites it in the storage.
- **Local Disk Mirroring and Sync Encryption**: Local disk certificate private key files (`example.com.key`) will remain in plaintext and be protected by strict `0600` permissions (to satisfy TLS handshake performance constraints). However, during certificate sync and push operations (such as `SyncCertificatesToLitemesh`), private keys are automatically encrypted with `storage_secret` before being uploaded to Litemesh KV storage, preventing plaintext private key leakage in the shared KV registry.

---

## 5. Troubleshooting & FAQ

### ACME challenge status is stuck at "Pending"?
1. **Verify Inbound Access (HTTP-01)**: Confirm that the public DNS A-record maps correctly to your gateway and that port 80 is publicly reachable from Let's Encrypt's servers.
2. **DNS Propagation (DNS-01)**: Wait for DNS records to propagate. Some cloud DNS systems require additional latency before TXT records become visible.
3. **CA Rate Limiting**: Let's Encrypt enforces strict weekly limits on duplicate certificate requests. Check server logs to see if a rate limit exception was raised.

### How do I force an immediate certificate renewal?
To force a renewal, physically delete the target domain's certificate files (e.g., `example.com.pem` and `example.com.key` inside `certs_dir` on local disk, or the corresponding domain bundle key in Consul / Litemesh KV) and restart the LiteGate process. The gateway will immediately trigger a new ACME handshake on startup.

---

## Further Reading
- [Configuring Global Auto-Cert Parameters](../03-configuration/global-config.md#2-automated-certificate-auto-cert)
- [Production Deployment Recommendations](../10-deployment/production.md)
