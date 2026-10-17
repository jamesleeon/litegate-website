# Certificate Issuance Configuration Guide

This page explains how LiteGate requests, renews and stores HTTPS certificates, covering Let's Encrypt, ZeroSSL, Google Public CA, custom ACME, the LiteMesh private CA, wildcard certificates and the local development CA.

## 1. Choose an issuance method first

| Scenario | Recommended method | Do clients need an extra trusted root? |
| :--- | :--- | :--- |
| Ordinary public domain | Let's Encrypt + HTTP-01 | No |
| Ordinary public domain (port 80 blocked or not wanted) | Let's Encrypt + TLS-ALPN-01 | No |
| Public wildcard domain | Let's Encrypt + DNS-01 | No |
| Intranet tunneling / hybrid-cloud multi-tenant | Connect delegated issuance (DNS-01 done for you + private key stays local) | No |
| Backup public CA | ZeroSSL or Google Public CA | No |
| Enterprise internal domain | LiteMesh/other private ACME + DNS-01 | Yes |
| Single-machine development domain | LiteGate Local CA | Yes |

Issuance requires `auto_cert.enabled: true`. HTTP-01 needs the CA to reach port 80 of the domain; TLS-ALPN-01 needs the CA to reach port 443 (no port 80 and no DNS API credentials needed); DNS-01 needs LiteGate to be able to create `_acme-challenge` TXT records. If an internal Private node has no public DNS credentials and needs end-to-end TLS termination, use [Connect delegated certificate issuance](connect-csr-delegation.md).

## 2. Let's Encrypt for an ordinary domain (HTTP-01)

```yaml
auto_cert:
  enabled: true
  email: "ops@example.com"
  ca_provider: "letsencrypt"
  use_staging: false
  certs_dir: "./certs"
  renew_days: 10
```

Make sure the domain's A/AAAA records point to LiteGate and the host's ports 80 and 443 map to LiteGate. For first-time debugging set `use_staging: true`, then switch back to production once it works.

## 2.1 Let's Encrypt for an ordinary domain (TLS-ALPN-01)

If port 80 is blocked by your ISP or cloud firewall, or a pure HTTPS gateway shouldn't open port 80, and you have no DNS API credentials, use TLS-ALPN validation:

```yaml
auto_cert:
  enabled: true
  email: "ops@example.com"
  ca_provider: "letsencrypt"
  default_challenge: "tls-alpn"  # global TLS-ALPN-01 validation (over port 443)
  certs_dir: "./certs"
```

The CA performs a TLS handshake against port 443 and LiteGate negotiates the `acme-tls/1` protocol to complete the challenge and obtain the certificate.
> Note: TLS-ALPN cannot issue wildcard certificates (`*.example.com`); for wildcards configure DNS-01 below.

## 3. DNS-01 and wildcard certificates

Wildcard certificates cannot use HTTP-01; a DNS provider is required:

```yaml
auto_cert:
  enabled: true
  email: "ops@example.com"
  ca_provider: "letsencrypt"
  dns_providers:
    - name: "aliyun-main"
      type: "aliyun"
      enabled: true
      domains: ["example.com", "*.example.com"]
      config:
        access_key_id: "${ALIYUN_ACCESS_KEY_ID}"
        access_key_secret: "${ALIYUN_ACCESS_KEY_SECRET}"
```

`domains` decides which domains use this DNS provider. All domains in one SAN certificate must resolve to the same challenge provider.

The default build includes three DNS providers: `aliyun`, `tencent` and `cloudflare`; other providers must be compiled in with `litegate build --dns`, see [DNS providers](dns-providers.md). Don't write AccessKeys and similar credentials in plaintext; use `env://`, `file://` or [sealed secrets](sealed-secrets.md).

## 4. ZeroSSL and Google Public CA

Both require EAB:

```yaml
auto_cert:
  enabled: true
  email: "ops@example.com"
  ca_provider: "zerossl" # or google
  eab_kid: "your-eab-key-id"
  eab_hmac: "your-eab-hmac"
```

With `use_staging: true`, Google uses its staging directory. Production and staging EAB credentials can't be mixed. Each CA uses its own ACME account key.

> Buypass has stopped issuing TLS certificates, and LiteGate no longer accepts `ca_provider: buypass`.

## 5. Custom ACME and a private HTTPS root

```yaml
auto_cert:
  enabled: true
  email: "pki@example.internal"
  ca_provider: "custom"
  acme_url: "https://ca.example.internal/acme/directory"
  acme_ca_cert: "/etc/litegate/private-acme-root.pem"
  acme_headers:
    Authorization: "Bearer private-acme-token"
```

`acme_ca_cert` can be a PEM file path or the PEM content itself. LiteGate adds the root to the system trust store; TLS verification is never disabled. `acme_headers` is allowed only in `custom` mode; inject sensitive values through protected configuration or a secret manager.

