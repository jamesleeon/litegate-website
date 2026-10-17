# Secure Database Access with LiteGate

Database protocols such as MySQL and PostgreSQL usually cannot share port 443 with HTTPS through SNI. MySQL, for example, has the client wait for the server's handshake packet and only then possibly upgrade with SSLRequest; the first packet of the connection is not a TLS ClientHello with SNI. Configuring `db.example.com:443` directly as an SNI Stream therefore fails with almost every database client.

LiteGate offers two complementary modes:

- Fixed trusted source IPs: an L4 Stream on a dedicated port with an IP allow list.
- Only 443 can be opened, or source IPs vary: `litegate forward`, carrying the raw database byte stream inside HTTPS (Forward v3 HTTP/2 streams by default, falling back to WSS when needed).

## Forward data path

```text
Navicat / DBeaver
        │  MySQL (plaintext by default; MySQL's own SSL can be enabled)
        ▼
Local or LAN address:3306
        │
litegate forward client
        │  TLS 1.2+, reusing LiteGate's 443 and existing certificates
        ▼
LiteGate Forward endpoint
        │  Plain TCP by default, or a Unix socket
        ▼
Internal MySQL / RDS
```

The public segment is always TLS-encrypted. From LiteGate to the internal database the default is plain TCP, so MySQL needs no certificate configuration — the easiest way to roll out internally. If MySQL SSL is enabled in Navicat, MySQL's SSLRequest and encrypted data pass through the Forward tunnel untouched; LiteGate neither terminates nor parses database TLS.

> A Forward Stream cannot enable `tls.enabled` at the same time. Stream TLS requires the connection to start with raw TLS, which is incompatible with MySQL/PostgreSQL's in-protocol TLS upgrade.

## Server configuration

Forward is a site feature; `config.yaml` doesn't change. Create a site file for the domain; the domain must be covered by an existing `websecure` certificate. For example, with an existing `*.example.com` wildcard certificate you can use `forward.example.com` directly, and no extra certificate is requested for Forward.

```yaml
# sites/forward.example.com.yaml
site: forward.example.com
forward:
  stream: rds-mysql
  token_file: /etc/litegate/secrets/forward.token
```

`entrypoints` isn't needed here. Without a global `entrypoints` section, LiteGate still provides `websecure` from `http.https_port` (default 443), and Forward only accepts TLS. Add `entrypoints: [websecure]` only when several entrypoints are deployed and you need to limit exposure.

The token must be at least 32 bytes. Let LiteGate generate it and save it with safe permissions:

```bash
sudo litegate forward token --output /etc/litegate/secrets/forward.token
```

Then create a Stream used only by Forward:

```yaml
# streams/rds-mysql-forward.yaml
name: rds-mysql
listen: false
protocol: tcp
upstream: 172.16.0.25:3306
enabled: true

max_sessions: 100
idle_timeout: 7200
ip_restriction:
  allow_ips:
    - 203.0.113.0/24
```

`upstream` can also be `unix:///run/mysqld/mysqld.sock`, or use `service_name` with service discovery. Forward enters the full Stream data path, so load balancing, service discovery, IP restrictions, session limits, timeouts and metrics all still apply. `forward.example.com.yaml` binds the domain to `rds-mysql` exclusively; clients cannot choose another Stream or pass an arbitrary target.

## Client usage

Copy the server's token securely to the machine running the client, then run:

```bash
litegate forward \
  --remote https://forward.example.com \
  --local 127.0.0.1:3306 \
  --token-file ./forward.token
```

In Navicat:

```text
Host: 127.0.0.1
Port: 3306
Username/password: the database's existing credentials
```

The token can also come from an environment variable, keeping the secret off the command line and out of the process list:

```bash
export LITEGATE_FORWARD_TOKEN='a random value of at least 32 bytes'
litegate forward --remote https://forward.example.com --local 127.0.0.1:3306
```

### A LAN entry on an always-on VM

The default address is loopback. To let Navicat on other LAN computers connect through an always-on VM, give the VM's LAN IP explicitly:

```bash
litegate forward \
  --remote https://forward.example.com \
  --local 192.168.50.20:3306 \
  --token-file ./forward.token
```

Navicat then connects to `192.168.50.20:3306`. LiteGate prints a LAN exposure warning; restrict 3306 to trusted LAN ranges with the VM's firewall. Don't use `0.0.0.0:3306` unless you really need all interfaces and have a firewall in place.

