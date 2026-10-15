# CredKeeper centralized credential storage

CredKeeper is a separate service with a web console for entering DNS credentials and AES-256-GCM encrypted storage. LiteGate fetches secret:// references on demand and briefly caches decrypted results in memory. For a single host that only needs to avoid plaintext YAML, consider Sealed Secrets first.

secret_token authenticates requests and decrypts responses. Protect it as a master key, using env://, file:// or enc://. CredKeeper listens on loopback by default. Use HTTPS or a protected transport across hosts. Response encryption cannot replace TLS because the token travels with the request. Coordinate credential/token rotations with clients.

The default gateway includes aliyun, tencent and cloudflare. CredKeeper can store other providers' credentials, but does not install gateway DNS plugins; huawei, for example, requires a compiled plugin. HTTP-01/TLS-ALPN-01 need no DNS API key; wildcard DNS-01 does.

Verify service startup, encrypted-storage permissions, client authentication and credential names before testing staging certificate issuance. Keep credential files, tokens and private keys out of public repositories.

## Related documentation and code

- [Sealed secrets](sealed-secrets.md)
- [Service implementation](../../../../credkeeper)
- [Secret resolver](../../../../internal/secret)
