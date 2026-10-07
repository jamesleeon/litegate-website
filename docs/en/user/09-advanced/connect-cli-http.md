# Publish an HTTP Service with the CLI

`litegate connect http` publishes a single LAN HTTP/HTTPS upstream, such as a NAS, audit service, or development server. Home initiates the connection to Cloud, so it needs no inbound port and no LiteGate Site configuration.

## How it works

```text
Browser --HTTPS--> Cloud LiteGate --Connect tunnel--> CLI --HTTP/HTTPS--> LAN upstream
```

Public TLS terminates on Cloud. The Dashboard therefore reports two separate states:

- **Registration**: whether Cloud accepted the hostname and the tunnel is online;
- **Cloud TLS**: whether Cloud has a usable certificate for that hostname.

Both must be healthy before public HTTPS works. A successful CLI registration alone does not prove that TLS is ready.

## 1. Configure Cloud

Generate a token:

```bash
litegate connect token --output /etc/litegate/secrets/home-connect.token
```

Authorize the peer in the Cloud configuration:

```yaml
connect:
  server:
    enabled: true
    hostname: connect.example.com
    path: /_litegate/connect/v1
    peers:
      home:
        token_file: /etc/litegate/secrets/home-connect.token
        allowed_domains:
          - "*.home.example.com"
        max_sites: 20
        max_connections: 512
        sessions: 2

auto_cert:
  enabled: true
  email: ops@example.com
  on_demand:
    enabled: true
    max_certs_per_hour: 10
    max_certs_per_day: 50
```

`allowed_domains` is the peer's authorization boundary. Each CLI process must register one **exact hostname**; HTTP registrations cannot contain wildcard hostnames. The wildcard above only describes the allowed namespace.

## 2. Configure DNS and certificates

Point both `connect.example.com` and the published `audit.home.example.com` hostname at Cloud.

Cloud can provide TLS in these ways:

| Method | Best for | Dashboard result |
| --- | --- | --- |
| Installed exact or SAN certificate | Existing enterprise certificates | `ready · exact` |
| Installed `*.home.example.com` wildcard | Many services under one suffix; recommended | `ready · wildcard` |
| On-demand with HTTP-01 | A few exact names and public access to Cloud ports 80/443 | `eligible/issuing`, then `ready` |
| On-demand with a matching DNS provider | DNS-01 or environments where HTTP-01 is unavailable | Shows `dns-01:<provider>` |

When `auto_cert.on_demand.enabled` is enabled, Cloud asynchronously pre-issues a missing certificate after accepting a new CLI HTTP registration. The registration ACK does not wait for ACME, and hourly/daily issuance limits still apply. An existing exact, SAN, or wildcard certificate prevents duplicate issuance.

Connect does not enable on-demand TLS by itself. Without on-demand, install a certificate first or the Dashboard will report `missing`.

## 3. Run the CLI on Home

Copy the token file securely to Home, then run:

```bash
litegate connect http \
  --remote https://connect.example.com \
  --name home \
  --token-file ./home-connect.token \
  --domain audit.home.example.com \
  --upstream http://192.168.50.247:8090
```

Common options:

| Option | Meaning |
| --- | --- |
| `--sessions 2` | Number of persistent tunnels |
| `--max-connections 128` | Maximum concurrent requests per session |
| `--host-header preserve` | Default; preserve the public Host upstream |
| `--host-header upstream` | Use the Host from `--upstream` |
| `--host-header audit.internal` | Use an explicit virtual host |
| `--cert-file` / `--key-file` | Client certificate and key when Cloud requires mTLS |

The CLI also accepts `LITEGATE_CONNECT_REMOTE`, `LITEGATE_CONNECT_NAME`, `LITEGATE_CONNECT_TOKEN_FILE`, and `LITEGATE_CONNECT_TOKEN`. There is deliberately no plaintext token command-line option, preventing exposure in shell history and process listings.

## 4. Verify in the Dashboard

Open **Connect Network** and expand the peer and hostname:

| State | Meaning |
| --- | --- |
| Registration `ready` | Cloud accepted the hostname; also check the peer's online state |
| Cloud TLS `ready` | A certificate is loaded, with coverage, source, challenge, and expiry details |
| Cloud TLS `eligible` | Automatic issuance is authorized and about to start |
| Cloud TLS `issuing` | ACME issuance is in progress |
| Cloud TLS `failed` | Issuance failed; expand the row for the error |
| Cloud TLS `missing` | No certificate and no usable automatic issuance configuration |

Finally verify from outside the LAN:

```bash
curl -v https://audit.home.example.com/healthz
curl -N https://audit.home.example.com/events
```

## Limits and troubleshooting

- CLI HTTP supports ordinary requests, uploads, downloads, long polling, and SSE. It does not support WebSocket/HTTP Upgrade; use a full [LiteGate Connect](connect.md) Site for those protocols.
- The public Host is preserved by default. Use `--host-header upstream` or an explicit value when the origin enforces a Host allowlist.
- Cloud discards client-supplied `Forwarded`, `X-Forwarded-*`, and `X-Real-IP`, then rebuilds forwarding headers from its trusted-proxy result.
- For an HTTP-01 failure, check public ports 80/443, DNS, and the ACME challenge path. For DNS-01, check the selected provider credentials.
- Ordinary CLI downtime does not remove its registration: Cloud retains hostname ownership and renewal authorization. An on-demand certificate loses this Connect authorization only when a later registration explicitly removes/replaces the hostname or Cloud loses its persisted Registry state; registering it again triggers pre-issuance.
- When a peer is offline, Cloud retains hostname ownership and returns 503 instead of falling back to a local wildcard Site.
- A `failed` detail includes the original ACME error and may reveal internal hostnames, provider details, or network information. Restrict the Dashboard and its status endpoint to trusted administrators.
