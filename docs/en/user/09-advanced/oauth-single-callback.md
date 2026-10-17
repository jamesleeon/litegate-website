# Single Callback URL Routing (One OAuth Callback, Several Backends)

Many third-party open platforms (Taobao, WeChat, DingTalk, WeCom, e-commerce and payment platforms) **allow only one OAuth callback URL** per application. In practice the callback often has to go to different handlers, for example:

- **main account authorization** and **sub-account authorization** handled by different backend services;
- several tenants or business lines sharing one platform application, each needing its own handler after the callback.

The platform gives you one callback URL; how do you split it again at the gateway? This page shows LiteGate's standard approach.

---

## 1. Core idea: split on `state`, switch upstreams by matching rather than rewriting

You send a `state` parameter when starting OAuth, and the platform returns it unchanged. **`state` is the natural routing key** — give each kind of authorization its own prefix when starting:

| Authorization type | state when starting | Callback URL (the only one the platform accepts) |
| --- | --- | --- |
| Main account | `main.<nonce>` | `https://cb.example.com/callback?...&state=main.abc` |
| Sub-account | `sub.<nonce>`  | `https://cb.example.com/callback?...&state=sub.xyz`  |

LiteGate uses the [`QueryPrefix`](../03-configuration/site-config.md#9-rule-expression-dsl-reference) rule to match different routes by the `state` prefix, and **each route decides its own upstream and path**.

> **The key difference from Nginx**
>
> A common Nginx pattern:
> ```nginx
> location = /callback {
>     if ($arg_state ~ ^sub\.) { rewrite ^/callback$ /sub_callback last; }
>     proxy_pass http://main_backend;
> }
> ```
> Here `rewrite ... last` **isn't really meant to change the path; it re-matches locations after the rewrite in order to switch upstreams** — because Nginx's `if` can't change `proxy_pass` within one location. Changing the path is a side effect, and the backend is forced to expose an extra `/sub_callback`.
>
> LiteGate works the other way round: **switching upstreams is the result of the matching rule itself**, and changing the path is an optional, separate step. In most cases below you don't need `rewrite` at all.

---

## 2. Option A: one service, different paths (recommended, simplest)

If you are willing to put the main and sub-account handlers in **the same backend service**, listening on different paths (say `/oauth/main/callback` and `/oauth/sub/callback`), the gateway only rewrites the path by `state` prefix and the upstream stays the same:

```yaml
site: cb.example.com
routes:
  # Sub-account: state starts with sub. → rewrite to the backend's sub-account path
  - name: oauth-callback-sub
    priority: 200
    match:
      rule: 'Path("/callback") && QueryPrefix("state", "sub.")'
    proxy: ["127.0.0.1:8080"]
    rewrite:
      path:
        pattern: "^/callback$"
        target: "/oauth/sub/callback"

  # Main account (and every other callback) → rewrite to the backend's main-account path
  - name: oauth-callback-main
    priority: 100
    match:
      rule: 'Path("/callback")'
    proxy: ["127.0.0.1:8080"]
    rewrite:
      path:
        pattern: "^/callback$"
        target: "/oauth/main/callback"
```

`GET /callback?code=...&state=sub.xyz` is rewritten to `/oauth/sub/callback?code=...&state=sub.xyz` and sent to the backend; everything else falls through to the main-account path. The query (including `code` and `state`) is kept unchanged.

**When to use it**: one backend service in one repository, where you just want separate functions per type. Least change, simplest operations.

---

## 3. Option B: two services, switch upstreams

If main and sub accounts are **two independently deployed services** (different processes or machines), let the matching rule pick different upstreams. Whether you still need `rewrite` **depends on which path the target backend registers**:

### B-1: the backend already serves `/callback` — no rewrite needed

```yaml
site: cb.example.com
routes:
  - name: oauth-callback-sub
    priority: 200
    match:
      rule: 'Path("/callback") && QueryPrefix("state", "sub.")'
    proxy: ["10.0.0.2:9091"]   # sub-account service, handles /callback itself

  - name: oauth-callback-main
    priority: 100
    match:
      rule: 'Path("/callback")'
    proxy: ["10.0.0.1:9091"]   # main-account service, handles /callback itself
```

The matching rule already sends the request to the right service, and both services receive on `/callback`, so **no path rewrite is needed**.

### B-2: the backend only serves `/sub_callback` — rewrite required

If the sub-account service only listens on `/sub_callback` and doesn't know `/callback`, a direct forward gets 404, so rewrite the path into the form the backend knows:

```yaml
site: cb.example.com
routes:
  - name: oauth-callback-sub
    priority: 200
    match:
      rule: 'Path("/callback") && QueryPrefix("state", "sub.")'
    proxy: ["10.0.0.2:9091"]
    rewrite:
      path:
        pattern: "^/callback$"
        target: "/sub_callback"      # the path the backend registers

  - name: oauth-callback-main
    priority: 100
    match:
      rule: 'Path("/callback")'
    proxy: ["10.0.0.1:9091"]
```

**The rule in one sentence**: whether you need `rewrite` depends only on whether "the incoming path" equals "the path the backend listens on" — **not on whether you switch upstreams**.

---

## 4. Three things to get right

### ① Make the order explicit with `priority` when several routes share a path

Routes in a site are tried in a fixed order: higher explicit `priority` first; at equal priority, exact paths (`path:`) come before rule routes with extra conditions. Therefore:

- The configuration above gives the sub-account rule `priority: 200` and the main account `priority: 100`, so the sub-account rule is tried first, and the main account can be written as either `rule: 'Path("/callback")'` or `path: "/callback"`;
- **if neither route has a `priority`**, the main account's `path: "/callback"` matches first and `state=sub.` callbacks also go to the main-account backend.

**Rule**: when the same path is split by query/header conditions, give the more specific route an explicitly higher `priority`. For the routing order see [Named matchers and priority](../cookbook/06-matchers.md#3-which-route-matches-first-priority-rules).

### ② `state` must be single-valued, and the prefix is not a security check

- Query parameters used for matching must have **exactly one value**. Duplicates such as `state=sub.x&state=main.x` **match none** of the routes above, so the gateway and backend can't read different values of `state` (query smuggling).
- **The prefix only routes; it cannot replace the backend's `state` validation.** `state` must still be random, single-use, short-lived and bound to the session that started the authorization. Prefer `sub.<nonce>.<signature>`, or store a `state → authorization type` mapping on the server and derive the prefix from it.

### ③ `rewrite` doesn't trigger route matching again

LiteGate's `rewrite` only changes the path **within the current route** and **doesn't** return to the routing table like Nginx `rewrite ... last`. That is what keeps it simple and predictable: a route goes straight from match to upstream with no second hop.

---

## 5. Complete example

One platform application and one callback URL, supporting both main and sub accounts, plus the authorization entry and portal static assets:

```yaml
site: cb.example.com
defaults:
  timeout: 600
routes:
  # Authorization entry (starts OAuth; business code decides the state=main./sub. prefix)
  - name: authorize
    priority: 100
    match:
      path: "/authorize"
    proxy: ["10.0.0.1:9091"]

  # Sub-account callback
  - name: oauth-callback-sub
    priority: 200
    match:
      rule: 'Path("/callback") && QueryPrefix("state", "sub.")'
    proxy: ["10.0.0.2:9091"]

  # Main account and other callbacks
  - name: oauth-callback-main
    priority: 100
    match:
      rule: 'Path("/callback")'
    proxy: ["10.0.0.1:9091"]

  # Authorization portal static assets
  - name: oauth-portal
    priority: 50
    match:
      path_prefix: "/portal/"
    proxy: ["10.0.0.2:9091"]
    strip_prefix: "/portal"
```

---

## 6. Verification and troubleshooting

Send a callback with the sub-account prefix and check it reaches the sub-account upstream:

```bash
curl -i "https://cb.example.com/callback?code=test&state=sub.abc123"
```

- **Wrong upstream (sub-account callbacks reach the main account)**: usually point ① — the sub-account rule doesn't have a higher `priority` than the main account. Give the sub-account route `priority: 200`.
- **404**: the backend doesn't register the forwarded/rewritten path. Either serve that path in the backend, or rewrite it to a path the backend knows as in option B-2.
- **Matched the main account when you expected the sub-account**: check whether `state` was sent with several values (`&state=` twice) — multi-valued parameters don't match — and whether the prefix really is `sub.` (case-sensitive).
- To confirm which route a request will hit, use LiteGate's route lookup (MCP `lookup_route`) or enable access log `routing_detail`.

---

## Related docs

- [Proxy and `rewrite` parameters](../04-actions/proxy.md#8-url-rewrite-rewrite)
- [Rule expression DSL (`Path` / `QueryPrefix`, ...)](../03-configuration/site-config.md#9-rule-expression-dsl-reference)
- [Routing priority](../02-concepts/routing-priority.md)
- [Fall back to a front controller for clean URLs (WordPress/Laravel/SPA) with `try_files`](../04-actions/serve.md)