## TLS boundaries

| Segment | Default | Optional hardening |
| :--- | :--- | :--- |
| Forward client → LiteGate 443 | TLS 1.2+ enforced | Trusted CA, token rotation |
| LiteGate → internal MySQL | Plain TCP | Enable MySQL SSL in Navicat, passed through end to end |
| LiteGate → Unix socket | Local Unix byte stream | Control with socket group and `0660` permissions |

Forward doesn't accept `http://` or `ws://` and offers no client option to skip certificate verification. Public transport never degrades to plaintext.

Forward v3 checks session liveness with HTTP/2 PING (probe after 30 seconds idle, 15-second timeout). PINGs are answered by the protocol stack, so a healthy connection isn't misjudged as dead when the local application pauses reading. When falling back to v2, a WebSocket Ping is sent every 20 seconds so idle tunnels aren't silently reclaimed by load balancers, CDNs or NAT. When the upstream closes, the tunnel ends immediately rather than waiting for `idle_timeout` before informing the local database client. `idle_timeout` still controls the idle limit of database traffic; when connection pools keep connections long-term, raise it in line with the database's `wait_timeout`.

Both the CLI client and the LiteGate server send heartbeats, so connections stay alive even with no SQL traffic in either direction for a long time. Heartbeats only prevent idle timeouts; if a cloud load balancer enforces an absolute maximum connection lifetime, connections still close when it expires — raise that limit on the SLB/CDN or make sure database clients reconnect.

### Token file rotation

`token_file` is read when the Site loads and kept in a non-serializable runtime field. Replacing the external secret file alone doesn't trigger the `sites/` watcher. After rotating, trigger a reload of that Site, for example:

```bash
sudo litegate forward token --output /etc/litegate/secrets/forward.token.new
mv /etc/litegate/secrets/forward.token.new /etc/litegate/secrets/forward.token
touch /etc/litegate/sites/forward.example.com.yaml
```

Replace the token atomically first, then trigger the Site reload. If the new token file is unreadable, empty or shorter than 32 bytes, the new configuration is rejected; never overwrite the in-use file with an incomplete secret. Clients must switch to the new token; established tunnels are not forcibly closed by rotation. v2 checks the token only when a tunnel is created; v3 rechecks it on every new connection, so new connections on an old session get 403 and the client re-handshakes with the current token.

### Front proxies and the real client IP

Forward writes the real client IP resolved by the router into the tunnel connection's `RemoteAddr()`, so the Stream's `ip_restriction` keeps applying to public clients. With an SLB, WAF or CDN in front, trust only the actual proxy nodes:

```yaml
real_ip:
  trusted_proxies:
    - 10.0.1.10/32       # internal SLB address
    - 10.0.2.0/24        # controlled proxy node range
```

Never set `trusted_proxies` to `0.0.0.0/0`. LiteGate should accept `X-Forwarded-For` only from trusted connectors; otherwise external callers can forge the client IP. When misconfigured, the Stream ACL usually sees the SLB/CDN node address and safely rejects the request — but legitimate users can't connect either.

## When to still use a dedicated Stream

When the office egress IP is fixed and a dedicated port may be opened, a direct L4 Stream is simpler and has the lowest overhead:

```yaml
name: mysql-office
port: 13306
protocol: tcp
upstream: 172.16.0.25:3306
enabled: true
ip_restriction:
  allow_ips: ["203.0.113.10/32"]
```

Don't point ordinary MySQL connections at an SNI Stream on shared 443. The raw TLS/SNI mode on shared 443 suits protocols whose first packet is a ClientHello, such as `rediss://`, gRPC, or TCP services with direct TLS; for general database tool access prefer Forward.

## Current security boundaries

- Forward uses one static token per Forward Site, suitable for small teams and controlled operations environments. When you need per-person identity, short-lived credentials and detailed auditing, integrate an identity provider in a later version or use a dedicated bastion host.
- The default v3 opens a separate stream per local database connection over one long-lived TLS connection (v2 uses one WSS tunnel per connection); if a single connection drops, the database session isn't restored automatically and the database client reconnects.
- `ip_restriction` acts on the real client IP resolved by LiteGate; with a front load balancer configure `real_ip.trusted_proxies` correctly.

## Related docs

- [Stream configuration reference](user/03-configuration/stream-config.md)
- [Forward and Connect overview](user/09-advanced/forward-and-connect.md)
- [Connect configuration and rollout](user/09-advanced/connect.md)
