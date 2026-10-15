# Stream and Forward configuration

## Stream entry and upstreams

Files live under streams_dir and support TCP, UDP and built-in SOCKS5. Dedicated listeners use port (listen defaults to true). Shared 443 uses listen: false, entrypoints: [websecure] and hostnames, without port. Forward-bound internal streams use listen: false without entrypoints/hostnames/Stream TLS. Do not mix the three entry modes.

upstream is a static address (TCP also supports unix:///absolute/path). service_name with upstream_type uses discovery and is mutually exclusive with a static upstream. proxy aliases upstream; see the L4 guide for unified site syntax. idle_timeout defaults to 60 seconds; UDP max_sessions defaults to 10000.

lb_policy supports round_robin (default), ip_hash, weighted/weighted_round_robin, least_conn, p2c and plugins, excluding cookie. Static backends use the selected policy. Mixed discovery lists first select a service by backend weight, then an instance within it. UDP picks a destination once per session. P2C latency measures connection establishment/first response, not application-request duration.

## SOCKS5 and Forward

SOCKS5 requires allowed_destinations and gives denied_destinations precedence. Rules match resolved IPs; public/private/any, IP/CIDR and port ranges constrain destinations. Built-in denial protects loopback, link-local, metadata and unspecified addresses; exceptions require more-specific explicit prefixes. public excludes private/reserved ranges; private includes RFC1918 and IPv6 ULA.

A Forward Site references stream or generates an internal forward:<domain> Stream using target/socks5; these options are mutually exclusive. token_file authorizes tunnels and max_sessions/idle_timeout bound them. Without --target the client provides a transparent tunnel. --target automatically performs SOCKS5 CONNECT and therefore requires a SOCKS5 server Stream.

Clients support version: 1 files through --config. Relative token_file paths resolve against the file directory; explicit CLI flags override corresponding fields. remote/remotes are exclusive, as are mappings and top-level local/target. name/local must be unique; enabled defaults to true. All ports must bind before startup; any failure cleans up the whole set. Non-loopback listeners require allow_lan_listen: true. Multiple mappings are implemented; configuration hot reload is not yet available.

## Forward v3 and failover

transport is auto (default), v3 or v2. v3 opens a long-lived TLS connection per Cloud, authenticates with litegate-forward.v3 Upgrade, carries local connections on HTTP/2 CONNECT and uses PING for liveness. auto can fall back to WebSocket v2 with legacy servers, proxy environments or entries rejecting Upgrade, retrying v3 after ten minutes. Explicit capacity/destination rejection does not trigger protocol fallback.

remotes initially tries in order, then prefers the last successful node. Transport failures or capacity rejection can switch Clouds; SOCKS5 policy/target-connection rejection cannot. Servers revalidate tokens, sites and entrypoints for new streams. Revocation denies new streams while established ones drain. Default v3 session caps are 32 per IP and 256 per Site; exceeding them returns 429.

## TLS, ACLs, tags and observation

TCP TLS uses tls.enabled with paired cert_file/key_file, or auto_cert/domains. Shared entries reuse hostnames and existing covering certificates; min_version is 1.2/1.3. Dedicated listeners cannot take occupied HTTP/HTTPS ports. Shared 443 uses attached streams as above and does not require changing https_port. Native database STARTTLS differs from a raw TLS wrapper; match client protocols.

stream_ip_restriction supplies global ACLs and each Stream can set ip_restriction. Dedicated SOCKS5 has no protocol authentication and binds all interfaces: restrict sources/destinations. UDP/QUIC prepends PROXY v2 headers to datagrams, only the first by default; proxy_protocol_udp_each_packet selects every packet. Backends must recognize/remove them and allow MTU headroom.

Discovery tags explicitly declare TCP/UDP ports listed in service_discovery.tag_entrypoints.allowed_ports without conflicts with entries/static streams. TLS tags match their named group. UDP TLS termination is unsupported and invalid TCP TLS does not downgrade to plaintext. Observe sessions, bytes, rejection and timeouts through Dashboard/metrics.

```yaml
name: mysql-proxy
port: 3307
protocol: tcp
upstream: 192.168.1.100:3306
enabled: true
idle_timeout: 300
```

```yaml
site: forward.example.com
forward:
  token_file: /etc/litegate/secrets/forward.token
  max_sessions: 200
  idle_timeout: 600
  socks5:
    allowed_destinations:
      - 10.0.0.25/32:3306
      - 10.0.0.26/32:6379
```

```yaml
version: 1
remotes:
  - https://forward-primary.example.com
  - https://forward-backup.example.com
token_file: ./forward.token
transport: auto
mappings:
  - name: mysql
    local: 127.0.0.1:13306
    target: 10.0.0.25:3306
  - name: redis
    local: 127.0.0.1:16379
    target: 10.0.0.26:6379
```

```bash
litegate forward --config ./forward.yaml
```

```yaml
name: database
listen: false
entrypoints: [websecure]
hostnames: [db.example.com]
protocol: tcp
upstream: unix:///run/litegate/database.sock
enabled: true
tls:
  enabled: true
  auto_cert: true
  min_version: '1.2'
```

## Related documentation and code

- [L4 reference](l4-guide.md)
- [Entrypoints](entrypoints.md)
- [Shared 443](../09-advanced/shared-443-l4-stream.md)
- [Client implementation](../../../../pkg/litegate/forward_cmd.go)
- [Transport](../../../../internal/forward)
