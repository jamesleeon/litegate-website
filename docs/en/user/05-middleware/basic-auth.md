# Basic Auth (HTTP Basic Authentication Middleware)

`basic_auth` is a named middleware that protects routes with standard HTTP Basic authentication (`WWW-Authenticate: Basic`). It suits internal tools, staging environments and simple admin pages — places where you don't want OIDC/SSO but must keep anonymous visitors out.

> **The one thing to know**: `users` must contain **bcrypt hashes** (as produced by `htpasswd -B`), **never plaintext passwords**. Plaintext fails at load time.

---

## 1. Quick start

Step 1: generate a **bcrypt** password hash with LiteGate's built-in command (no extra tools needed):

```bash
./litegate -hash 'S3cret!'
# The hash field in the log output is the result, e.g.:
#   hash=$2a$10$Q9Q0k8m....  (a 60-character bcrypt hash)
```

Step 2: put `username:hash` into a named middleware and reference it from a route:

```yaml
site: internal.example.com

middlewares:
  admin-gate:
    type: basic_auth
    config:
      users: 'admin:$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy'   # username:bcrypt hash; use your own
      realm: "Internal Tools"

/:
  use: [admin-gate]
  proxy: 127.0.0.1:8080
```

Without credentials, or with wrong ones, the gateway returns **`401 Unauthorized`** with `WWW-Authenticate: Basic realm="Internal Tools"`, and the browser shows a login prompt.

---

## 2. Fields

| Field | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `users` | string | Yes | — | Comma-separated `username:bcrypt_hash` entries. Hashes must be valid bcrypt (starting with `$2a$`/`$2b$`/`$2y$`, 60 characters). |
| `realm` | string | No | `LiteGate Restricted` | Realm shown in the browser's login prompt. Must not contain double quotes or control characters. |
| `remove_header` | bool | No | `false` | Remove the `Authorization` header after successful authentication so Basic credentials don't reach the upstream. |
| `enabled` | bool | No | `true` | When `false`, the definition is excluded from the runtime pipeline and from composition conflict checks. |

Separate multiple users with commas:

```yaml
config:
  users: "admin:$2y$05$AAAA....,ops:$2y$05$BBBB....."
```

---

## 3. Ways to generate bcrypt hashes

| Tool | Command | Notes |
| :--- | :--- | :--- |
| **LiteGate built-in (recommended)** | `./litegate -hash 'password'` | Prints a bcrypt hash directly, no extra tools |
| Apache htpasswd | `htpasswd -nbB user 'password'` | Prints `user:hash`; take the part after the colon |
| Python | `python -c "import bcrypt;print(bcrypt.hashpw(b'password', bcrypt.gensalt()).decode())"` | Needs `pip install bcrypt` |

> Only **bcrypt** is supported. MD5 (`$apr1$`), SHA (`{SHA}`) and plaintext are rejected at load time with `password must be a valid bcrypt hash`.

---

## 4. Versus inline `auth: {type: basic}`

LiteGate has two "basic authentication" paths; don't mix them up:

| Aspect | Named `basic_auth` middleware (this page) | Inline `auth: { type: basic }` |
| :--- | :--- | :--- |
| Purpose | Generic, reusable cross-cutting middleware referenced by many routes | Static authentication bound to a single route's action |
| Reuse | Define once, reference from many routes with `use: [name]` | Each route writes its own |
| Phase | Authentication phase, compiled into the PipelinePlan | Inline on the route, also run in the Authentication phase |
| Best for | Sharing one set of accounts across routes; seeing the pipeline in the Dashboard | One-off protection of a single route |

**Recommendation**: use named `basic_auth` when several routes share it or you want its position visible in the PipelinePlan; for a one-off single route, inline `auth` is simpler. Don't stack both on the same route.

---

## 5. Placement and security notes

- **Phase**: `basic_auth` runs in the **Authentication** phase — after CORS preflight, request rewriting and WAF, before the proxy action. CORS preflights (`OPTIONS`) are not blocked by it.
- **Single instance**: `basic_auth` has `AllowMultiple = false`; a route may have only one active basic authentication definition, and duplicates fail at load time.
- **Forged header cleanup**: client-forged internal identity headers are stripped before authentication (same as `jwt_auth` / `api_key`).
- **Username enumeration resistance**: for unknown users the gateway still runs one bcrypt comparison against a fixed dummy hash, so "no such user" and "wrong password" take the same time.
- **Always use HTTPS**: Basic credentials are Base64-encoded, not encrypted; over plaintext they are exposed. In production enable it only on TLS entrypoints.

---

## 6. FAQ

**Q: Every request gets 401 although the username and password are right.**
Plaintext passwords are rejected at load time, so check the hash itself: it should start with `$2a$`/`$2b$`/`$2y$`, be 60 characters, and be generated from the current password. Hashes copied from elsewhere are often truncated or carry stray spaces.

**Q: Can the backend get the username?**
Requests continue to the upstream after authentication, but this middleware doesn't inject a username header. To pass identity upstream use `inject_claims` of `jwt_auth`, or parse it in the backend. If you don't want Basic credentials to reach the backend, set `remove_header: true`.

**Q: Can `realm` contain non-ASCII text?**
Yes, but no double quotes `"` or control characters, or loading fails.

---

## Further reading

- [Authentication overview](./authentication.md)
- [Middleware pipeline and chain](./pipeline.md)
- [OIDC single sign-on](./oidc.md)
