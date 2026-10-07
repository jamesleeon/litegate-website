# LiteGate Connect Configuration and Rollout

LiteGate Connect publishes Home HTTPS Sites and optional L4 TCP Streams through a TLS tunnel initiated by Home. Home exposes no inbound port; the Connect control hostname and published service hostnames resolve to Cloud.

For protocol and security details, see the [Connect design](https://github.com/jamesleeon/LiteGate/blob/master/docs/zh-cn/litegate-connect-design.md).

## Cloud

```yaml
connect:
  server:
    enabled: true
    hostname: connect.example.com
    path: /_litegate/connect/v1
    state_file: data/connect-registry.json
    reserved_domains:
      - admin.example.com
    peers:
      home:
        token_file: /etc/litegate/secrets/home-connect.token
        allowed_domains:
          - "*.home.example.com"
          - camera.example.com
        max_sites: 200
        max_connections: 4096
        sessions: 2
        max_registrations_per_minute: 30
```

`server.path` may be any absolute URL path. Include the same path in the Home
client's `remote` URL. The endpoint is matched exactly and takes precedence over
normal Site routes.

The control hostname must be an exact public DNS name. `allowed_domains` is an authorization boundary, not a route declaration. The state file contains the last validated ownership snapshot, but no tokens or live sessions. Unusable state entries are skipped at startup and affected Home peers re-register.

Cloud token files accept one token per non-empty line, which permits overlapping credentials during rotation. Keep the file outside source control with restrictive permissions. Generate a secure token using LiteGate:

```bash
sudo litegate connect token --output /etc/litegate/secrets/home-connect.token
```

Or print a secure random key directly to the console:

```bash
litegate -gen-secret
```

## Home

```yaml
connect:
  client:
    enabled: true
    name: home
    remote: https://connect.example.com/_litegate/connect/v1
    token_file: /etc/litegate/secrets/home-connect.token
    publish_sites: true
    publish_streams: false
    sessions: 2
    max_connections: 4096
    registration_debounce: 500ms
    exclude_domains:
      - connect.example.com
      - admin.example.com
```

The token must be at least 32 bytes. Published Sites must use the `websecure` entrypoint and have a usable certificate on Home, because client TLS terminates there. Until the certificate and Home websecure pipeline are ready, Cloud retains ownership as `pending_certificate` and fails closed.

Registered Connect hosts, including pending and offline targets, receive a safe HTTP 308 redirect on Cloud port 80. Unknown Host headers are not redirected.

### Quick HTTP publication from the CLI

See [Publish an HTTP Service with the CLI](connect-cli-http.md) for the complete Cloud, DNS,
certificate, Dashboard, and troubleshooting workflow.

For a small number of HTTP services, Home does not need to run LiteGate `web`, `websecure`, or a
Site configuration:

```bash
litegate connect http \
  --remote https://connect.example.com \
  --name home \
  --token-file /etc/litegate/secrets/home-connect.token \
  --domain audit.home.example.com \
  --upstream http://192.168.50.247:8090
```

Cloud terminates public TLS and forwards individual HTTP requests through Connect. Ordinary
requests, uploads, downloads, long polling, and SSE stream normally. WebSocket and other HTTP
Upgrade requests are not supported in this mode; use a full Connect Site for them. Apart from the
Connect control endpoint and ACME challenges, the published application owns the complete path
space, including `/healthz`, `/readyz`, and `/_litegate/*`.

Cloud must have a certificate covering `--domain`, either an installed exact/wildcard certificate
or automatic issuance with `auto_cert.on_demand.enabled: true`. Connect registration alone does
not enable on-demand TLS. When on-demand TLS is enabled, an authenticated Connect HTTP registration
that satisfies the peer's `allowed_domains` policy authorizes the exact registered hostname for
rate-limited issuance and asynchronously pre-issues a missing certificate after the registration
ACK. HTTP registrations cannot contain wildcard hostnames, unregistered names remain unauthorized,
and an existing exact, SAN, or wildcard certificate prevents duplicate issuance.

The public Host is preserved by default (`--host-header preserve`). Use `--host-header upstream` or an explicit value such as
`--host-header audit.internal` when the origin requires another virtual host. Client-provided
`Forwarded`, `X-Forwarded-*`, and `X-Real-IP` values are discarded and rebuilt from Cloud's
`trusted_proxies` result. Tokens are accepted only through `--token-file` or
`LITEGATE_CONNECT_TOKEN`, never a command-line token value.

## Multiple Cloud nodes and mTLS

Use `remotes` for multiple Cloud nodes and configure at least as many sessions as remotes. For optional mTLS, set `connect.server.client_ca_file` on Cloud and both `connect.client.cert_file` and `connect.client.key_file` on Home. The client certificate DNS or URI SAN must bind the Connect peer name.

## Publishing TCP and SOCKS5 Streams

Enable `publish_streams` on Home and opt in each TCP Stream:

```yaml
name: home-git-ssh
protocol: tcp
enabled: true
listen: false
connect_publish: true
hostnames:
  - git-ssh.home.example.com
upstream: 192.168.1.60:22
idle_timeout: 300
```

Use `connect_publish: forward_only` when a Stream must only be reachable through an authenticated
Forward Site. Direct public SNI routing is then rejected while Forward can still select the Connect
target. SOCKS5 Streams can also be published. The legacy boolean `connect_publish: true` logs a
compatibility notice and is narrowed to `forward_only`; an explicit `connect_publish: public` is
rejected during validation:

```yaml
name: home-socks
protocol: socks5
enabled: true
listen: false
connect_publish: forward_only
hostnames: [access.home.example.com]
idle_timeout: 600
socks5:
  allowed_destinations: ["private:22,80,443,3389"]
```

One Cloud Forward Site can then route every authenticated tunnel to that Connect-published SOCKS5
Stream:

```yaml
domain: forward.example.com
forward:
  target:
    type: connect
    name: access.home.example.com
  token_file: /etc/litegate/secrets/home-forward.token
  max_sessions: 200
  idle_timeout: 600
```

Native QUIC/UDP publication is not implemented.

## Zero-downtime migration

Authorize one exact Cloud Site for one peer:

```yaml
domain: camera.example.com
connect_override: home
routes:
  - name: old-cloud-upstream
    match:
      path_prefix: /
    action:
      type: proxy
      upstream:
        - http://127.0.0.1:8080
```

The local route remains active until `home` registers the same exact hostname. Connect then owns new connections atomically. If Home goes offline, ownership remains fail-closed and never falls back to the old Cloud upstream. Withdraw the Home publication before removing `connect_override` to roll back.

## Rollout and monitoring

1. Enable Cloud first and verify existing port 443 traffic.
2. Enable Home with a test hostname.
3. Verify peer sessions, generation, and domain state in the dashboard.
4. Test WebSocket/SSE for full Sites; test HTTP 308, HTTPS, SSE, uploads, downloads, and network recovery for CLI HTTP publication.
5. Migrate production Sites one at a time with `connect_override`.

Monitor `litegate_connect_sessions`, `litegate_connect_domains`, `litegate_connect_active_connections`, `litegate_connect_connections_total`, `litegate_connect_registrations_total`, `litegate_connect_authentication_total`, and `litegate_sni_connect_dispatch_queue_depth`.
