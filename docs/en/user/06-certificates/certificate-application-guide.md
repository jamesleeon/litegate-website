# Certificate issuance methods and configuration

Public non-wildcard domains can use HTTP-01 (CA access to port 80) or TLS-ALPN-01 (CA access to port 443, default_challenge: tls-alpn). Wildcards require DNS-01 and a DNS Provider authorized to modify TXT records. DNS, port mappings and listeners must be correct. Validate with staging before switching to production.

auto_cert.enabled enables issuance; email, ca_provider, certs_dir and renew_days manage the account and lifecycle. The default distribution includes aliyun, tencent and cloudflare; other providers require compiled plugins. Use secure references or sealed values for DNS credentials and keep plaintext keys out of Git.

Configure account requirements for the selected ZeroSSL/Google Public CA or custom ACME service. Private CAs require client root trust. Local CA suits single-host development. Private nodes without DNS credentials can delegate Connect CSRs while keeping their private keys local.

For failures, check DNS, challenge ports, DNS API permissions, certificate directories and logs. Staging certificates are unsuitable for production, and automatic renewal does not imply certificate synchronization across replicas.

```yaml
auto_cert:
  enabled: true
  email: ops@example.com
  ca_provider: letsencrypt
  default_challenge: tls-alpn
  use_staging: true
  certs_dir: ./certs
  renew_days: 10
```

## Related documentation and code

- [Auto cert](auto-cert.md)
- [DNS providers](dns-providers.md)
- [CSR delegation](connect-csr-delegation.md)
- [Local CA](local-ca.md)
