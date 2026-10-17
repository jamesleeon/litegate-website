# L4 SNI Routing on Port 443 Combined with L7: Recipes

On one TCP/443, the SNI (and ALPN) in the TLS ClientHello decides where a connection goes: some are passed through untouched to other programs, some have TLS terminated by LiteGate and become layer-4 byte streams, and the rest enter LiteGate's own HTTPS sites. Starting from common caddy-l4 configurations, this page shows the LiteGate equivalents and more combinations.

For mechanism details, hot reload and troubleshooting see [HTTPS and L4 TCP on one port 443](shared-443-l4-stream.md); for field definitions see [Entrypoints](../03-configuration/entrypoints.md) and the [Stream configuration reference](../03-configuration/stream-config.md).

## 1. Migrating from caddy-l4: an L4 passthrough service and websites on one 443

A typical caddy-l4 configuration:

```caddyfile
layer4 {
    :443 {
        @tls-regexp tls sni_regexp ^a.example.com$
        route @tls-regexp {
            proxy localhost:444      # a.example.com traffic to a backend L4 service
        }
        @tls-any tls
        route @tls-any {
            proxy localhost:1234     # everything else to caddy's own HTTPS
        }
    }
}
```

The LiteGate equivalent:

```yaml
# config.yaml
entrypoints:
  websecure:
    address: ":443"
    tls: true
    routes:
      - name: a-service
        match:
          sni: a.example.com
        handle:
          proxy: tcp://127.0.0.1:444
```

No "everything else" rule is needed: connections that match no route go straight into LiteGate's built-in HTTPS pipeline and are handled by the sites in `sites/`.

| | caddy-l4 | LiteGate |
|---|---|---|
| Remaining traffic to websites | `proxy` to local 1234, an extra TCP hop | Handed to HTTPS within the same process, no second hop |
| Client IP seen by websites | Port 1234 needs PROXY protocol for the real IP | The real IP natively |
| Domain matching | Write your own regex | Exact, `*.` wildcard, regex and ALPN, with a fixed priority |
| Changing routes | Reload configuration | Atomic hot update without rebinding 443 |
| L4 governance | Separate matchers | Named Streams: ACLs, load balancing, service discovery, session limits, metrics |

## 2. Three ways to handle a match

Once an SNI matches, there are three ways to say who handles it:

| Form | TLS | Capabilities | Use for |
|---|---|---|---|
| Entrypoint route `handle.proxy` | Passed through; the backend does the handshake | A single target (TCP or Unix socket), optional PROXY protocol | The simplest passthrough, such as a self-hosted TCP/TLS proxy or a service with its own certificate |
| Entrypoint route `handle.stream: <name>` | Decided by the Stream | Everything a Stream can do | When you need manual match conditions (regex, ALPN) plus Stream features |
| A Stream with its own `entrypoints` + `hostnames` | Decided by the Stream | Everything a Stream can do, with routes and certificate domains generated | **Recommended**: the domain is written once |

Unmatched connections → L7 HTTPS sites.

## 3. Combinations

### 3.1 Passthrough: the certificate stays on the backend

This is the form from section 1. The backend speaks TLS from the first byte and must hold the domain's certificate itself.

Plan how the backend gets certificates: LiteGate occupies port 80, so the backend can't complete HTTP-01; the domain is passed through on 443, so TLS-ALPN-01 must be answered by the backend too. Usually the backend uses DNS-01, or you switch to the next form and let LiteGate manage certificates.

When the backend supports PROXY protocol, the real client address can be passed on:

```yaml
        handle:
          proxy: tcp://127.0.0.1:444
          proxy_protocol: 2     # the backend must parse it, or it treats the header as data
```

### 3.2 Termination: LiteGate manages certificates, the backend receives plaintext

When the backend only needs to handle plaintext TCP (or can turn its own TLS listener off), let a Stream terminate TLS:

```yaml
# streams/tunnel.yaml
name: tunnel
listen: false
entrypoints: [websecure]
hostnames: [tunnel.example.com]
protocol: tcp
upstream: tcp://127.0.0.1:10000
enabled: true
tls:
  enabled: true
  auto_cert: true        # shares the certificate pool with HTTPS sites; an existing *.example.com is reused
```

`hostnames` decides both the SNI route and the certificate domains. Certificates are requested and renewed exactly as for HTTPS sites, and the backend no longer deals with them.

### 3.3 One SNI, several backends

Passthrough can be load-balanced or use service discovery too, written as a Stream:

```yaml
# streams/tls-pool.yaml
name: tls-pool
listen: false
entrypoints: [websecure]
hostnames: [api-tls.example.com]
protocol: tcp
enabled: true
lb_policy: round_robin
backends:
  - {upstream: 10.0.0.11:8443}
  - {upstream: 10.0.0.12:8443}
```

`service_name` can also fetch backends dynamically from Consul, LiteMesh and other registries, so instances coming and going need no configuration change; see the [Stream configuration reference](../03-configuration/stream-config.md#stream-entry-and-upstreams).

### 3.4 One domain split by protocol (ALPN)

Browsers send `h2` / `http/1.1` in the ClientHello, and other clients can send their own ALPN. So one domain can serve half as a website and half as layer 4:

```yaml
entrypoints:
  websecure:
    address: ":443"
    tls: true
    routes:
      # PostgreSQL 17+ (sslnegotiation=direct) → database
      - name: pg
        match:
          sni: db.example.com
          alpn: postgresql
        handle:
          stream: pg
```

- A browser opening `https://db.example.com` → ALPN doesn't match → L7 site (for example the database's web console);
- `psql "host=db.example.com sslnegotiation=direct"` → the `pg` Stream.

