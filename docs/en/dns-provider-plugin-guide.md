# DNS Provider Plugin Authoring Guide (DNS-01, DDNS and ECH HTTPS Records)

## ECH extension boundary

LiteGate owns ECH keys, TLS installation, rotation, retention, encrypted file/KV state, Consul/LiteMesh synchronization, publisher leases, group selection and retries. A DNS plugin only reads and writes provider HTTPS (type 65) records. It does not implement KV or receive ECH private keys/storage secrets.

Implement plugin.HTTPSDNSProvider (GetName and PublishHTTPS(ctx, name, value, owned)) and register via RegisterDNSProviderV2 with DNSCapabilityHTTPS (`https_records`). The capability is independent of DDNS: Sync is not required. Add CertDNSProviderV2/cert_dns01 only if the same plugin also performs certificate DNS-01 challenges; otherwise arrange a covering certificate provider. A lego DNS-01 adapter does not automatically support HTTPS records.

For an HTTPS-only plugin, `domains` selects ECH publication scope. LiteGate removes these selectors only in the certificate runtime copy, preserving the saved configuration. Configure a separate certificate-capable provider covering the public name and websites, such as a Cloudflare provider with `domains: ["*.example.com"]`. Both providers must operate on the appropriate authoritative zone: the record plugin manages HTTPS records, and the certificate provider manages ACME TXT records. The record plugin must be registered and compiled into the binary.

Each group's public name needs certificate coverage: another enabled DNS-01 provider, legacy `auto_cert.provider` + `auto_cert.domains`, or a currently valid covering `.pem`/`.crt` certificate with its matching `.key` in `tls.certs_dir`. Missing coverage fails configuration validation, including `-t`. Manual certificates require your own renewal and must be readable during validation and startup. Withdrawal preserves foreign records and succeeds without an ownership conflict. The new value need not be in `owned`; ownership governs existing records. Plugin configuration validation resolves secrets and fills `secret_token` from provider/global certificate settings before calling Validate, so validation requires access to those secrets.

name is the hidden DNS owner. value is a public presentation-format record such as `1 . alpn="h2,h3" ech="..."`, excluding owner/type/TTL; use TTL 600. owned is supplied by LiteGate from retained keys and publication state. Read the existing RRset and compare DNS semantics, not formatting. Reject foreign records before publishing a nonempty value; replace only owned records. Empty value withdraws owned records while preserving foreign values; missing records succeed. Never modify A/AAAA. Honor context cancellation, make operations idempotent and report API errors for core retries. DNSCloser may release resources.

Compile with `litegate build --with your-module/mydns -o litegate`. Set dns_providers[].type to the registration name and ech.dns_provider to that configured entry's name. ECH storage/KV remains a core configuration, not a plugin responsibility. Missing capability declarations or implementations fail validation/startup.

