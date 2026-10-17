# LiteGate CredKeeper: Secure Hosting for DNS Credentials

> The default LiteGate build includes Alibaba Cloud, Tencent Cloud and Cloudflare. The Huawei Cloud configuration on this page requires compiling the corresponding third-party DNS provider plugin into LiteGate first; CredKeeper can store credentials for those providers regardless.

## 1. Background and purpose

Issuing wildcard certificates (`*.example.com`) over ACME requires a **DNS-01 challenge**. The gateway typically has to call a cloud provider's DNS API (Alibaba Cloud, Tencent Cloud, Huawei Cloud, Cloudflare) to add `_acme-challenge` TXT records.

In private enterprise deployments, financial compliance or multi-tenant settings, this raises key security problems:
1. **No high-risk keys in plaintext configuration**: a cloud account's `AccessKey Secret` is a high-risk credential. Written in plaintext into the gateway's `config.yaml`, it is easily exposed through leaked configuration, accidental commits or host audit violations.
2. **No plaintext at rest**: security standards usually require sensitive data to be stored with strong standard encryption (such as AES-256) so an offline disk copy reveals nothing.
3. **Central management**: when several gateways share one set of cloud credentials, you want to enter and rotate them in one place.

LiteGate therefore provides **CredKeeper**, a credential hosting service. It runs as a small standalone executable in the customer's controlled data center, offers a web console for entering credentials, encrypts them locally with AES-256-GCM, and LiteGate fetches them on demand and uses them only in memory.

> **First check whether you need CredKeeper**: if you only want to avoid plaintext AK/SK in YAML, [sealed secrets](sealed-secrets.md) are simpler — write `enc://` ciphertext in YAML with no extra service. CredKeeper suits central credential management for many gateways.

> **Security boundary**:
> - `secret_token` is used for both authentication and decryption. Whoever has it can retrieve every credential, so **don't write it in plaintext in YAML** either; use `enc://` ciphertext or a `file://` reference (see section 6).
> - CredKeeper listens on `127.0.0.1` by default. In cross-host deployments over internal HTTP, the token travels in a request header, and **transport security depends on the customer network**; if eavesdropping is a concern, put HTTPS in front.

> **When it applies**:
> - **Ordinary single/multiple domains (public port 80 open)**: plain **HTTP-01** works; LiteGate answers `/.well-known/acme-challenge/*` itself, and **no cloud credentials or CredKeeper are needed**.
> - **Wildcard certificates (`*.example.com`) or internal environments that can't expose port 80**: ACME requires **DNS-01**, and CredKeeper is recommended for keeping the keys safe.

---

## 2. Architecture and encryption

```
                     +-------------------------------------------------------------+
                     |                 Customer-controlled internal host           |
                     |                                                             |
+----------------+   |   +-----------------------------------------------------+   |
| Customer       |   |   | Embedded web console (http://localhost:8088)        |   |
| security staff | ----->| 1. Set the master token                             |   |
| (browser)      |   |   | 2. Enter AK/SK for each cloud provider              |   |
+----------------+   |   +--------------------------+--------------------------+   |
                     |                              | Click "Encrypt and save"     |
                     |                              | SHA-256(Token) -> AES key    |
                     |                              v                              |
                     |   +-----------------------------------------------------+   |
                     |   | Local ciphertext file data/credentials.enc          |   |
                     |   | (fully encrypted, no plaintext on disk)             |   |
                     |   +--------------------------+--------------------------+   |
                     |                              |                              |
                     |                              | 3. HTTP GET /v1/secret/:name |
+----------------+   |                              |    (Bearer token auth)       |
| LiteGate       |<=================================+                              |
| (business node)|   |   4. Returns: { encrypted: true, nonce: "...",              |
+----------------+   |             ciphertext: "encrypted with a random nonce" }   |
  Decrypts in memory +-------------------------------------------------------------+
  with the token,
  runs ACME, keeps
  nothing on disk
```

### 1. Key derivation
A high-entropy token agreed between both sides (or a 32-character random passphrase generated in the UI) is turned into a 32-byte master key with `SHA-256`.

### 2. Encryption at rest
All credentials are encrypted with `AES-256-GCM` and written atomically to local disk as JSON (default `data/credentials.enc`). An offline copy of the file shows only ciphertext and random nonces; nothing can be recovered without the token.

