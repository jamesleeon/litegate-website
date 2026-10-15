<!-- GENERATED FILE — DO NOT EDIT.
     Source: internal/configdocs/docs/en/on-demand-tls.md (package internal/configdocs)
     Regenerate: go generate ./internal/configdocs/...
     Edit the source instead; a drift test fails if this copy is edited directly. -->

# On-Demand TLS (SaaS certificate issuance on demand)

LiteGate supports Caddy-style **On-Demand TLS**, issuing certificates during the TLS handshake. This matters for SaaS platforms: your customers can point their own custom domains at your platform without you configuring a certificate for each one or restarting the service.

## 1. How it works

When LiteGate receives a TLS handshake for a domain it has no certificate for — neither locally nor in distributed storage — it runs the following:

1.  **Authorization**: LiteGate asks your backend (through the `ask` endpoint) or checks KV storage to confirm the domain is allowed to obtain a certificate.
2.  **Binding**: On success, LiteGate dynamically binds the domain to a designated *SaaS template site*.
3.  **Issuance (ACME)**: LiteGate requests a certificate over ACME (HTTP-01 challenge by default) from Let's Encrypt or another CA.
4.  **Caching and sync**: The issued certificate is written to distributed storage (Litemesh/Consul) and cached, so later requests use it directly.

## 2. Configuration

Configure `auto_cert.on_demand` in `config.yaml`:

```yaml
auto_cert:
  enabled: true
  email: "admin@example.com"
  certs_dir: "./certs"
  on_demand:
    enabled: true
    # Option A: external authorization endpoint (recommended)
    ask: "https://api.mysaas.com/v1/verify-domain"
    # Option B: authorization from Litemesh KV
    kv_prefix: "saas/domains/"
    # default SaaS template site domain (the domain field of a site under sites/)
    saas_template_site: "template.mysaas.com"
```

### Parameters
- **`ask`**: LiteGate sends a GET request to this URL with a `domain` parameter, for example `https://api.mysaas.com/v1/verify-domain?domain=customer1.com`.
- **`saas_template_site`**: The `site` hostname of a site you have already defined in LiteGate — the key the Loader indexes that site under. Every authorized dynamic domain reuses that site's backend configuration.

## 3. Integrating your SaaS backend

### Implementing the `ask` endpoint
Your backend needs to expose an endpoint returning JSON:

```json
{
  "authorized": true,
  "template": "premium-template.mysaas.com"
}
```

- `authorized`: must be **explicitly `true`** for issuance to proceed.
- `template` (optional): when returned, overrides the globally configured `saas_template_site`.

### Request and response contract

LiteGate sends `GET {ask}?domain=shop.customer.com`. Existing query parameters are retained and domain is set to the hostname requesting a certificate. There is no JSON request body or automatically added business authorization header. The request timeout is 5 seconds.

Allow requires **HTTP 200** and a JSON object such as `{"authorized": true}`. An optional template selects an existing template site's hostname; omitted or empty uses saas_template_site. Return Content-Type: application/json. Deny with HTTP 403 and `{"authorized": false}`, or HTTP 200 with that same JSON. Missing authorized, false, empty or invalid JSON, non-200 status, network errors and timeouts deny authorization.

HTTPS with certificate verification is required by default. Internal HTTP requires allow_insecure_ask: true; private HTTPS CA certificates use ask_ca. allow_insecure_ask does not disable HTTPS certificate verification. The endpoint must already be reachable before the customer certificate is issued; avoid a hostname depending on that same issuance.

### Customer CNAME domains

If a customer sets `shop.customer.com CNAME edge.mysaas.com` and visits `https://shop.customer.com`, both TLS SNI and the ask domain are shop.customer.com, and the certificate covers that customer hostname. The CNAME target's certificate does not automatically cover it. Authorize verified, active tenant-domain bindings rather than accepting any domain whose CNAME points at the platform.

The CNAME chain must resolve to a gateway capable of serving validation. HTTP-01 requires the customer hostname's public port 80 and `/.well-known/acme-challenge/` to reach the challenge handler, including through proxies or CDNs. DNS-01 `_acme-challenge` CNAME delegation is separate; a normal application CNAME does not configure DNS-01. See [Let's Encrypt challenge types](https://letsencrypt.org/docs/challenge-types/).

### Minimal Go ask service

```go
package main

import (
    "encoding/json"
    "log"
    "net/http"
    "strings"
)

func main() {
    // Replace with verified, active tenant-domain bindings from your database.
    bindings := map[string]string{
        "shop.customer.com": "template.mysaas.com",
    }
    http.HandleFunc("/v1/verify-domain", func(w http.ResponseWriter, r *http.Request) {
        if r.Method != http.MethodGet {
            w.Header().Set("Allow", "GET")
            http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
            return
        }
        domain := strings.TrimSuffix(strings.ToLower(strings.TrimSpace(r.URL.Query().Get("domain"))), ".")
        template, allowed := bindings[domain]
        w.Header().Set("Content-Type", "application/json")
        if !allowed {
            w.WriteHeader(http.StatusForbidden)
        }
        _ = json.NewEncoder(w).Encode(struct {
            Authorized bool   `json:"authorized"`
            Template   string `json:"template,omitempty"`
        }{allowed, template})
    })
    log.Fatal(http.ListenAndServe("127.0.0.1:9080", nil))
}
```

This example listens on local HTTP only. Put an HTTPS reverse proxy in front for production; for a same-host internal trial set ask: http://127.0.0.1:9080/v1/verify-domain and allow_insecure_ask: true. Replace the static map with verified, active bindings from your database and deny unbound domains.

### Authorization sources and caching

An exact configured HTTPS site can authorize directly without calling ask every time. Dynamic SaaS domains first pass allowed_patterns (if configured), then check Litemesh KV, then fall back to ask. A valid KV entry can bypass ask; omit kv_prefix if ask must decide every dynamic domain. Successful authorization is cached for about 10 minutes. Unbinding does not immediately revoke issued certificates or cached authorization; ask is not per-request application access control.

## 4. Practices and caveats

1.  **Security**
    - **Domain validation**: LiteGate applies strict SNI validation and IDNA normalization, automatically rejecting IP addresses and invalid characters.
    - **Authorization endpoint**: enable `ask` and validate strictly. LiteGate no longer falls back to accepting a non-JSON 200 OK, which closes that gap.
2.  **Lifecycle**
    - **Caching**: authorization results are cached in memory for a short window (10 minutes by default), after which `ask` is consulted again.
    - **Renewal**: renewal **re-authorizes**. If the tenant has been unbound, LiteGate stops renewing that certificate.
3.  **Template site**: define the template site under `sites/`.
    ```yaml
    site: "template.mysaas.com"
    routes:
      - match:
          path_prefix: "/"
        proxy: ["127.0.0.1:8080"]
    ```

## 5. Implementation notes (for developers)

The logic lives in `handleOnDemand` in `internal/certmanager/certmanager.go`:

1.  **Validation and normalization**: `isValidHostname` and IDNA normalize the SNI, in `internal/cert/manager.go`.
2.  **Authorization (`checkAuthorization`)**: the `ask` endpoint is called with safely encoded parameters and its JSON response is validated.
3.  **Loader registration**: once authorized, `RegisterSaaSDomain` establishes the mapping immediately.
4.  **Distributed issuance**: a distributed lock is acquired before running the ACME challenge. On failure `UnregisterSaaSDomain` cleans the mapping up, so no dead route is left behind.
5.  **SAN preservation**: renewal extracts every `DNSNames` entry from the existing certificate, so a multi-domain certificate is not silently downgraded when it renews.