See the [compilable memory provider](https://github.com/jamesleeon/LiteGate/blob/master/examples/plugins/dns/memory/memory.go) for ownership checks, update and withdrawal. It is an in-memory demonstration, not a production authoritative DNS writer. See the [ECH deployment/client guide](user/06-certificates/ech.md).

> This guide shows you how to write a custom **DNS Provider** plugin for LiteGate, taking over two responsibilities: the **DNS-01 challenge for ACME certificate issuance** (adding/removing TXT records) and **Dynamic DNS (DDNS) synchronization** (writing the host's IP to A/AAAA records).
>
> Use it when: your DNS service is not in the built-in list (built-ins: Alibaba Cloud / Cloudflare / Tencent Cloud / Huawei Cloud), or you want to use your own DNS API / internal IPAM / private DNS service for certificate validation and DDNS.
>
> The contract lives in the public package [`github.com/jamesleeon/LiteGate/pkg/plugin`](https://github.com/jamesleeon/LiteGate/blob/master/pkg/plugin), so **third parties can author and compile it from a standalone repository**. For general plugins (Action / Middleware / LoadBalancer) see [plugin-authoring-guide.md](../zh-cn/plugin-authoring-guide.md); for IDS auth plugins see [ids-provider-plugin-guide.md](../zh-cn/ids-provider-plugin-guide.md); for DDNS usage itself see [user/06-certificates/ddns.md](user/06-certificates/ddns.md).
>
> *(Note: the two plugin guides linked above currently exist in Chinese only.)*

---

## 1. Core idea: one name, two capabilities

LiteGate models DNS operations as a **named Provider**. Your plugin registers a name (e.g. `"mydns"`), which users reference via `auto_cert.dns_providers[].type`. A single Provider can offer two capabilities, **each implemented as needed, neither mandatory**:

| Capability | Interface | What it does | When it's called |
|---|---|---|---|
| **Certificate DNS-01** (read/write TXT) | `plugin.CertDNSProvider` | Add/remove the `_acme-challenge` TXT record during ACME challenges | On certificate issuance / renewal |
| **DDNS sync** (write A/AAAA) | `plugin.DDNSProvider` | Sync the latest IP to the domain's A / AAAA record | On DDNS periodic sync / IP change |

Both build on a **marker interface** `plugin.DNSProvider` (which only has `GetName()`). **A cert-only plugin implements just `CertDNSProvider`; a DDNS-only plugin implements just `DDNSProvider`; one that needs both implements both.** The core asserts the capability at the point of use: if the required capability is missing, it returns a clear error there — it never silently fails mid-flight.

> Built-in providers (aliyun / cloudflare / tencent / tencentcloud / huawei / huaweicloud) and your third-party plugin go through the **same public registry and the same assertion path** — built-in features eat their own dog food.

---

## 2. The interface contract (`pkg/plugin/dns.go`)

Everything is defined in [pkg/plugin/dns.go](https://github.com/jamesleeon/LiteGate/blob/master/pkg/plugin/dns.go):

```go
// marker: base interface for all DNS plugins
type DNSProvider interface {
	GetName() string // the provider's unique identifier
}

// Capability 1: ACME DNS-01 challenge (certificate issuance/renewal)
type CertDNSProvider interface {
	DNSProvider
	AddTXTRecord(ctx context.Context, domain, token, keyAuth string) error    // add TXT
	DeleteTXTRecord(ctx context.Context, domain, token, keyAuth string) error // delete TXT (cleanup after challenge)
}

// Capability 2: Dynamic DNS (A/AAAA sync)
type DDNSProvider interface {
	DNSProvider
	Sync(ctx context.Context, domain string, ip string) error // write ip to domain's A/AAAA
}
```

Plus three **optional interfaces** (effective only when implemented; the core probes them with type assertions):

```go
// Customize DNS-01 propagation waiting (otherwise lego's default authoritative-NS polling is used)
type DNSPropagationChecker interface {
	WaitForPropagation(ctx context.Context, domain, value string) error
}

// Customize DNS-01 propagation timeout (otherwise defaults to total 2min / poll interval 10s)
type DNSOptionalTimeout interface {
	GetTimeout() (totalTime, checkInterval time.Duration)
}

// Customize record-sync routing (preferred over DDNSProvider.Sync on the cert-manager sync path; gives direct control over recordType)
type DNSSyncRecordRouter interface {
	SyncRecord(ctx context.Context, domain, recordType, value string) error
}

// Validate provider-specific config early. Existing plugins may omit this.
type DNSConfigValidator interface {
	ValidateConfig(config map[string]string) error
}

// Describe capabilities/config fields for docs, dashboard, and preflight tooling.
type DNSProviderDescriptor interface {
	Describe() DNSProviderInfo
}

// Optional API reachability / credential health check for preflight tooling.
type DNSHealthChecker interface {
	CheckHealth(ctx context.Context) error
}
```

**Registration function:**

```go
// Third parties register a custom DNS Provider; a clash with a built-in or already-registered name returns an error
func RegisterDNSProvider(name string, factory DNSProviderFactory) error

// Legacy factory: receives only a string config map (from the YAML dns_providers[].config)
type DNSProviderFactory func(config map[string]string) (DNSProvider, error)

// Dependency-aware factory: use this when the provider needs the host logger.
func RegisterDNSProviderWithDependencies(name string, factory DNSProviderFactoryWithDependencies) error

type DNSProviderFactoryWithDependencies func(config map[string]string, deps *Dependencies) (DNSProvider, error)
```

> Note: `RegisterDNSProvider` stays backward compatible and only receives `config`. Use `RegisterDNSProviderWithDependencies` if your plugin needs the LiteGate logger. DNS providers should treat `deps.Discovery` as optional/not guaranteed.

---

## 3. Writing a DNS Provider plugin

### Shortcut: the provider already exists in lego (recommended)

[lego](https://go-acme.github.io/lego/dns/) ships 180+ DNS providers (VegaDNS, DNSPod, Route 53, GoDaddy, ...). If yours is among them, register it with [`pkg/plugin/legodns`](https://github.com/jamesleeon/LiteGate/blob/master/pkg/plugin/legodns) — no API calls or TXT derivation to write:

```go
package vegadns

import (
	"github.com/go-acme/lego/v5/providers/dns/vegadns"
	"github.com/jamesleeon/LiteGate/pkg/plugin/legodns"
)

func init() {
	legodns.MustRegister("vegadns", legodns.Registration{
		Required: []string{"url", "api_key", "api_secret"}, // checked at config load (litegate -t)
		New: func(cfg map[string]string) (legodns.ChallengeProvider, error) {
			c := vegadns.NewDefaultConfig()
			c.BaseURL, c.APIKey, c.APISecret = cfg["url"], cfg["api_key"], cfg["api_secret"]
			return vegadns.NewDNSProviderConfig(c)
		},
	})
}
```

`legodns` handles the capability declaration (`cert_dns01`) and manifest, required-key validation, forwarding lego's `Timeout()` as the propagation timeout (VegaDNS defaults to 12 minutes; without forwarding, the 2-minute default would cut it short), and classifying constructor failures as `invalid_config`. It matches lego's method set structurally and **does not import lego**, so the plugin picks its own lego version. Full example: [examples/plugins/dns/vegadns](https://github.com/jamesleeon/LiteGate/blob/master/examples/plugins/dns/vegadns).

If the provider is not in lego, or you also need DDNS, implement the interfaces directly as below.

### Step 1: Implement the interfaces + register

Below is a minimal skeleton implementing **both certificate DNS-01 and DDNS**. When you only need one capability, drop the other method group.

```go
package mydns

import (
	"context"
	"fmt"

	"github.com/jamesleeon/LiteGate/pkg/plugin"
	"github.com/rs/zerolog/log"
)

// providerName is the name users put in YAML dns_providers[].type; it must not clash with a built-in name.
const providerName = "mydns"

type provider struct {
	apiKey    string
	apiSecret string
}

// GetName implements the marker interface plugin.DNSProvider
func (p *provider) GetName() string { return providerName }

// --- Capability 1: certificate DNS-01 (implements plugin.CertDNSProvider) ---

func (p *provider) AddTXTRecord(ctx context.Context, domain, token, keyAuth string) error {
	// domain looks like "example.com"; you must add a TXT record on _acme-challenge.<domain> with value keyAuth.
	// Add the record via your DNS API. Honor ctx cancellation (shutdown/timeout).
	return p.upsertTXT(ctx, "_acme-challenge."+domain, keyAuth)
}

func (p *provider) DeleteTXTRecord(ctx context.Context, domain, token, keyAuth string) error {
	// Clean up the TXT above after the challenge passes.
	return p.removeTXT(ctx, "_acme-challenge."+domain, keyAuth)
}

// --- Capability 2: DDNS (implements plugin.DDNSProvider) ---

func (p *provider) Sync(ctx context.Context, domain string, ip string) error {
	// Set the domain's A/AAAA record to ip. The record type is determined by whether ip is IPv4 or IPv6.
	return p.upsertAddr(ctx, domain, ip)
}

// init: auto-register when the package is imported
func init() {
	err := plugin.RegisterDNSProvider(providerName, func(config map[string]string) (plugin.DNSProvider, error) {
		key := config["api_key"]
		secret := config["api_secret"]
		if key == "" || secret == "" {
			return nil, fmt.Errorf("%s: api_key and api_secret are required", providerName)
		}
		return &provider{apiKey: key, apiSecret: secret}, nil
	})
	if err != nil {
		log.Error().Err(err).Str("plugin", providerName).Msg("register DNS provider failed")
	}
}

// The following are stubs; replace with your DNS API calls
func (p *provider) upsertTXT(ctx context.Context, fqdn, value string) error  { /* ... */ return nil }
func (p *provider) removeTXT(ctx context.Context, fqdn, value string) error  { /* ... */ return nil }
func (p *provider) upsertAddr(ctx context.Context, domain, ip string) error  { /* ... */ return nil }
```

### Step 2: Configuration — reference it under `auto_cert.dns_providers`

```yaml
auto_cert:
  enabled: true
  email: admin@example.com
  dns_providers:
    - name: my-cloud              # logical name (referenced by domain routing; may differ from type)
      type: mydns                 # ← your registered plugin name plugin.RegisterDNSProvider("mydns", …)
      enabled: true
      domains: ["*.example.com"]  # domains this provider issues certificates for (DNS-01)
      config:                     # ← the whole map is passed verbatim to the factory's config param
        api_key: "AKxxxx"
        api_secret: "yyyy"
        propagation_wait: "60s"   # optional: DNS-01 propagation wait (see §4)
      ddns:                       # optional: enable DDNS sync
        enabled: true
        sync_a: true
        domains: ["home.example.com"]
```

- **Certificate DNS-01**: when a domain matches `dns_providers[].domains`, the core uses that provider for the DNS-01 challenge (requires the provider to implement `CertDNSProvider`).
- **DDNS**: when `ddns.enabled: true`, the periodic DDNS task calls `Sync` on `ddns.domains` (requires `DDNSProvider`). `DNSSyncRecordRouter` only applies to the cert-manager record-sync path described below.
- The entire `config` `map[string]string` is passed straight to your factory — put all custom parameters here.

---

## 4. Optional capabilities in detail

### 4.1 Custom propagation wait / timeout (certificate DNS-01)

Default behavior: lego polls the authoritative NS to confirm the TXT record has propagated before letting the CA validate; the default total is 2 minutes with a 10-second interval. You can intervene in two ways:

- **Config-level** (no code): set `propagation_wait: "60s"`, `skip_propagation_check: "true"`, `disable_complete_propagation: "true"`, or `recursive_nameservers: "1.1.1.1,8.8.8.8"` in `config` (parsed by `buildDNSChallengeOptions` in [internal/cert/interface.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/cert/interface.go)).
- **Context**: every method receives the ACME order's context; it is cancelled on shutdown or when this node loses the cluster certificate lock, so pass it to your SDK's HTTP calls. Cleanup runs with a context that is not cancelled with the order, so TXT records are still removed.
- **Resolvers**: `auto_cert.propagation_dns` is process-wide (lego v5 shares one resolver set); a provider's `recursive_nameservers` is checked by LiteGate for that provider only.
- **Code-level**: implement `DNSPropagationChecker` to fully take over the waiting logic; implement `DNSOptionalTimeout` to change the total/interval.

```go
func (p *provider) GetTimeout() (time.Duration, time.Duration) {
	return 5 * time.Minute, 15 * time.Second // bump it up for slow DNS
}
```

### 4.2 Custom record-sync routing (`DNSSyncRecordRouter`)

LiteGate has **two paths** that write A/AAAA records, with different interface requirements:

- **Standalone DDNS periodic task** (`auto_cert.dns_providers[].ddns`): goes through `NewProvider` in [internal/ddns/provider.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/ddns/provider.go) and **directly calls `DDNSProvider.Sync(ctx, domain, ip)`**, with the record type determined by whether `ip` is IPv4/IPv6. This path only recognizes `DDNSProvider`.
- **Cert-manager record sync** (e.g. automatic service-host sync, via `CertificateManager.SyncRecordWithProvider`): bridged through `externalCertProviderAdapter.SyncRecord`, which **prefers** `DNSSyncRecordRouter.SyncRecord` (where you get an explicit `recordType`) and falls back to `DDNSProvider.Sync`.

Implement `DNSSyncRecordRouter` when you need fine-grained record-type control on the second path:

```go
func (p *provider) SyncRecord(ctx context.Context, domain, recordType, value string) error {
	// recordType is computed by the core (IPv4→"A", IPv6→"AAAA")
	return p.api.SetRecord(ctx, domain, recordType, value)
}
```

---

## 5. Compiling into the binary (user-owned main)

Just like other plugins, use the "user-owned main" approach — in **your own repository**, create a `main` that blank-imports the plugin package and calls `litegate.Run()`:

```go
// main.go
package main

import (
	"log"

	"github.com/jamesleeon/LiteGate/pkg/litegate"

	_ "your-module/mydns" // ← init() calls RegisterDNSProvider
)

func main() {
	if err := litegate.Run(); err != nil {
		log.Fatalf("litegate exited: %v", err)
	}
}
```

`go build` produces a gateway with the plugin. The one-shot builder supports both published versions and local module replacements:

```bash
litegate build --with your-module/mydns@v1.2.3 -o litegate
litegate build --with your-module/mydns=../your-module -o litegate
```

The right-hand side of a local replacement is the directory containing the plugin's `go.mod`. See [examples/plugin-template](https://github.com/jamesleeon/LiteGate/blob/master/examples/plugin-template) for a copyable starter and [examples/plugins/dns/memory](https://github.com/jamesleeon/LiteGate/blob/master/examples/plugins/dns/memory) for a compilable DNS Provider V2 example. The in-memory provider is for learning and tests only; it does not change authoritative DNS.

> You can also develop in-tree in this repo (put the package in the repo and blank-import it in [cmd/litegate/plugins.go](https://github.com/jamesleeon/LiteGate/blob/master/cmd/litegate/plugins.go)), but **a standalone repo + user-owned main is the recommended approach**.

---

## 6. Things you must watch out for (pitfalls)

1. **Implement capabilities as needed, but using the wrong one fails.** A DDNS-only plugin configured to issue certificates (its domain entered `dns_providers[].domains`) makes the core's `CertDNSProvider` assertion fail and return a clear error — and vice versa. Whatever role you assign a provider, it must have the matching capability.

2. **Choose the right factory.** Use `RegisterDNSProvider` for simple providers that only need `config`. Use `RegisterDNSProviderWithDependencies` when you want LiteGate to inject `*plugin.Dependencies`, currently including `Logger`; `Discovery` is optional/not guaranteed for DNS providers.

3. **You can't override a built-in name.** `RegisterDNSProvider("aliyun", …)` and the like return an error. Built-in names: `aliyun` / `cloudflare` / `tencent` / `tencentcloud` / `huawei` / `huaweicloud`. Pick a non-conflicting name.

4. **Honor `ctx` cancellation.** The `ctx` passed to `AddTXTRecord` / `DeleteTXTRecord` / `Sync` is canceled on gateway shutdown or challenge timeout — pass it to your HTTP calls, don't use `context.Background()`, or you'll hang/leak on shutdown.

5. **`AddTXTRecord`'s `domain` is the base domain.** lego passes in the domain being issued (e.g. `example.com`); you operate on the `_acme-challenge.<domain>` TXT record with value `keyAuth`. On delete, clean up precisely by value to avoid removing TXT records from concurrent challenges.

6. **The DDNS periodic task only calls `Sync`.** The periodic sync driven by `auto_cert.dns_providers[].ddns` only calls `DDNSProvider.Sync(ctx, domain, ip)`, with the record type determined by whether `ip` is IPv4/IPv6 — implementing `DNSSyncRecordRouter` on this path will **not** be called. `DNSSyncRecordRouter.SyncRecord` (with the ready-made `recordType`) applies only to the cert-manager record-sync path (see §4.2).

7. **`config` values are all strings.** A `map[string]string` has no numbers/booleans — write durations as `"60s"` and `time.ParseDuration` them yourself; write switches as `"true"` and check them yourself. Validate in the factory and return an error when key config is missing (surface the problem at startup).

8. **Wildcard certificates must use a DNS Provider.** Wildcard certs like `*.example.com` can't use HTTP-01; a provider implementing `CertDNSProvider` must be responsible for that domain.

---

## 7. Lifecycle and dispatch (how it works)

```
Program start
  └─ plugin package init() → plugin.RegisterDNSProvider("mydns", factory)
     or plugin.RegisterDNSProviderWithDependencies("mydns", factory)        [name lands in the public registry]
Config load
  └─ auto_cert.dns_providers[].type references the name
Certificate issuance/renewal (a domain matches dns_providers[].domains)
  └─ cert.GetCertProvider(type, config)
       ├─ Hit in the built-in registry? → use built-in
       └─ Otherwise → public registry factory(config, deps) → assert CertDNSProvider → adapt to internal CertProvider
            └─ lego calls AddTXTRecord → wait for propagation → CA validates → DeleteTXTRecord
DDNS periodic sync (ddns.enabled, periodic / IP change)
  └─ ddns.NewProvider(type, config) → assert DDNSProvider → Sync(ctx, domain, ip)
Cert-manager record sync (e.g. service-host auto sync, SyncRecordWithProvider)
  └─ cert.GetSyncProvider → adapter prefers DNSSyncRecordRouter.SyncRecord, falls back to DDNSProvider.Sync
```

- When a built-in provider registers via the internal `RegisterProvider`, it **first reverse-checks the public registry to prevent name clashes, then reserves the name in the public registry** (see [internal/cert/interface.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/cert/interface.go) and [internal/ddns/registerprovider.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/ddns/registerprovider.go)).
- A third-party provider is bridged to the internal `CertProvider` by `externalCertProviderAdapter` ([internal/cert/interface.go](https://github.com/jamesleeon/LiteGate/blob/master/internal/cert/interface.go)): `WaitForPropagation` probes `DNSPropagationChecker`; `SyncRecord` prefers `DNSSyncRecordRouter` then falls back to `DDNSProvider.Sync`; `GetTimeout` probes `DNSOptionalTimeout` (defaulting to 2min/10s).

---

## Cheat sheet

| I want to… | How |
|---|---|
| Add certificate issuance for a new DNS service | Implement `plugin.CertDNSProvider`, register with `plugin.RegisterDNSProvider` or `plugin.RegisterDNSProviderWithDependencies`, configure `dns_providers[].type` + `domains` |
| Add DDNS for a new DNS service | Implement `plugin.DDNSProvider`, register with `plugin.RegisterDNSProvider` or `plugin.RegisterDNSProviderWithDependencies`, configure `dns_providers[].ddns` |
| Support both certificates + DDNS | One provider implements both interface groups |
| Customize propagation wait | Implement `plugin.DNSPropagationChecker`, or set `propagation_wait` etc. in `config` |
| Customize propagation timeout | Implement `plugin.DNSOptionalTimeout` |
| Fine-grained record type on cert-manager sync | Implement `plugin.DNSSyncRecordRouter` (with ready-made `recordType`, see §4.2) |
| Fail fast on bad plugin config | Implement `plugin.DNSConfigValidator`; LiteGate calls it when creating external cert/DDNS providers |
| Expose plugin metadata | Implement `plugin.DNSProviderDescriptor` for docs/UI/preflight tools |
| Support preflight health checks | Implement `plugin.DNSHealthChecker` |
| Read plugin config | Factory param `config map[string]string` (values are all strings) |
| Compile into the binary | User-owned `main`, blank-import the plugin package + `litegate.Run()`, `go build`, or `litegate build --with` |