### 3. Encrypted response payloads
When LiteGate fetches a credential with `GET`, CredKeeper authenticates the token and encrypts the credential with a random nonce before returning it, so no plaintext appears in the response body.
Note: this layer uses the same token as authentication, and the token travels in a request header, so it **does not replace HTTPS**. Its purpose is to keep plaintext out of proxy logs and debug output; to defend against network sniffing, use HTTPS or only the local loopback address.

### 4. Transparent decryption in LiteGate
LiteGate's built-in secret resolver (`internal/secret`) decrypts payloads marked `"encrypted": true` with the `secret_token` from `config.yaml` and completes DNS-01 validation in memory; nothing is persisted on the gateway (to reduce requests, decrypted results are cached in memory for 5 minutes; a 401/403 from CredKeeper invalidates the cache immediately).

---

## 3. DNS provider fields supported by the web console

The CredKeeper web console can store credentials for these 4 providers. Alibaba Cloud, Tencent Cloud and Cloudflare are DNS providers built into LiteGate by default; Huawei Cloud requires compiling its plugin in with `litegate build --dns` first, see [DNS providers](dns-providers.md).

| Provider | Type (`type`) | Required fields | Optional fields | Permission advice |
| :--- | :--- | :--- | :--- | :--- |
| **Alibaba Cloud DNS** | `aliyun` | `access_key_id`<br>`access_key_secret` | `zone` (hosted zone; found via SOA when omitted) | RAM user with `AliyunDNSFullAccess` or permission to change specific domains |
| **Tencent Cloud** | `tencent` | `secret_id`<br>`secret_key` | none | CAM key with `QcloudDNSPodFullAccess` |
| **Huawei Cloud** | `huawei` | `access_key_id`<br>`secret_access_key` | `region` (default `cn-north-1`) | IAM user with DNS Administrator or permission for specific domains |
| **Cloudflare** | `cloudflare` | **Mode 1 (recommended)**: `api_token`<br>**Mode 2 (legacy)**: `api_key` + `email` | `timeout` (default `120s`) | A token with only `Zone.DNS:Edit`; least privilege is safer |

---

## 4. Building and running

### 1. Build the binary
From the repository root:

```bash
# Build for the local platform (output cmd/bin/credkeeper or credkeeper.exe)
make credkeeper

# Or build everything (Windows/Linux/macOS, multiple architectures)
make all
```

### 2. Flags and environment variables

CredKeeper takes a few flags and the matching environment variables (handy for containers or systemd):

| Flag | Environment variable | Default | Description |
| :--- | :--- | :--- | :--- |
| `-port` | `CREDKEEPER_PORT` | `8088` | HTTP listening port |
| `-host` | `CREDKEEPER_HOST` | `127.0.0.1` | HTTP listening interface. Change to an internal IP or `0.0.0.0` only when LiteGate runs on another host |
| `-data` | `CREDKEEPER_DATA_FILE` | `data/credentials.enc` | Path of the local encrypted file |

#### Examples:
```bash
# Start on the default port 8088
./cmd/bin/credkeeper

# Custom port and storage path
./cmd/bin/credkeeper -port 9090 -data /var/lib/credkeeper/secrets.enc
```

---

## 5. Using the web console

1. Open `http://<service IP>:8088` in a browser.
2. **Set the master token**:
   * Enter the agreed token in step 1, or click **Generate** for a 32-character high-entropy passphrase.
   * *Tip: click the eye icon to show it in plaintext, and keep the token safe.*
3. **Enter DNS provider credentials**:
   * Switch tabs (Alibaba Cloud / Tencent Cloud / Huawei Cloud / Cloudflare);
   * Fill in the key and secret (leave unused providers empty).
4. **Click "Encrypt and save locally"**:
   * The console confirms, and a strongly encrypted `credentials.enc` is created at the configured path.
   * Saving **merges**: providers you didn't fill in this time keep their existing credentials.
   * If the encrypted file exists, you must save with the **original token**, so others can't overwrite it. To change the token, back up and delete `credentials.enc`, then enter everything again with the new token.
5. **Copy the configuration**:
   * "Step 3" at the bottom **generates ready-to-use YAML from what you entered**; click **Copy configuration**.