An in-house client only needs a custom ALPN in its TLS configuration (such as `myproto/1`) to share the domain and certificate with a website the same way.

### 3.5 Wildcards and regexes: onboarding in bulk

```yaml
entrypoints:
  websecure:
    address: ":443"
    tls: true
    routes:
      # One subdomain per tenant, all passed through to the tenant cluster's entry
      - name: tenants
        match:
          sni: "*.tenant.example.com"
        handle:
          proxy: tcp://10.1.0.10:443

      # Numbered nodes: node-1.example.com, node-23.example.com ...
      - name: nodes
        match:
          sni_regex: 'node-[0-9]+\.example\.com'
        handle:
          stream: node-pool
```

`sni_regex` matches the whole name case-insensitively; no `^` or `$` needed. Priority is fixed: **exact domain → longest wildcard → regex → ALPN-only**. So you can use a broad wildcard as a fallback and pull individual subdomains back with exact names:

```yaml
      - name: tenant-special
        match:
          sni: vip.tenant.example.com     # exact wins over *.tenant.example.com above
        handle:
          proxy: tcp://10.1.0.20:443
```

### 3.6 Tightening the public entry

```yaml
entrypoints:
  websecure:
    address: ":443"
    tls: true
    on_non_tls: reject    # first packet isn't TLS (scanners, plaintext protocols): disconnect
    on_no_sni: reject     # connections by IP without SNI: disconnect
    inspect:
      timeout: 5s
      per_ip_pending: 16  # connections per source IP allowed in handshake inspection at once
```

Access control for layer-4 services goes on the Stream:

```yaml
# streams/admin-tunnel.yaml
ip_restriction:
  allow_ips: ["203.0.113.0/24"]
max_sessions: 200
idle_timeout: 600
```

HTTP sites keep using WAF, authentication, rate limiting and other L7 middleware. On one port 443, each kind of traffic uses its own governance.

### 3.7 With another layer-4 load balancer in front

When LiteGate sits behind a cloud LB or HAProxy, have the entrypoint accept PROXY protocol to recover real addresses. SNI routing, L7 sites and passthrough backends all use the recovered address:

```yaml
entrypoints:
  websecure:
    address: ":443"
    tls: true
    proxy_protocol:
      accept: true
      required: true
      trusted: [10.0.0.0/8]   # trust only the LB's range
    routes:
      - name: a-service
        match: {sni: a.example.com}
        handle:
          proxy: tcp://127.0.0.1:444
          proxy_protocol: 2   # pass the recovered address on to the backend
```

### 3.8 Internal services by SNI through a tunnel

A Cloud LiteGate can hand an SNI to an internal Home node through a Connect tunnel, with no inbound port opened internally. These routes are created dynamically by Connect registrations and aren't written in `routes`; see [LiteGate Connect configuration and rollout](connect.md).

## 4. Priority at a glance

A new connection's destination is decided in this order:

1. First packet isn't TLS → `on_non_tls` (`http` hands it to the HTTPS service to return an error / `reject` disconnects);
2. No SNI → `on_no_sni`; when not rejected, only ALPN-only routes can still match, otherwise L7;
3. The Connect control-plane domain → Connect;
4. Exact domain (for the same domain, routes matching ALPN win over routes without ALPN);
5. Longest `*.` wildcard;
6. `sni_regex`, in configuration order;
7. ALPN-only routes;
8. Nothing matched → L7 HTTPS sites.

Routes generated from Stream `hostnames` take part in steps 4 and 5. For the same pattern, rules written explicitly in `routes` win.

## 5. Notes

- **`default` can only be `http`.** There's no switch for "send everything else to another program". Don't use `sni_regex: '.+'` as a fallback: L7 sites aren't in the SNI routing table, so that regex swallows connections meant for websites. To hand a set of domains to an old service, list their exact names or wildcards.
- **Don't repeat a domain on both L4 and L7.** When one SNI is both a Stream `hostnames` entry and an HTTPS site domain, L4 takes over first and the site gets no traffic. LiteGate logs the conflict at startup and on hot reload but doesn't choose for you. If one domain really needs both, split by ALPN as in 3.4.
- **HTTP/3 doesn't take part.** It runs on UDP/443 with a separate listener; everything here is about TCP/443.
- **ECH and missing SNI.** With ECH the gateway sees only the outer SNI; clients connecting by IP send no SNI and can only be handled by ALPN or `on_no_sni`.
- **The first packet must be TLS.** Plaintext SSH, native MySQL TLS and older PostgreSQL SSLRequest can't be routed by SNI; for alternatives see [protocol limitations](shared-443-l4-stream.md#9-protocol-limitations).
- **Once any route exists, every connection goes through ClientHello inspection first**, including those that end up at websites. When a CDN origin or corporate NAT shares one IP, raise `per_ip_pending` to the real handshake peak.

## 6. Related docs

- [HTTPS and L4 TCP on one port 443](shared-443-l4-stream.md)
- [Entrypoints](../03-configuration/entrypoints.md)
- [Stream configuration reference](../03-configuration/stream-config.md)
- [Auto-Cert](../06-certificates/auto-cert.md)
- [Forward and Connect overview](forward-and-connect.md)