## 6. Site certificates from the LiteMesh private CA

LiteMesh has two kinds of endpoints:

- `/v1/ca/sign`: issues SPIFFE/mTLS workload identity certificates.
- `/acme/directory`: lets LiteGate request website HTTPS certificates.

### 6.1 Enable LiteMesh ACME

```yaml
ca:
  bootstrap: true
  cert_valid_days: 365
  acme:
    enabled: true
    domain_policies: [".internal", ".svc.litemesh"]
    disable_challenge: false
    allow_private_http01: false
```

In production keep challenge validation and configure DNS-01 for internal DNS. LiteMesh offers both HTTP-01 and DNS-01 for ordinary domains, and only DNS-01 for wildcards.

LiteGate configuration:

```yaml
auto_cert:
  enabled: true
  email: "pki@example.internal"
  ca_provider: "custom"
  acme_url: "http://litemesh:8080/acme/directory"
  dns_providers:
    - name: "internal-dns"
      type: "mydns" # name registered with plugin.RegisterDNSProviderV2
      enabled: true
      domains: ["corp.internal", "*.corp.internal"]
      config:
        endpoint: "https://dns-api.example.internal"
        token: "your-dns-api-token"
```

If LiteMesh ACME uses private HTTPS, add `acme_ca_cert`. TXT records written by the DNS provider must be resolvable by the DNS resolver LiteMesh uses.

### 6.2 Internal HTTP-01

Only when the CA and the target hosts are on a trusted isolated network:

```yaml
ca:
  acme:
    allow_private_http01: true
```

This lets LiteMesh reach private/loopback addresses for HTTP-01 validation and widens the SSRF surface; don't enable it when DNS-01 is possible.

### 6.3 Skipping challenges in trusted environments

Test or tightly controlled internal environments can set `disable_challenge: true` and have LiteGate carry the cluster token:

```yaml
auto_cert:
  ca_provider: "custom"
  acme_url: "http://litemesh:8080/acme/directory"
  acme_headers:
    X-Lito-Token: "your-litemesh-cluster-token"
```

Never skip domain control validation on open networks.

### 6.4 Distributing the LiteMesh root

Site certificates from a private CA are not trusted automatically by browsers, operating systems or containers. Export the root with LiteMesh `GET /v1/ca/root` and install it in every client's trust store. The root certificate can be distributed; the root private key must never leave the CA node.

## 7. LiteMesh mTLS identity certificates

With the cluster administrator token:

```yaml
litemesh:
  enabled: true
  address: "litemesh:8080"
  token: "cluster-token"
  mtls: true
  spiffe_id: "spiffe://litemesh.local/ns/default/sa/litegate"
```

Or with workload credentials:

```yaml
litemesh:
  enabled: true
  address: "litemesh:8080"
  mtls: true
  spiffe_id: "spiffe://litemesh.local/ns/default/sa/litegate"
  workload_service_id: "litegate-node-1"
  workload_token: "registered-workload-token"
```

The workload's service name, namespace, source IP and token must match its LiteMesh registration.

## 8. LiteGate Local CA

```yaml
tls:
  enabled: true
  certs_dir: "./certs"
  local_ca: true
  local_ca_domains: [".localhost", ".test", "dev.internal"]
  local_ca_trust: false
```

The root certificate is at `certs/local_root_ca.crt`. Distribute and trust it manually; don't enable `local_ca_trust` in production. If the root certificate or key is missing or corrupt, LiteGate refuses to rotate the root automatically, so clients don't suddenly lose trust.

## 9. Troubleshooting checklist

1. Check the CA URL and challenge type actually chosen in the logs.
2. HTTP-01: from the CA's network, fetch `http://<domain>/.well-known/acme-challenge/test` to confirm port 80 is reachable.
3. DNS-01: query the TXT record of `_acme-challenge.<domain>` and confirm both the authoritative DNS and the resolver LiteMesh uses can see it.
4. Private HTTPS ACME: confirm `acme_ca_cert` is the root that issued the ACME server certificate.
5. ZeroSSL/Google: confirm EAB is complete, belongs to the right environment, and the ACME account key storage hasn't been lost.
6. Browser says a private CA certificate isn't trusted: check the right root CA is installed on the client, not just the LiteGate server.
7. Cluster deployments: every LiteGate node must use the same `ca_provider` and `acme_url` and share certificate storage.
8. Never use staging certificates in production; automatic renewal is not certificate synchronization across replicas — multiple nodes need shared certificate storage.

## Related docs

- [Auto-Cert](auto-cert.md)
- [DNS providers](dns-providers.md)
- [Connect delegated certificate issuance](connect-csr-delegation.md)
- [Local CA](local-ca.md)
- [LAN CA and mTLS](lan-ca-and-mtls.md)
