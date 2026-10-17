# DDNS (Dynamic DNS)

## Multiple nodes and internal DNS

A/AAAA updates preserve the record set: each node ensures its own address is present without replacing other nodes' addresses. Built-in Alibaba, Tencent and Cloudflare providers append records; third-party providers must preserve the same semantics. With Consul/LiteMesh certificate storage, distributed locks coordinate updates by provider, hostname and record type. Identical updates are idempotent and later DNS checks repair manually deleted records.

```yaml
litemesh:
  enabled: true
  roles:
    cert_storage: true
```

Multiple A/AAAA addresses provide DNS rotation, not active health checking. Resolver/client caches can retain failed addresses. LiteGate persists this node's ownership in `ddns-owned.json`: after publishing a new address it withdraws its old values, and a completed sweep removes values for domains no longer served. A stopped node cannot withdraw its own records, so clean those up manually. Keep the ownership file across restarts. Renaming a provider with unchanged credentials is supported for new ownership records; if its original DNS account cannot be identified, restore that configuration or remove stale values manually.

`ddns.domains` wildcards select providers for loaded exact Site/Stream names. They do not create literal wildcard A/AAAA owners; requests containing `*` are skipped and record writers reject wildcard owners. Configure explicit IPv4/IPv6 values when the node should avoid public-IP probes.

Internal DNS uses `auto_cert.dns_update`, publishing the gateway's internal IP into LiteMesh KV for LiteDNS rather than updating a public DNS provider. Enable LiteMesh and align the key prefix with LiteDNS. Omitted ip detects the outbound interface address; omitted node_id uses the hostname. KV TTL is three times heartbeat_interval.

```yaml
auto_cert:
  dns_update:
    enabled: true
    auto_service_host_sync: true
    ip: ''
    key_prefix: litedns/v1/records/
    node_id: ''
    record_ttl: 30
    heartbeat_interval: 30s
```

See [internal DNS and multiple nodes](../../dynamic-dns-multi-node.md).

For another DNS service, see [Add a DNS provider](dns-providers.md): compatible libdns modules can be compiled in with `litegate build --dns` without writing plugin code.

LiteGate features an integrated Dynamic DNS (DDNS) engine that automatically synchronizes the gateway's public WAN IP address with the A and AAAA records of your DNS cloud provider. Default builds include Alibaba Cloud DNS, Tencent Cloud DNSPod, and Cloudflare. Huawei Cloud DNS and other providers require third-party DNS provider plugins compiled on demand.

---

## 1. Primary Operational Scenarios

- Gateways deployed in networks with dynamic WAN IPs (such as residential broadband, offices, or NAT VPS).
- Pointing the exact hostnames of loaded Sites/Streams to the active gateway node IP.
- Seamless pairing with Let's Encrypt DNS-01 validation to achieve fully automated DNS updates and certificate renewals.

---

## 2. Configuration Settings

DDNS configurations are nested inside individual global `dns_providers` profiles under the `auto_cert` block:

```yaml
auto_cert:
  enabled: true
  email: admin@example.com
  dns_providers:
    - name: "aliyun-main"
      type: "aliyun"
      enabled: true
      domains: ["*.example.com", "example.com"]
      ddns:
        enabled: true
        ipv4: ""               # Omit to auto-probe public WAN IPv4
        ipv6: ""               # Omit to auto-probe public WAN IPv6
        sync_a: true           # Synchronizes DNS 'A' records (IPv4)
        sync_aaaa: true        # Synchronizes DNS 'AAAA' records (IPv6)
        # domains is optional. When omitted, the parent domains select the provider.
        # Wildcards only match loaded Sites/Streams; exact discovered hosts are written.
      config:
        access_key_id: "LTAI..."
        access_key_secret: "..."
```

---

## 3. Mapped Cloud DNS Providers

