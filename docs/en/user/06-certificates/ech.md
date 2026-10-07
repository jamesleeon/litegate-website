# Encrypted ClientHello (ECH)

ECH encrypts the browser-to-LiteGate ClientHello. The outer SNI contains the selected group's `public_name`; after decryption LiteGate selects the certificate, TLS policy and site using the inner name. Existing ACME certificates continue to work.

## Setup guide: server, DNS and client

The complete flow is: LiteGate installs ECH keys and publishes HTTPS DNS records, the resolver preserves their `ech` parameters, and the browser uses them to encrypt ClientHello. Enabling ECH on the server does not force ordinary clients to use it.

### Server preparation and legacy compatibility

Enable `auto_cert`, configure an Aliyun/Cloudflare DNS provider covering the hidden sites and public name, and grant HTTPS-record management permissions. Serve `websecure` on TCP 443 and allow TLS 1.3. Hidden sites need direct A/AAAA records pointing to the TLS terminator; persist and back up the ECH state. A CDN or proxy terminating browser TLS must itself implement ECH.

Existing single-group configurations remain supported. Keep your existing provider and site definitions; this main-config block does not require site-level `ech: true`:

```yaml
ech:
  enabled: true
  public_name: ech.example.com
  dns_provider: aliyun-main
  domains:
    - litemesh.example.com
    - dashboard.example.com
```

Every listed domain needs a local HTTPS site, including sites eventually loaded from KV. Omitted storage retains the legacy automatic selection: Consul/LiteMesh KV when config_watch is enabled, otherwise file storage. Do not change storage or delete keys just to match a new example. Keep the original state and prefixes; see migration notes below. Root legacy public_name/dns_provider/domains cannot be mixed with groups. Site-level false does not cancel a legacy global domains entry; changing that list requires a restart.

### Start and verify DNS

Restart after changing global ECH/provider settings. Run `litegate -t -config config.yaml`, then start the gateway. In KV mode, -t checks local configuration without fetching remote sites; complete validation is deferred to runtime. Publication waits for valid initial KV snapshots. Look for `ECH keys loaded` and per-domain `ECH HTTPS record published`; resolve errors identifying invalid_keys, certificates or providers.

```bash
dig app.example.com HTTPS
# Replace with your resolver's actual address and port.
dig @192.168.50.110 -p 53 app.example.com HTTPS
```

Expect HTTPS type 65 with `ech="..."`, not just an A record. The ECHConfigList is public configuration; Base64 does not encrypt DNS transport. A successful DNS lookup alone does not prove the browser used ECH.

### Configure the browser

Use your own resolver's DoH URL, for example `https://dns.example.com/dns-query`, with a valid certificate and standard wire-format DoH GET (`dns=`) / POST (`application/dns-message`) support. A JSON name/type lookup is a diagnostic interface, not the URL to paste into browser DNS settings.

