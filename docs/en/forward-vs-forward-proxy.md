# Two "Forwards" in LiteGate: `Forward` (Asset Mapping Tunnel) vs `Forward Proxy`

LiteGate has two network features with "Forward" in the name:
1. **`Forward`** (built-in / `site.forward` / the `litegate forward` CLI)
2. **`Forward Proxy`** (an entry plugin / `pkg/plugins/forwardproxy`)

They are easy to confuse at first, and some assume they are two names for one feature. **They are independent mechanisms with completely different use cases, topologies, client requirements and security models.**

This page compares them so you can choose correctly.

---

## 1. Positioning and direction in one picture

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ Case 1: LiteGate Forward (private asset mapping tunnel)                               │
│ Purpose: "I securely use isolated private assets in the cloud/intranet"               │
│          (cloud RDS, Redis, internal RPC)                                              │
│                                                                                        │
│ Local tool (Navicat) ──TCP──▶ litegate forward CLI ══TLS 443 (token)══▶ Cloud LiteGate │
│ (127.0.0.1:3306)              (dedicated client, dials out)    │ (bound to one Stream) │
│                                                                ▼                       │
│                                                         RDS MySQL 3306 in the VPC      │
└────────────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────────────┐
│ Case 2: Forward Proxy (generic HTTP/HTTPS forward proxy plugin)                        │
│ Purpose: "I use LiteGate as an egress hop to the internet or any authorized site"      │
│                                                                                        │
│ Any client (browser/curl) ──HTTP CONNECT (bcrypt)──▶ LiteGate ──TCP/TLS──▶ Internet API│
│ (no LiteGate install, just set a proxy)              (Ingress plugin)  (github.com, ...)│
└────────────────────────────────────────────────────────────────────────────────────────┘
```

- **`Forward`** is a **point-to-point private tunnel**: the client must run the `litegate forward` CLI, and **the target is locked by the server to a specific private Stream** (for example only one internal database; the client has no way to request any other address).
- **`Forward Proxy`** is a **point-to-any egress hop**: the client is an ordinary browser, curl or crawler using standard HTTP `CONNECT`, **the client chooses the target** (`github.com`, `api.openai.com`, ...), and a server-side ACL allow list controls what is reachable.

---

## 2. Comparison matrix

| Aspect | LiteGate Forward (asset mapping tunnel) | Forward Proxy (generic forward proxy plugin) |
| :--- | :--- | :--- |
| **Purpose** | **Bastion for private internal assets**<br>Maps databases/TCP services in isolated cloud environments to local ports securely | **Egress proxy and network hop**<br>Lets LAN clients or crawlers use LiteGate as the exit to the internet or third-party services |
| **Client requirement** | ⚠️ **Must run the `litegate` client**<br>`litegate forward` listens on a local port | ✅ **Nothing to install**<br>Any standard browser, curl or framework, just set `HTTP_PROXY` |
| **Target control** | 🔒 **Bound by the server (strict)**<br>Server configuration binds a specific Stream (such as `10.0.0.25:3306`); the client has no destination parameter at all, so it can't be used as a pivot | 🌐 **Declared by the client (ACL-protected)**<br>The client names the target (`CONNECT target.com:443`), filtered by the server's `allowed_destinations` allow list |
| **Protocol layer** | **L4 over L7 private long-lived connection**<br>After an HTTPS handshake on public 443, upgrades to a dedicated binary channel with keepalives in both directions | **Standard L7 HTTP proxy protocol**<br>Handles HTTP/1.1, HTTP/2 and HTTP/3 `CONNECT` tunnels and absolute-URL requests |
| **Authentication** | 🔑 **Pre-shared token file**<br>A dedicated file generated offline with `litegate forward token` (mode 0600); no token, no tunnel | 👤 **Standard HTTP Basic**<br>Credentials in `Proxy-Authorization`, verified on the server with timing-safe bcrypt |
| **Where it is configured** | `forward:` in `sites/*.yaml` + `streams/*.yaml` | The global `ingress_plugins` array in `config.yaml` |
| **Anti-probing** | Invalid requests or handshakes without a token are cut off or get 404 / a disguised response | `probe_resistance: true`: unauthenticated requests **never get 407** (so it doesn't reveal itself as a proxy) and fall through to the ordinary website |
| **ECH** | ❌ **Not applicable** (the client is a dedicated CLI) | ❌ **Not recommended** (most proxy clients don't support ECH, so connections may fail) |

---

## 3. Scenarios and configuration

### Case 1: developers reaching a cloud-internal database securely (use `Forward`)

#### Why it must be `Forward`
Enterprise cloud RDS databases (MySQL/PostgreSQL/Redis) usually live only in the VPC, and exposing 3306 publicly is forbidden.
- Traditional SSH tunnels need a Linux account on a cloud server for each person — too much privilege.
- With a generic forward proxy, a leaked password lets an attacker use the proxy as a pivot to scan the whole VPC.
- **LiteGate `Forward` solves this**: the tunnel's **target is fixed**, so even a client holding the token **can only reach that one database** and nothing else on the internal network.

#### Configuration

**1. Server**
```yaml
# streams/rds-mysql.yaml
name: rds-mysql
protocol: tcp
enabled: true
listen: false                  # no public port; referenced only by Forward
upstream: 10.0.0.25:3306       # private RDS address in the VPC
idle_timeout: 600
```

```yaml
# sites/db-tunnel.example.com.yaml
site: db-tunnel.example.com
forward:
  stream: rds-mysql            # target locked; the client can't change it
  token_file: /etc/litegate/secrets/rds.token
```

```bash
# Generate the token on the server and distribute it securely
litegate forward token --output /etc/litegate/secrets/rds.token
```

**2. Client**
Developers run locally:
```bash
litegate forward \
  --remote https://db-tunnel.example.com \
  --local 127.0.0.1:3306 \
  --token-file ./rds.token
```
Local database tools (Navicat / DBeaver) connect to `127.0.0.1:3306`, as if the database ran on the same machine.

---

### Case 2: unified egress for internal servers/crawlers without public IPs (use `Forward Proxy`)

#### Why it must be `Forward Proxy`
In private data centers or isolated financial zones, many servers have no public IP but need to:
- call WeChat Pay / Alipay public APIs;
- reach public SaaS (GitHub, SMS providers, AI model APIs);
- crawl many public websites on a schedule.

The targets are **thousands of varying domains**; you can't write thousands of `stream.yaml` fixed port mappings. What you need is a **standard HTTP/HTTPS egress proxy**.

#### Configuration

On the edge LiteGate host, `config.yaml`:

```yaml
# config.yaml
entrypoints:
  websecure:
    address: ":443"

ingress_plugins:
  - name: my-forward-proxy
    type: forward_proxy            # enable the forward proxy plugin
    entrypoints: [websecure]       # attach to 443
    config:
      hosts: [proxy.example.com]   # only for this SNI
      username: crawler_ops
      password_env: LITEGATE_PROXY_PASSWORD # proxy password from an environment variable
      probe_resistance: true       # anti-probing
      allowed_ports: [80, 443]     # web traffic only
      allowed_destinations:        # destination allow list
        - "*.github.com"
        - "*.wechat.com"
        - "api.openai.com"
```

#### Client
Internal machines install nothing; use the standard environment variable:
```bash
export https_proxy="https://crawler_ops:YourPassword@proxy.example.com:443"

# curl or Python crawlers reach the internet through the proxy
curl https://api.github.com/zen
```

---

## 4. Common misconceptions

### Misconception 1: can `Forward Proxy` replace `Forward` for database access?
**Technically yes (via HTTP CONNECT 443), but it is a dangerous security architecture.**
- If clients may freely connect back to internal 3306 through the forward proxy, anyone with a proxy account can target `10.0.0.1:22` or `10.0.0.2:80` and turn your proxy into an internal pivot.
- `Forward` statically binds the domain to a target Stream in the data model (least privilege, zero trust).

### Misconception 2: can `Forward` replace `Forward Proxy` for browsing?
**Not practically.**
- `Forward` is designed for infrastructure asset mapping. To browse with it you would need a SOCKS5 Stream with client `mappings`, and the client would have to keep `litegate forward` running. For ordinary browsers and ad-hoc scripts, setting `HTTP_PROXY` is far more natural.

### Misconception 3: how does Connect relate to Forward?
- **Forward**: reach inside from outside (the client connects to the cloud and brings cloud-private assets to the local computer).
- **Connect**: publish from inside to outside (an internal machine without a public IP connects out to the cloud and publishes its internal sites for everyone).
- *See [Forward and Connect overview](user/09-advanced/forward-and-connect.md)*.

---

## 5. Decision flow

```text
You need network connectivity
      │
      ▼
Is the target a fixed private asset (cloud RDS, Redis, internal admin)
or arbitrary internet sites (public APIs, crawl targets, browsing)?
      │
      ├─► [fixed private asset] ──► Can the client run a command-line tool?
      │                               │
      │                               ├─► [yes] ──► 🌟 LiteGate Forward
      │                               │            (strong token auth, Stream locked)
      │                               │
      │                               └─► [no] ──► consider LiteGate Connect
      │                                            (publish the internal asset as an authenticated website)
      │
      └─► [dynamic / many public targets] ──► 🌟 Forward Proxy (forward proxy plugin)
                                              (standard HTTP CONNECT, nothing to install, ACL + anti-probing)
```

## Related docs

- [Stream configuration reference](user/03-configuration/stream-config.md)
- [Ingress entry plugins](ingress-plugin-guide.md)
- [forward_proxy example](../../examples/plugins/ingress/forwardproxy/README.md)
