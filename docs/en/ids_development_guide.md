# LiteGate Identity Service (IDS) Development Specifications

The Identity Service (IDS) acts as one of the core "brains" inside LiteGate. It is responsible for parsing inbound request credentials (e.g., AppIDs, Session Tokens) and dynamically transforming them into gateway-level decision-making metrics. These metrics include security assertions, physical route steering configurations, downstream HTTP header injections, and **dynamic tenant-based QPS rate limiting**.

---

## 1. Core Platform Responsibilities

1. **Credential Parsing**: Resolves inbound client IDs to return corresponding validation secrets and signing algorithms.
2. **Traffic Steering**: Dictates microservice destinations by returning routing selector keys, steering traffic to isolated backend tenant clusters.
3. **Context Injection**: Returns custom HTTP headers dynamically, injecting tenant codes, user identifiers, and ACL metrics into downstream requests.
4. **Dynamic Tenant-Based Rate Limiting**: Yields ratelimit metrics, enabling LiteGate's data plane to execute high-concurrency rate limits per tenant/user to protect downstream databases from cascading surges.

---

## 2. API Contract (OIDC & OpenAPI Modes)

Designed for API token verification and Remote Auth interceptor modes. The gateway queries your central identity provider via the following endpoint:

```http
GET /api/gate/credentials?client_id={ID}&type={TYPE}
```

### 2.1 Security Handshakes
LiteGate appends the following headers to the discovery request. The Identity Service must validate these credentials before returning payloads:
- `X-Gateway-ID`: The gateway identifier.
- `X-Gateway-Secret`: The gateway signing key.
- `Authorization`: `Bearer <token>` (Optional. Injected if a global token is declared in the gateway config).

### 2.2 Expected JSON Response Schema (including the `ratelimit` block)

```json
{
  "auth": {
    "type": "md5",
    "secret": "your-app-secret-here",
    "algorithm": "HmacSHA256",
    "ttl": 300
  },
  "route": {
    "selector": {
      "sid": "scm:prod:c1"
    },
    "meta": {
      "priority": "high"
    }
  },
  "head": {
    "X-Tenant-ID": "T_Company_A",
    "X-User-ID": "U_908821"
  },
  "ratelimit": {
    "qps": "150.0",
    "limit_key": "T_Company_A"
  }
}
```

---

## 3. Redis Contract (IDS-Session Mode)

Under SaaS Session modes, the Identity Service writes user session states **directly into a Redis database** upon login success. The gateway only reads session states from Redis to bypass remote HTTP overheads during active request forwarding.

### 3.1 Session Key Pattern
```text
gate:session:{UUID}
```
*(The prefix is configurable; defaults to `gate:session:`)*

### 3.2 Storage Data Structure
- Redis Structure: **Hash**.

### 3.3 Hash Field Specifications (including `ratelimit` details)

| Hash Field | Value Example | Description |
| :--- | :--- | :--- |
| `tenantId` | `T_Company_A` | Automatically mapped and injected as header `X-Tenant-ID`. |
| `sid` | `scm:prod:c1` | Core steering key used to route traffic to isolated microservices. |
| `ratelimit` | `'{"qps": "150.0", "limit_key": "T_Company_A"}'`| Represents tenant rate limit quotas in JSON format. |
| `X-*` | `X-Custom-Val` | Fields prefixed with `X-` are mapped directly to downstream headers. |
| Flat Fields | `my_claim_val` | Mapped to downstream headers prefixed with `X-Claim-` (e.g., `X-Claim-my_claim_val`). |

#### CLI Redis Injection Example:
```bash
HSET gate:session:uuid-xxx-yyy tenantId "T_Company_A" sid "scm:prod:c1" ratelimit '{"qps": "100.0", "limit_key": "T_Company_A"}'
```

---

## 4. Dynamic Tenant-Based Rate Limiting

LiteGate's built-in `DynamicRateLimitHandler` parses and enforces session limits based on the following logic:

### 4.1 Quote Extractions
The Identity Service is not strictly forced to expose the `qps` parameter key. The gateway tolerates and parses floating-point rate limits by searching these three keys sequentially:
1. `qps` (Recommended)
2. `rate`
3. `limit`

### 4.2 Rate Limiting Key Mapping & Shared Quotas (`limit_key`)
- **Shared Tenant Rate Limiting**: If the Identity Service provides a **`limit_key`** (e.g., mapping it to the tenant ID `T_Company_A`), all active users belonging to the same tenant **share** the same rate limit pool. This is perfect for enforcing global tenant-wide throughput limits.
- **Isolated User / IP Limits**: If `limit_key` is omitted, the gateway executes a graceful fallback strategy:
  - Checks if `tenantId` is active ➡️
  - Checks if `userId` is active ➡️
  - Checks if `app` identifier is active ➡️
  - Falls back to the client's physical IP address.
- **Route Namespace Isolation**: During physical counting, LiteGate appends site and route prefixes to the limit key (`siteName:routeName:dyn:limitKey`). This ensures that tenant limits are partitioned across separate routes and domains without interference.

---

## 5. Implementation Guidance for Identity Providers

### 5.1 Dynamic Attribute Injections
Avoid hardcoding downstream headers inside the gateway or your identity provider codes. Always leverage the `head` payload block (or Redis session fields) to return permissions dynamically. The gateway maps and projects these properties automatically.

### 5.2 Throughput & Latency Protections
The latency of your authorization API directly impacts the first-packet latency of the gateway.
- Cache active tenant metadata and AppID secrets within the identity service.
- If an AppID does not exist, return an explicit HTTP `404 Not Found`. When LiteGate captures a `404` error, it automatically applies **"Negative Caching"** (cached for 60 seconds by default) to protect your authentication services from invalid AppID DDoS flood attacks.