---

## 6. Complete LiteGate configuration

### 1. LiteGate `config.yaml` example (direct configuration, no environment variables)

References are written as `secret+http://<address>/v1/secret/<provider>#<field>`; use `secret+https://` when CredKeeper is served over HTTPS. In LiteGate's configuration, set `secret_token` under `auto_cert` (or per DNS provider) to authenticate to CredKeeper and decrypt. `secret_token` supports `enc://`, `file://`, `env://` and `${VAR}` references:

```yaml
auto_cert:
  enabled: true
  email: "admin@mycompany.com"
  renew_days: 30
  check_interval: 24
  # Token agreed with CredKeeper. Don't write it in plaintext; prefer ciphertext:
  #   litegate secret keygen          # once on the gateway host
  #   litegate secret encrypt         # enter the token, get enc://...
  # or "file:///etc/litegate/credkeeper.token" (file mode 0600)
  secret_token: "enc://AWoirIpF..."

  dns_providers:
    # 1. Alibaba Cloud wildcard certificates
    - name: aliyun
      type: aliyun
      domains:
        - "*.aliyun.mycompany.com"
      config:
        access_key_id: "secret+http://127.0.0.1:8088/v1/secret/aliyun#access_key_id"
        access_key_secret: "secret+http://127.0.0.1:8088/v1/secret/aliyun#access_key_secret"
        region_id: "cn-hangzhou"

    # 2. Tencent Cloud wildcard certificates
    - name: tencent
      type: tencent
      domains:
        - "*.tencent.mycompany.com"
      config:
        secret_id: "secret+http://127.0.0.1:8088/v1/secret/tencent#secret_id"
        secret_key: "secret+http://127.0.0.1:8088/v1/secret/tencent#secret_key"

    # 3. Huawei Cloud wildcard certificates (requires the Huawei Cloud DNS plugin)
    - name: huawei
      type: huawei
      domains:
        - "*.huawei.mycompany.com"
      config:
        access_key_id: "secret+http://127.0.0.1:8088/v1/secret/huawei#access_key_id"
        secret_access_key: "secret+http://127.0.0.1:8088/v1/secret/huawei#secret_access_key"

    # 4. Cloudflare wildcard certificates
    - name: cloudflare
      type: cloudflare
      domains:
        - "*.cloudflare.mycompany.com"
      config:
        api_token: "secret+http://127.0.0.1:8088/v1/secret/cloudflare#api_token"
        timeout: "120s"
```

---

## 7. FAQ

### Q1: `Unauthorized: token mismatch or corrupted data`?
- **Cause**: the token LiteGate sends differs from the one CredKeeper used to encrypt the file, so the AES-GCM authentication tag check fails.
- **Fix**: make sure `secret_token` in LiteGate's `config.yaml` exactly matches the token entered in the CredKeeper console.

### Q2: Saving says the token doesn't match the stored credentials?
- **Cause**: the encrypted file exists and the token you entered differs from the original. CredKeeper refuses the save so others can't overwrite the credentials.
- **Fix**: save with the original token. To change the token, back up and delete `credentials.enc`, enter all credentials again, and update `secret_token` on every gateway.

### Q3: Can CredKeeper run as a systemd service?
Create `/etc/systemd/system/credkeeper.service`:
```ini
[Unit]
Description=LiteGate CredKeeper Security Sidecar
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/credkeeper
ExecStart=/opt/credkeeper/credkeeper -host 127.0.0.1 -port 8088 -data /opt/credkeeper/data/credentials.enc
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
Then run `systemctl enable --now credkeeper`.

---

## 8. Summary

With CredKeeper:
* **The customer** gets a friendly web page for entering credentials; sensitive keys are AES-256 encrypted on local disk and cloud permissions stay under their control;
* **Implementers and operators** see only references and ciphertext in configuration files, never plaintext keys;
* **Boundary**: CredKeeper addresses "no plaintext credentials in configuration or on disk" and central management; rely on HTTPS or the internal network for transport security, and no purely software scheme defends a fully compromised host.

## Related docs and code

- [Sealed secrets](sealed-secrets.md)
- [DNS providers](dns-providers.md)
- [CredKeeper implementation](../../../../credkeeper)
- [Secret resolver](../../../../internal/secret)
