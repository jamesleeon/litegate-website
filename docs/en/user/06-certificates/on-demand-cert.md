# On-Demand TLS (Dynamic SSL Generation)

**On-Demand TLS** is an advanced certificate orchestration capability built into LiteGate. Unlike standard Auto-Cert, which attempts domain certificate acquisition during startup, On-Demand TLS triggers dynamic, real-time certificate acquisition on the **First Handshake** when a client attempts to connect.

---

## 1. Primary Operational Scenarios

- **Multi-Tenant SaaS Portals**: Enables SaaS platforms to let custom client hostnames (e.g. `customer-brand.com`) CNAME map to your ingress gateway. These hostnames can be securely provisioned and bound without having prior knowledge of client domain mappings.
- **Massive Scalability**: Prevents gateway startup slowdowns and Let's Encrypt rate-limit blocks when managing thousands of rarely accessed subdomain routes.

---

## 2. Configuration Parameters

Declare your on-demand validation strategy inside `config.yaml` (an explicit authorization whitelist hook is **mandatory** to prevent abuse):

```yaml
auto_cert:
  enabled: true
  on_demand:
    enabled: true
    # Whitelist verification API (queries this HTTPS URL during handshake check)
    ask: "https://your-backend:8443/check-domain"
    ask_ca: "/etc/litegate/certs/ask-ca.pem" # Optional. Local path to Root CA for validating the Ask server cert
    allow_insecure_ask: false                # Optional. Disable HTTPS enforcement (allows plain HTTP or skips TLS validation for local testing)
```

### Site Declaration YAML
```yaml
domain: "*"  # Pair with catch-all wildcard configurations
force_https: true
```

---

## 3. Handshake & Provisioning Sequence

1. **First Connection**: A client accesses a brand new custom domain `https://random-user.com` resolved to the LiteGate WAN IP.
2. **Handshake Interception**: The gateway intercepts the TLS Client Hello SNI payload. The gateway queries your backend `ask` endpoint (e.g. `GET /check-domain?domain=random-user.com`) to verify if the domain belongs to a registered client.
3. **Upstream Authorization**: Your backend returns an HTTP **`200 OK`** to authorize the domain.
4. **On-the-Fly Challenge**: The gateway triggers an immediate background ACME HTTP-01 challenge. The certificate is issued by the CA and returned within **3 to 10 seconds**.
5. **TLS Completion**: The TLS handshake completes successfully. The certificate is stored in the gateway's memory cache and written to disk. Subsequent connections are processed immediately.

---

## 4. Security Mitigations & Tunnel Hardening

Because SSL certificate generation involves heavy CPU-bound handshakes and network latency, LiteGate implements the following guardrails:
- **Maximum Concurrent Handshakes**: Restricts the maximum number of concurrent background ACME acquisition tasks.
- **Strict Ask Validation**: Rejecting unauthorized domains via the `ask` endpoint check prevents malicious actors from exhausting your Let's Encrypt rate-limits.
- **TLS Pinning for Ask Endpoints (Ask CA)**: To prevent spoofing or man-in-the-middle (MITM) attacks on the authorization check channel, LiteGate enforces HTTPS queries for the `ask` endpoint by default. You can supply a custom Root CA certificate path using `ask_ca` to lock trust on your authorization server. Setting `allow_insecure_ask: true` bypasses this enforcement for local sandbox or test environments.

---

## 5. Local Whitelist (Allowed Patterns)

In addition to dynamic backend validation (via the `ask` endpoint or a shared KV storage), the gateway supports local pattern-matching whitelists under `allowed_patterns`.

Its security model behaves as follows:
- **Dual-Track Filtering (Pre-Filter)**: If both `allowed_patterns` and `ask` (or `kv_prefix`) are configured, the gateway checks the requested domain against the patterns first. The dynamic backend `ask` endpoint is only queried if the domain successfully matches the local pattern whitelist. This reduces useless upstream traffic and blocks random internet scanner requests.
- **Direct Whitelist Authorization**: If only `allowed_patterns` is set, while `ask` and `kv_prefix` are left blank, the gateway will treat all domains matching the pattern rules as **directly authorized**. The dynamic certificate generation flow is triggered immediately. This is highly useful for simple scenarios where a predefined domain suffix or list is sufficient, eliminating the need to set up a separate API microservice.

> [!IMPORTANT]
> Ensure that at least one verification strategy (`ask`, `kv_prefix`, or `allowed_patterns`) is enabled. **Do not** expose wildcard `domain: "*"` configurations without any active security filters, as it presents a severe resource exhaustion risk (arbitrary host headers triggering unlimited cert requests).

Example configuration:
```yaml
auto_cert:
  enabled: true
  on_demand:
    enabled: true
    # Filter requests locally via patterns without any external ask APIs
    allowed_patterns:
      - "*.user.example.com"
      - "custom.domain.org"
```

---

## Further Reading
- [Configuring Custom Mock Responses](../../user/04-actions/respond.md)
- [Comprehensive Auto-Cert Manual](./auto-cert.md)