- Vivaldi: Settings → Network → enable DNS Lookup Over HTTPS and choose your custom provider. [Official instructions](https://vivaldi.com/blog/tips/tip-739/)
- Other browsers: configure their secure DNS/DoH provider; ECH use depends on browser version, policy and proxies. [Firefox ECH guidance](https://support.mozilla.org/en-US/kb/understand-encrypted-client-hello)
- UDP/TCP DNS can also return ECH configuration, but pointing system DNS at CamoDNS does not guarantee the browser uses those records. DoH is not a protocol requirement of ECH; verify the actual client path. Plain DNS still exposes query names, whereas DoH/DoT encrypt DNS transport.

Fully quit and restart the browser, then visit the original site URL, not the public name.

### CamoDNS scripts and diagnostics

Do not reject HTTPS queries or remove HTTPS records in post-processing for ECH-enabled sites. For a two-domain test, add exceptions inside the existing HTTPS rejection branch (match the actual domain format supplied to your script):

```javascript
if qtype == "HTTPS" {
    if domain == "app.example.com" || domain == "dashboard.example.com" {
        return { "action": "continue" }
    }
    return { "action": "reply", "mode": "reject", "reason": "noerror" }
}
```

Save and clear the script cache. Post-script filter_type must not strip HTTPS records for these sites. Filtering DNS type 65 does not block all HTTPS, HTTP/3 or third-party DoH traffic.

For CamoDNS deployments offering JSON lookup:

```bash
curl 'https://dns.example.com/dns-query?name=app.example.com&type=65'
```

Question.type and Answer.type should be 65 with an ech parameter. Question.type=1 indicates conversion to an A query: check numeric type parsing and the deployed version before blaming cache collisions. Displaying decoded JSON in a terminal is normal even over encrypted transport.

### Verify ECH use

If the browser's Security panel reports Encrypted ClientHello enabled, that connection uses ECH. A fresh packet capture should show the public name as outer SNI while the original site opens normally. Server-side decrypted ServerName/HTTP Host and the address bar retain the original site name.

Use Wireshark's `tls.handshake.extensions_server_name` filter; a target-IP/TCP-443 filter is useful for TCP tests. HTTP/3 uses UDP 443. An ECH extension alone may be GREASE, and TLS 1.3 or a successful page load alone does not establish ECH use.

Empty HTTPS answers call for checking scripts, upstream failures, caches and local overrides. If DNS has ech but SNI remains the original name, check browser DNS settings, policy, proxies and reused connections. invalid_keys logs identify KV readiness blockers. Deleting a site still listed in global domains suspends publication and retains existing records rather than automatically withdrawing them.

## New configuration: groups and site selection

Add to the main `config.yaml`, reusing an enabled DNS provider:

For packet capture diagnostics, the presence of an `encrypted_client_hello` extension alone does not prove ECH worked: browsers can send a random GREASE extension. If the outer SNI still contains the hidden site name rather than the configured public name, that connection exposed the site name. Query the site's HTTPS (type 65) record through the browser's actual DNS/DoH resolver, then check browser ECH policy, secure DNS, proxy/hosts overrides, DNS caches and reused connections. Capture a fresh connection and verify the outer SNI is the group's `public_name`. After decryption, server-side ServerName and HTTP Host still contain the original site name.

```yaml
auto_cert:
  enabled: true
  email: admin@example.com
  certs_dir: ./certs
  dns_providers:
    - name: aliyun-main
      type: aliyun
      enabled: true
      domains: ["*.example.com", "example.com"]
      config:
        access_key_id: "..."
        access_key_secret: "..."
    - name: cloudflare-main
      type: cloudflare
      enabled: true
      domains: ["*.example.net"]
      config:
        api_token: "..."

ech:
  enabled: true
  groups:
    - public_name: ech.example.com
      dns_provider: aliyun-main
    - public_name: ech.example.net
      dns_provider: cloudflare-main
  storage: file
  # For shared storage:
  # storage: kv
  # kv:
  #   provider: litemesh  # or consul, reuse the existing connection
  #   key_prefix: litegate/ech/mycluster/
  # key_prefix: litegate/ech/mycluster/
```

Set `ech: ech.example.com` or `ech: ech.example.net` alongside site: to select a group. Global `ech.domains` is optional and remains compatible. `public_name` and `domains` must be concrete ASCII DNS names, without wildcards, IP addresses or ports. Use a dedicated public name. ECH defaults to disabled, requires `auto_cert.enabled`, and supports built-in `aliyun` and `cloudflare` providers and registered DNS plugins advertising `https_records` and implementing `plugin.HTTPSDNSProvider` with the `websecure` TCP listener on port 443. Site TLS policies must allow TLS 1.3. ECH/provider configuration changes require a restart.

Each published site needs existing direct A/AAAA records pointing to this instance and must not use CNAME. Cloudflare records must be DNS only, without proxying. The provider needs permission to query, create, update and delete HTTPS records, and its DNS plan must support that record type. Existing unmanaged HTTPS records cause an error instead of being overwritten. Address records are never modified by ECH.

LiteGate reuses a covering public-name certificate or automatically adds that name to the selected provider's certificate issuance group. DNS-01 does not require an address record for the public name; adding one is useful for diagnosis. Once HTTPS is running and the public-name certificate is valid, it publishes:

```text
app.example.com. 600 IN HTTPS 1 . alpn="h2" ech="<Base64 ECHConfigList>"
```

Cloudflare reuses `api_token`/`token` credentials. Aliyun recognizes public suffixes such as `example.com.cn`; for a delegated zone set `config.zone` explicitly.

Private keys persist in `auto_cert.certs_dir/ech/<public_name>/state.json`, falling back to `tls.certs_dir`. Back up and persist this directory. Unix permissions are 0700 for newly created directories and 0600 for files; configure appropriate directory ACLs on Windows. KV state is encrypted with auto_cert.storage_secret, which must match across nodes and contain at least 32 bytes. The local recovery copy still contains private keys. Initial KV creation imports local state with CAS.

Keys rotate every 7 days. New keys are persisted and installed before DNS publication. Each domain has independent publication state: healthy domains are checked every 30 minutes; failed domains retry every minute without blocking other domains or rotation. Old keys remain accepted for 14 days after no domain references them in a confirmed or uncertain DNS write. Potentially advertised keys remain pinned. Exhausting all 256 config IDs during a prolonged outage warns and defers new key generation while existing keys and healthy publication remain usable. Restarts reuse saved keys; corrupt state fails startup instead of silently generating replacements. Disabling a site flag or deleting a site withdraws its owned HTTPS records on live reconciliation. Legacy global domains remain enabled even if a site flag is false.

Auto storage reuses Consul/LiteMesh connections only when config_watch is enabled. A publisher lease selects one writer; followers consume KV watch/blocking query notifications and refresh within one five-second cycle. Rotation stages keys at least 15 seconds before DNS publication. All group members must use identical public name, provider, sites, prefix and storage secret, and synchronize successfully before receiving traffic. Explicit file storage supports one instance; a process lock prevents concurrent access to the same state directory. ECH belongs on the service that actually terminates client TLS, including when a CDN, Connect tunnel or L4 passthrough is involved. The public name is reserved for local TLS decryption in shared-port SNI routing and must not be the Connect control hostname.

Before disabling ECH, stop every instance in the KV group and run `litegate ech withdraw -config config.yaml`. The command needs exclusive state access and the original provider credentials. It removes only HTTPS records belonging to saved keys, preserves keys, and clears publication state only after every withdrawal succeeds; partial failures can be retried. Wait at least the record TTL (600 seconds by default, allowing for client caches), then restart with ECH disabled. Removing the configuration does not automatically withdraw records. When changing the public name/provider, withdraw using the original configuration, wait for caches to expire and archive the old state file; otherwise startup rejects mismatched state. For continuous service while waiting, manual DNS withdrawal is possible, but complete disabling before the next full check republishes the record.

Successful publication is checked every 30 minutes while configuration, protocols and keys remain unchanged; failures retry every minute. HTTP/3 availability adds `alpn="h2,h3"`. Public-name certificate domains are derived only for runtime use and never written back into provider configuration. Waiting for a certificate for more than 5 minutes produces a warning.

Post-load validation requires a local HTTPS site for every hidden domain and rejects passthrough, L4 or Connect control hostnames and TLS policies that disallow TLS 1.3. The public name cannot be a hidden domain. KV initialization suspends DNS publication until the complete site configuration is valid and logs the reason.

Validation reads metadata snapshots without compiling live routes. Passthrough routes restricted to non-HTTP ALPN, such as `mqtt`, do not conflict with HTTP sites; routes matching `h2` or `http/1.1` still must not cover hidden names. Routes and L4 streams covering the public name generate a warning because the mux reserves it for local TLS.

If runtime site validation fails, subsequent DNS publication is suspended; **already published HTTPS records are not automatically withdrawn**. Identical validation or shadow warnings repeat at most every 30 minutes. Changed failures, or failures recurring after recovery, warn immediately. Use the withdrawal command when needed, and investigate site deletion or disappearing discovered services rather than treating existing DNS records as proof of a working site.

Clients must support ECH and receive HTTPS DNS responses containing `ech`. DoH/DoT also avoids exposing names through plaintext DNS. Ordinary TLS clients remain supported. Successful page loading alone does not prove ECH was accepted.

For deployment, check `ECH keys loaded` and `ECH HTTPS record published` logs, query `dig app.example.com HTTPS`, and use an ECH-capable client or packet capture to verify the outer SNI. Publication failures log the cause and retry automatically. Tests exercise actual HTTP/1.1, HTTP/2 and HTTP/3 ECH handshakes, inner TLS policy, authenticated retry, TLS 1.2 compatibility, durable rotation, restart recovery and DNS ownership.

References: [Go TLS](https://pkg.go.dev/crypto/tls#EncryptedClientHelloKey), [Caddy ECH](https://caddyserver.com/docs/automatic-https#encrypted-clienthello-ech), [Cloudflare HTTPS records](https://developers.cloudflare.com/dns/manage-dns-records/reference/dns-record-types/#https).


Each group has independent keys, rotation, DNS publication and a publisher lease. Default KV keys are litegate/ech/<public_name>/state and publisher. Root key_prefix is a parent directory; a group override is an exact prefix and must be unique. Reuse existing connection credentials and LiteMesh namespace. One group permits ech: true; multiple groups require an explicit public name. Any public name is prohibited as a hidden name.

Legacy single-group configs remain supported, cannot be mixed with groups, and retain their state path and litegate/ech/default/ prefix. Matching legacy local state is reused when upgrading. Existing KV deployments should explicitly set the matching group's key_prefix to litegate/ech/default/ to preserve shared state; stop old-config instances before migrating. Site transfers withdraw old records before the new group publishes. Group config changes require restart.

Use litegate ech withdraw -config config.yaml -public-name ech.example.com for one group, or omit public-name to withdraw every configured group. Stop every instance in the affected KV group first. Withdraw and wait for caches before removing a group; archive both local and KV state when changing public name/provider/prefix.

Sites must be covered by the selected DNS provider domains (wildcards match one label); uncovered names are rejected when loading. Withdrawal always proceeds before publication. Only names still claimed by another group wait and warn, so groups can exchange names without blocking independent domains. KV connection settings and LiteMesh namespace reuse the selected existing connection; DNS and KV providers are independent.

DNS plugins manage only provider HTTPS record APIs. ECH keys, rotation, encrypted KV synchronization and publication state remain inside LiteGate. See the [plugin authoring guide](../../dns-provider-plugin-guide.md).