| DNS Provider | `type` Identifier | Mapped Configuration parameters |
| :--- | :--- | :--- |
| **Alibaba Cloud DNS** | `aliyun` | `access_key_id`, `access_key_secret` |
| **Tencent Cloud DNSPod** | `tencent` / `tencentcloud` | `secret_id`, `secret_key` |
| **Cloudflare** | `cloudflare` | `api_token` |

> [!TIP]
> Beyond the built-in providers above, you can integrate **any** DNS service through a **DNS Provider plugin** (with your own `type` name). The same plugin can also handle ACME certificate DNS-01 challenges. See the [DNS Provider Plugin Authoring Guide](../../dns-provider-plugin-guide.md).

---

## 4. Automated WAN IP Probing

When the `ipv4` or `ipv6` parameters are left blank, LiteGate executes an automated WAN IP probing pipeline:

1. The gateway first scans local interfaces for a public address, excluding private and CGNAT (`100.64.0.0/10`) addresses. Linux also excludes temporary, deprecated, tentative and DAD-failed IPv6 addresses using `/proc/net/if_inet6`; stable-privacy addresses remain eligible. An external observation cannot reintroduce an excluded local address. If no usable address exists, it queries `https://api.ipify.org` over IPv4 or `https://api6.ipify.org` over IPv6, bypassing HTTP proxies. Each source has a five-second HTTP timeout; results are shared for one minute by address family and source list. Failures are logged and exposed in DDNS status.
2. Upon successfully obtaining the IP, it compares the value against active DNS records.
3. If a change is detected, LiteGate calls the DNS Provider's API to update the DNS records.

> [!NOTE]
> If your environment is provisioned with a static WAN IP, declare it explicitly inside `ipv4` or `ipv6` parameter fields to completely bypass external HTTP polling overhead.

Set `ddns.ipv4_sources` and `ddns.ipv6_sources` to replace the default reflection endpoints. Each accepts up to eight HTTP(S) URLs returning a plain-text public address; sources are tried in order until one succeeds. Use services reachable from your network, for example:

```yaml
ddns:
  enabled: true
  sync_a: true
  sync_aaaa: true
  ipv4_sources: ["https://4.ipw.cn", "https://api.ipify.org"]
  ipv6_sources: ["https://6.ipw.cn", "https://api6.ipify.org"]
```

Persist `ddns-identity.key` alongside `ddns-owned.json`. Ownership fingerprints use HMAC-SHA-256 with this random per-node key, so the JSON does not contain an unkeyed hash of credentials. Losing or corrupting the key disables rename recovery; normal cleanup through an unchanged provider name remains available. On Linux without readable IPv6 address metadata, configure `ipv6` explicitly instead of relying on automatic selection.

Wildcard entries such as `*.example.com` select the DNS provider for discovered hosts. LiteGate
still writes only exact Site/Stream owners such as `refund.example.com`. A synchronization request
whose owner itself contains `*` is skipped, and the low-level record writer rejects wildcard A/AAAA
owners as a second safety boundary. Certificate wildcard scope never implicitly creates wildcard
A/AAAA records.

---

## 5. Internal DNS (LiteMesh KV → LiteDNS)

DDNS publishes the public IP to your DNS provider. `dns_update` publishes this gateway's internal IP per domain into LiteMesh KV, where LiteDNS answers internal clients, so the same domain and certificate reach the gateway directly on the LAN. Requires litemesh.

```yaml
auto_cert:
  dns_update:
    enabled: true
    auto_service_host_sync: true       # Publish every loaded site/stream domain
    ip: ""                             # Omit to auto-detect the default-route interface IP
    key_prefix: "litedns/v1/records/"  # Must match LiteDNS
    node_id: ""                        # Defaults to the hostname
    record_ttl: 30
    heartbeat_interval: 30s            # KV TTL is 3x this value
```

See [Internal DNS Publishing - Multi-Node Gateway Support](../../dynamic-dns-multi-node.md).
