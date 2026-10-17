# Forward and Connect: Crossing Networks Overview

LiteGate has two "cross-network" features: **Forward** and **Connect**. Both use only public port 443 and both have the inside dial out over TLS, but their direction and purpose are completely different. This page explains how they differ, how to choose and combine them, and where they stand relative to tools such as frp and Cloudflare Tunnel. Field details are in the topic pages linked at the end; only minimal examples are given here.

> [!NOTE]
> **Terminology**: **Forward** here is the point-to-point encrypted tunnel for mapping isolated cloud assets (such as an RDS database) to a local port.
> If you need a standard HTTP forward proxy so ordinary browsers or crawlers can use LiteGate as an egress hop to the internet, see [Forward (asset mapping tunnel) vs Forward Proxy](../../forward-vs-forward-proxy.md).

## 1. The two directions in one picture

```text
Forward: bring "a service in the cloud" to "my computer"
─────────────────────────────────────────────
Navicat ──TCP──▶ litegate forward ══TLS 443══▶ Cloud LiteGate ──TCP──▶ RDS in the cloud VPC
(local port)      (client, dials out)            (Forward Site)

Connect: publish "a service at home" to "the internet"
─────────────────────────────────────────────
Browser ──HTTPS──▶ Cloud LiteGate ◀══TLS 443══ Home LiteGate ──▶ NAS / internal systems at home
                   (forwards by SNI)  (Home dials out and       (TLS terminated at Home, full
                                       carries traffic back)     Site and middleware)
```

