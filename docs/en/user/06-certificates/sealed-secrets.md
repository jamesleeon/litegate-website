# Sealed Secrets: No Plaintext Keys in Configuration Files

## 1. The problem

DNS-01 certificate issuance needs a cloud provider's AccessKey/SecretKey. Written directly into `config.yaml`, the key leaks as soon as the file is sent to a colleague, committed to git, backed up, or shows up in a ticket screenshot.

Sealed secrets work like this: **the YAML holds only ciphertext; the decryption private key exists only on the gateway host.**

- The public key can be shared: anyone can encrypt with it, but only the gateway holding the private key can decrypt.
- A configuration file copied to another machine cannot be decrypted, so it can circulate and live in git.
- Implementers only ever handle ciphertext: the customer's security staff encrypt the AK/SK with the public key themselves and hand over the ciphertext.

Algorithm: X25519 key agreement + HKDF-SHA256 + AES-256-GCM (a random ephemeral key per encryption, so the same plaintext encrypts differently every time, and tampering is detected).

## 2. Security boundary (tell customers honestly)

| Scenario | Protected? |
| :--- | :--- |
| Configuration file leaks (git, email, tickets, screenshots, backups) | ✅ Yes: only ciphertext |
| Configuration file copied to another machine | ✅ Yes: no private key, no decryption |
| An attacker already has root/administrator on the gateway host | ❌ No: they can read the private key and process memory |

No purely software scheme can defend a fully compromised host (the gateway ultimately has to call the cloud API with plaintext). Combine this with host hardening and a least-privilege RAM sub-account that may only change DNS records.

## 3. Steps

### 1. Generate a key pair on the gateway host (once per host)

```bash
litegate secret keygen
```

- The private key is written to `/etc/litegate/secret.key` by default (Windows: `%ProgramData%\LiteGate\secret.key`) with mode 0600.
- The `lgpk1_...` value printed on screen is the public key; send it to the customer's security staff.
- Back up the private key offline. **If the private key is lost, nothing encrypted with it can be decrypted**; you must generate a new key pair and encrypt everything again.
- If a private key already exists the command refuses to overwrite it; add `--force` to rebuild it deliberately.

Show the host's public key at any time:

```bash
litegate secret pubkey
```

### 2. Encrypt values

On the gateway host (uses the local public key by default), reading from standard input so the plaintext stays out of shell history:

```bash
litegate secret encrypt
```

The customer's security staff, on their own computer, with the gateway's public key:

```bash
litegate secret encrypt --pubkey lgpk1_xxxxxxxx
```

The output is a single line of ciphertext like `enc://AWoirIpF...`.

### 3. Put it in the configuration

```yaml
auto_cert:
  enabled: true
  email: "admin@example.com"
  dns_providers:
    - name: aliyun
      type: aliyun
      domains: ["*.example.com"]
      config:
        access_key_id: "enc://AWoirIpF..."
        access_key_secret: "enc://AbX9k2Qe..."
        region_id: "cn-hangzhou"   # non-sensitive fields can stay plaintext
```

`enc://` works in every field that supports secret references (each entry under a DNS provider's `config`, `webhook_token`, ...), just like `env://`, `file://` and `${VAR}`.

## 4. Where the private key is looked up

1. Environment variable `LITEGATE_SECRET_KEY` (the private key content itself; suits container secrets / systemd credentials)
2. Environment variable `LITEGATE_SECRET_KEY_FILE` (path to the private key file)
3. Platform default path: Linux/macOS `/etc/litegate/secret.key`, Windows `%ProgramData%\LiteGate\secret.key`

> Don't keep the private key in the configuration directory, and don't package, back up or commit it together with the configuration.

## 5. Relationship with CredKeeper

- **One or a few gateways**: sealed secrets are enough; no extra service to deploy.
- **Many gateways sharing credentials with central rotation**: use [CredKeeper](credkeeper.md). Its `secret_token` can itself be written as `enc://` ciphertext, so the YAML still holds no plaintext secret.

> `enc://` only works in fields that support secret references; in other fields it is not decrypted. When gateways use different private keys, encrypt separately for each.

## Related code

- [Ciphertext resolver](../../../../internal/secret/enc.go)
- [secret command](../../../../pkg/litegate/secret_cmd.go)