| | Forward | Connect |
| --- | --- | --- |
| Who dials out | `litegate forward` on the user's computer | LiteGate at Home |
| Traffic direction | User → Cloud → targets the Cloud can reach | Public visitor → Cloud → Home |
| Who can access | Only clients holding the Forward token | Anyone (subject to the Site's own authentication) |
| Typical targets | Databases, Redis, SSH and other TCP services | Websites, internal systems; TCP Streams can be published too |
| What visitors install | The `litegate` client | Nothing, a browser is enough |

In one sentence: **Forward is "I use things in the cloud"; Connect is "others use things at my home".**

## 2. How to choose

| Your need | Choice | Topic page |
| --- | --- | --- |
| No public IP at home/office; use a VPS to publish a NAS or internal system as public HTTPS | Connect | [Connect configuration and rollout](connect.md) |
| Developers reach cloud RDS/Redis that only has private addresses, from their machines, without a VPN | Forward | [Secure database access](../../database-proxy-solution.md) |
| Colleagues on the road reach non-HTTP services at Home, such as a database or SSH | Forward → Connect combined | Section 3.3 below |
| Publish internal systems of several branch offices through one cloud entry | Connect, one Peer per branch | [Connect configuration and rollout](connect.md) |
| Whole-network interconnection, arbitrary internal IPs, UDP | Neither fits; see section 6 | — |

## 3. Three typical topologies

### 3.1 Forward: reach a cloud-internal database from your machine

On the Cloud, an HTTPS domain is bound to exactly one Stream, and the client **cannot** choose which host to connect to:

```yaml
# Cloud: streams/rds.yaml
name: rds
protocol: tcp
enabled: true
listen: false
upstream: 10.0.0.25:3306
idle_timeout: 600
```

```yaml
# Cloud: sites/forward.example.com.yaml
site: forward.example.com
forward:
  stream: rds
  token_file: /etc/litegate/secrets/rds-forward.token
```

```bash
# Cloud: generate the token (directory 0700, file 0600, never overwrites) and hand it to the user securely
litegate forward token --output /etc/litegate/secrets/rds-forward.token

# User's computer
litegate forward --remote https://forward.example.com --local 127.0.0.1:3306 --token-file ./rds-forward.token
```

Navicat connects to `127.0.0.1:3306`. To let one client reach several targets, replace the Stream with a SOCKS5 Stream with an `allowed_destinations` allow list and write several `mappings` on the client; see [Stream configuration](../03-configuration/stream-config.md).

### 3.2 Connect: publish a website at Home to the internet

Business domains' DNS points to the Cloud. The Cloud declares which domains Home may publish, and Home declares what it publishes:

```yaml
# Cloud: config.yaml
connect:
  server:
    enabled: true
    hostname: connect.example.com
    peers:
      home:
        token_file: /etc/litegate/secrets/home-connect.token
        allowed_domains: ["*.home.example.com"]
        max_connections: 4096
```

```yaml
# Home: config.yaml
connect:
  client:
    enabled: true
    name: home
    remote: https://connect.example.com/_litegate/connect/v1
    token_file: /etc/litegate/secrets/home-connect.token
    publish_sites: true
    exclude_domains: [connect.example.com]
```

Every Site exposed on `websecure` at Home is registered automatically. Certificates live at Home and TLS terminates at Home; the Cloud only forwards by SNI and never sees plaintext.

### 3.3 Forward → Connect: reach the database at Home while away

Home publishes a Stream used only through Forward, and the Cloud exposes it with a Forward Site whose `target.type` is `connect`:

```yaml
# Home: streams/home-mysql.yaml
name: home-mysql
protocol: tcp
enabled: true
listen: false
connect_publish: forward_only     # not reachable by SNI from the internet, only through Forward
hostnames: [mysql.home.example.com]
upstream: 192.168.1.20:3306
```

```yaml
# Cloud: sites/home-db.example.com.yaml
site: home-db.example.com
forward:
  target:
    type: connect
    name: mysql.home.example.com
  token_file: /etc/litegate/secrets/home-db-forward.token
```

```bash
litegate forward --remote https://home-db.example.com --local 127.0.0.1:3306 --token-file ./home-db-forward.token
```

Data path: `Navicat → forward client ═443═▶ Cloud ═Connect═▶ Home → 192.168.1.20:3306`. Home still opens no inbound port. Home needs `connect.client.publish_streams: true`.

## 4. Security model

| Boundary | Mechanism |
| --- | --- |
| Who can build tunnels | Forward: one token per Forward Site; Connect: one token per Peer, optionally with mTLS client certificates. Both compare in constant time; Connect keeps only the SHA-256 digest of tokens in memory |
| Where they can go | Forward targets are fixed by server configuration; the client cannot choose hosts or ports. SOCKS5 mode requires `allowed_destinations`, checked on the resolved IP |
| What can be published | A Connect Peer can register only domains within `allowed_domains`; conflicts with Cloud-local Sites, reserved domains or other Peers are rejected (status `conflict`) |
| When offline | The domain keeps its ownership, its status becomes `offline` and connections are rejected; it never falls back to a Cloud wildcard site |
| Plaintext visibility | Sites published through Connect terminate TLS at Home, and the Cloud only forwards encrypted bytes; Forward's public segment is TLS-encrypted, and native database SSL passes through untouched |
| Token rotation | Connect token files hold one token per line, so old and new can coexist for zero-downtime rotation. Each Forward Site has a single token: after replacement, established connections are unaffected and new connections need the new token on the client; v3 sessions return 403 for new connections after rotation, and the session closes once existing connections finish |

## 5. Transport: Forward v3

The Forward client uses **v3** by default (`transport: auto`):

| | v2 (WebSocket) | v3 (HTTP/2 multiplexing) |
| --- | --- | --- |
| Connection model | One WSS per local connection | One long-lived connection per Cloud; each local connection is a stream on it |
| Cost of a new connection | TCP + TLS + WebSocket handshake (plus SOCKS5 with a target) | One HTTP/2 HEADERS frame (plus a SOCKS5 round trip with a target) |
| Liveness | WebSocket Ping | HTTP/2 PING (probe after 30 seconds idle, 15-second timeout); a local application pausing reads is not mistaken for a dead connection |
| Flow control | Whole connection | Per stream |
| On rejection | The connection is closed | An explicit status code and reason |
| Through proxies | Supported by most L7 proxies/CDNs | The proxy must allow the custom Upgrade |

Connect has always used HTTP/2 multiplexing between Cloud and Home; v3 brings Forward onto the same transport implementation.

**Fallback rules of `auto`**: it switches to v2 in these cases and retries v3 after 10 minutes.

- The server runs an older version without v3;
- Proxy environment variables such as `HTTPS_PROXY` are set;
- An SLB, WAF or CDN in front doesn't let the v3 Upgrade through (returns 400, 403, 502, ...).

Explicit server rejections **don't fall back** and are reported directly: `429` (session limit) and `503` (target unavailable). To pin a protocol use `--transport v2` or `--transport v3`. The server needs no configuration; v2 and v3 are both supported.

**Session limits**: by default at most 32 v3 sessions per client IP and 256 per site. Normally a client keeps one session per Cloud; the limits only stop token holders from piling up idle sessions.

**Known limitations**:

- All v3 streams share one TCP connection, so packet loss slows them together. For long bulk transfers that saturate the link, `--transport v2` gives them their own connection.
- Half-close: the client can close only its sending direction and keep receiving; when the server side finishes sending first, the whole stream ends (same as Connect).
- TCP only; no UDP / QUIC.

## 6. Relation to other tools

Multiplexing and reverse tunnels are not new. LiteGate's difference is that **the tunnel and the gateway are the same program**: traffic coming through the tunnel enters the full Site, certificate, WAF, authentication, rate limiting and access log pipeline directly. Use this table to decide which tool fits, not to rank them.

| Tool | Better for | Main difference from LiteGate |
| --- | --- | --- |
| frp | Mature general-purpose tunneling with UDP, KCP/QUIC and other transports | frp forwards bytes; TLS certificates, WAF and authentication must be built separately. With LiteGate the Home gateway holds certificates and applies Site policy directly, and the Cloud manages domain ownership and conflicts |
| Cloudflare Tunnel | No VPS to maintain; global edge and DDoS protection | Cloudflare terminates TLS at its edge; LiteGate Connect terminates TLS at Home so the Cloud never sees plaintext, and you control the entry VPS |
| SSH port forwarding (`-L` / `-R`) | Temporary, one-off access | SSH clients choose their own targets and need system accounts; Forward targets are bound by the server and tokens are separate from accounts |
| Tailscale / WireGuard | Whole-network connectivity, arbitrary internal IPs, UDP, peer-to-peer | Every device must install a client and join the network; Connect visitors need only a browser, and Forward exposes specific services rather than a whole network |

## 7. Troubleshooting

### Common Forward client errors

| Symptom | Meaning and fix |
| --- | --- |
| Handshake `HTTP 404` | Most often a wrong token: to resist probing, a wrong token, non-HTTPS and a wrong path all return 404. Next, check that the domain really has `forward:` configured and is exposed on the current entrypoint |
| Handshake `HTTP 429` | Over the v3 session limit; check for a client recreating sessions in a loop |
| `HTTP 503 (target unavailable)` | The target Stream doesn't exist or isn't ready; with a connect target, check whether Home is online |
| `HTTP 503 (target has reached max_sessions)` | The target Stream's `max_sessions` is full |
| `HTTP 403` | After the session was established, the token was rotated, the site was deleted, or it's no longer exposed on that entrypoint; the client re-authenticates with a new handshake automatically |
| `server rejected destination` | The SOCKS5 destination isn't in `allowed_destinations`, or the target refused the connection; such errors don't switch to another Cloud |

### The Connect panel on the status dashboard

| Field | Meaning |
| --- | --- |
| ROLE | This node's role: Cloud (accepts Home connections) or Home (dials out) |
| TUNNEL HEALTH | On the Cloud: "online Peers / configured Peers"; on Home: "connected upstream sessions / configured `sessions`". Both when a node is Cloud and Home |
| PUBLISHED HOSTNAMES | Registered domains: `ready`, `pending` (usually Home's certificate isn't ready), `conflict` (conflicts with Cloud-local routes) |
| ACTIVE DATA FLOWS | Current reverse data flows, capped by the Peer's `max_connections` |
| REVISION | `epoch` increases when a new Home instance connects (for example after a Home process restart), not on plain reconnects; `generation` increases when Home's published content changes |

For handling each Connect status see the rollout and monitoring part of [Connect configuration and rollout](connect.md).

## 8. Related docs

- [LiteGate Connect configuration and rollout](connect.md): all Cloud/Home fields, multiple Clouds, mTLS, migration, token rotation
- [Stream configuration](../03-configuration/stream-config.md): Forward Sites, SOCKS5, client `mappings` and `transport`
- [Secure database access](../../database-proxy-solution.md): a step-by-step Forward database tutorial
- [Forward vs HTTP forward proxy](../../forward-vs-forward-proxy.md)
