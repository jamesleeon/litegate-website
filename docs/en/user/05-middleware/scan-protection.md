# Scan Protection (Governance Rule Engine)

`scan_protection` is LiteGate's built-in **white-box traffic risk detection and automatic response** module. It reuses decisions the gateway makes anyway (does the Host match a site, is the request a 404, user-agent features, path features, ...), aggregates these signals into a **risk profile per source IP**, and when risk accumulates past thresholds it automatically applies **rate limiting / tarpit (delay) / temporary bans**.

This page covers **every configuration option** of `scan_protection`, including the **governance rule engine** (`global_rules` / `site_policies` / `tech_profiles`).

> It is **not** a WAF, nor DDoS/CC protection. It is **opportunistic mitigation with per-process in-memory state, keyed by source IP**. Distributed scanning, traffic through CDNs and forged sources can get around it. Risk state and bans are kept independently in each process and not shared across replicas (there is currently no Redis-backed shared ban list). Responses rely on the real client IP resolved through `real_ip.trusted_proxies`; configure trusted proxies correctly, or bans may land on the wrong IP.

---

## 1. Quick start

The module is **off by default**. Add a top-level `scan_protection` section to enable it:

```yaml
scan_protection:
  enabled: true                  # master switch
  block_duration: "1h"           # long ban duration
  max_404_attempts: 5            # maximum 404s allowed in the observation window
  observation_period: "1m"       # 404 sliding window (also the basis for risk decay)
  block_direct_ip: false         # block access that uses a bare IP as Host and matches no site
  forbidden_paths:               # custom sensitive path keywords (scored only on 404)
    - ".env"
    - "/wp-admin"
    - "/phpmyadmin"
```

> When first rolling out, keep `block_direct_ip: false`, watch the risk data on the dashboard, and tighten only after confirming there are no false positives.

---

## 2. Basic options

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | `false` | Master switch. Can be toggled at runtime from the dashboard/API. |
| `block_duration` | duration string | `"1h"` | Long ban duration. Short bans are 1/6 of this (at least 1 minute). Invalid values fall back to `1h`. |
| `max_404_attempts` | int | `5` | When an IP reaches this many 404s within `observation_period`, add `+5`. ≤0 falls back to `5`. |
| `observation_period` | duration string | `"1m"` | Length of the 404 sliding window. Invalid values fall back to `1m`. |
| `forbidden_paths` | list of strings | empty | Custom sensitive path keywords, substring-matched **only when the request is a 404**. Items starting with `/` are treated as `deny` (+30); others as extension-like and only scored (+6). |
| `block_direct_ip` | bool | `false` | When on, requests whose Host is a bare IP and match no site are judged `deny` (+8) and get 403. |
| `global_rules` | list | empty | Global governance rules, see section 4. |
| `site_policies` | map | empty | Per-site technology stack policies, see section 5. |
| `tech_profiles` | map | empty | Path fingerprints per technology stack, used with `site_policies`, see section 5. |

> Duration strings use Go format: `"30s"`, `"5m"`, `"2h"`.

---

## 3. Governance pipeline (stages)

Every request flows through the engine at these hooks; decisions from any stage are merged (the highest-priority action wins: `deny > tarpit > rate_limit > score > observe > allow`):

| Stage | When | What this module does |
|---|---|---|
| **OnIngress** | At the very front (before routing) | Checks whether the source IP is already banned / tarpitted / rate-limited |
| **OnRouteResolved** | After the Host matches a site, before route matching | Rechecks the IP block list; `block_direct_ip`; `site_policies` stack bans; **terminal actions** in `global_rules` (deny/tarpit/rate_limit) |
| **OnRouteMiss** | When the request is a 404 | Full 404 scoring (`score`/`observe` in `global_rules`, sensitive paths, UA, unknown Host, frequent 404s, multi-path scanning, ...) |
| **OnDecisionCommit** | When a terminal decision is actually enforced by the router | Bookkeeping: writes dashboard events and rule hit statistics, updates the IP's risk state |

> **Key point**: terminal actions (deny/tarpit/rate_limit) hit during route resolution are **not recorded immediately**; they are deferred to `OnDecisionCommit` (once interception is confirmed), so requests later let through by a magic-route fallback don't create false records. Non-terminal actions such as `score`/`observe` are recorded when hit.

---

## 4. Global rules: `global_rules`

`global_rules` is the core of the rule engine and applies to **all sites** (whether or not the Host matches).

```yaml
scan_protection:
  enabled: true
  global_rules:
    - name: "block_vcs"                 # rule name (for dashboard statistics)
      match:
        path_exact: ["/.git", "/.svn"]  # exact/segment match
        path_prefix: ["/.git/"]         # prefix match
        path_contains: ["/id_rsa"]      # substring match
      action: "deny"                    # deny|tarpit|rate_limit|score|observe|allow
      score: 30                         # risk score this rule contributes
      reason: "vcs_probe"               # reason label (shown on the dashboard)

    - name: "soft_watch_admin"
      match:
        path_prefix: ["/admin"]
      action: "observe"                 # record only: no score, no blocking
      score: 0
      reason: "admin_probe"
```

### 4.1 Fields

| Field | Description |
|---|---|
| `name` | Rule identifier, shown in the dashboard's rule hit statistics. |
| `match.path_exact` | Matches when `path == item`, **or** the path ends with the item, **or** the path contains `item + "/"` (treated as a path segment). |
| `match.path_prefix` | Path prefix match. |
| `match.path_contains` | Path substring match. |
| `action` | See action semantics below. Case-insensitive; unknown actions fall back to `allow` with a warning. |
| `score` | Added to the IP's risk score when hit. |
| `reason` | Custom reason label. |

### 4.2 Action semantics

| Action (synonyms) | Meaning |
|---|---|
| `deny` / `block` / `ban` | Reject directly (403) and record with `score`. |
| `tarpit` | Delay: the request sleeps before passing (once per request, about 3 seconds). |
| `rate_limit` / `ratelimit` | Return 429 and rate-limit for 1 minute. |
| `score` / `suspicious` | Only add risk score, no direct blocking (the accumulated score decides later actions). |
| `observe` | Record on the dashboard only; no score, no blocking. |
| `allow` / empty | Explicit pass (allow list); when hit, **no score and no record**. Useful for carving exceptions out of sensitive paths. |

> Terminal actions (deny/tarpit/rate_limit) **take effect immediately even with `score: 0`** — the action itself is mandatory; the score only affects the accumulated profile.

### 4.3 Built-in (legacy) rules

Whether or not `global_rules` is configured, these built-in rules always apply (your rules are **prepended** and match first):

- **Critical paths blocked directly** (`deny`, +30): `/.git`, `/.svn`, `/.hg`, `/.bzr`, `/.env`, `/wp-config.php`, `/etc/passwd`, `/proc/self/environ`, `/.aws/credentials`, `/.docker/config.json`, and paths containing `/.git/`, `/.env.`, `/id_rsa`, `/wp-json/gravitysmtp/`, `/wp-json/gravityforms/`, ...
- **`forbidden_paths`** items starting with `/` → `deny` +30; others (such as `.php`) → `score` +6.
- **Special probe paths** (404 only, +10): prefixes `/mcp`, `/sse`, `/actuator`, `/debug`, `/server-status`.
- **`/wp-admin`, `/phpmyadmin`** (404 only, +10).

---

## 5. Per-site stack bans: `site_policies` + `tech_profiles`

For "this site should never see paths of a certain technology stack" — for example a pure API site shouldn't be probed for WordPress paths.

```yaml
scan_protection:
  enabled: true

  # Reusable path fingerprints per stack
  tech_profiles:
    wordpress:
      path_prefix: ["/wp-admin", "/wp-content", "/wp-json/"]
      path_exact:  ["/xmlrpc.php"]
    phpmyadmin:
      path_prefix: ["/phpmyadmin", "/pma"]

  # Stacks to ban per site
  site_policies:
    api.example.com:
      deny_tech: ["wordpress", "phpmyadmin"]
      critical_action: "deny"     # action on hit: deny|tarpit|rate_limit|score|observe|allow
```

| Field | Description |
|---|---|
| `tech_profiles.<name>.path_prefix` / `path_exact` | Characteristic paths of the stack. |
| `site_policies.<host>.deny_tech` | Stacks forbidden on this site (keys of `tech_profiles`). |
| `site_policies.<host>.critical_action` | Action on hit. `deny` = 30 points, `tarpit` = 15, `rate_limit` = 10, `score` = 5, `observe` = 0, `allow` = pass. |

> `site_policies` keys are the **Host (site domain)**, case-insensitive. Matching happens in **OnRouteResolved** (site matched, route not yet matched), so requests can be blocked before reaching the backend.

---

## 6. Scoring and response thresholds

Each source IP keeps an accumulated risk `score`, and the decision engine picks the action from it:

| Accumulated score | Action | Behavior |
|---|---|---|
| ≥ 30 | `temp_ban_long` | Ban for `block_duration`, return 403 |
| ≥ 20 | `temp_ban_short` | Short ban for `block_duration/6` (at least 1 minute), return 403 |
| ≥ 15 | `tarpit` | Delay: each request sleeps about 3 seconds, for 1 minute |
| ≥ 10 | `rate_limit` | Return 429 for 1 minute |
| ≥ 5 | `suspicious` | Marked for observation only |
| < 5 | `observe` | Passed normally |

### 6.1 404 scoring signals (OnRouteMiss)

| Signal | Points | Condition |
|---|---|---|
| `not_found` | +1 | Every 404 |
| `post_unknown_path` | +6 | 404 with method POST |
| `unknown_host` | +5 | The request matched no site (each Host counted once per window) |
| `direct_ip_access` | +3 | No site matched and the Host is a bare IP |
| `bad_user_agent` | +2 | No site matched and the UA is missing or has scanner features |
| `sensitive_path` | +10 | Hit a special probe prefix (`/mcp`, ...) or `/wp-admin`, `/phpmyadmin` |
| `frequent_404` | +5 | **Distinct-path** 404s in the window ≥ `max_404_attempts` |
| `scan_multiple_paths` | +8 | The same IP hit ≥ 3 distinct paths (scored once) |
| `robots_txt` | +1 | 404 on `/robots.txt` |
| `global_rules` hit | the rule's `score` | See section 4 |

> **False-positive design**: weak signals such as `bad_user_agent`, `unknown_host` and `direct_ip_access` are **scored only when the request matched no site**. Legitimate clients (`curl`, `Go-http-client`, `python-requests`, monitoring probes) accessing **configured sites** don't accumulate risk because of their UA.
>
> Scanner UA keywords: `curl`, `wget`, `python`, `go-http-client`, `nmap`, `sqlmap`, `scan`, `headless`, `nikto`, `masscan`, `zgrab`.

> **Deduplication of repeats**: repeated 404s from the same IP on the same `method + Host + path` within `observation_period` **score once** (SSE reconnects, frontend polling, refreshes and duplicate form submits don't accumulate). Scanners don't hit the same path repeatedly, so detection is unaffected.
>
> **Strong/weak signals and the cap**: `not_found`, `post_unknown_path`, `unknown_host`, `frequent_404` and `scan_multiple_paths` are **weak signals** that real browsers also produce when a site isn't fully deployed or an API is misconfigured. An IP with only weak signals keeps accumulating score, but the response is **at most `suspicious`**; only when distinct-path 404s in the window reach `max_404_attempts` does it rise to `rate_limit`, and it **never reaches tarpit or bans**. Once a **strong signal** appears (`direct_ip_access`, `bad_user_agent`, `sensitive_path`, a scored `global_rules`/`deny_tech` hit), escalation follows the table normally, including the previously accumulated weak-signal score.

### 6.2 New-IP threshold and score decay

- **New-IP threshold**: an IP never seen before gets tracking state only when its first violation scores ≥ 5; one-off 404s below 5 pass without using memory.
- **Self-healing score**: when an IP is not banned / tarpitted / rate-limited, its score drops by 3 for about every 2 minutes idle (floor 0). Occasional probes decay to zero over time, and a misjudged client's score falls back once it stops misbehaving.

---

## 7. Runtime switch and hot reload

- `enabled` is the initial value at **process start**.
- At runtime toggle it with the dashboard's **"Scan Protection (Runtime)"** switch, or the API:
  ```
  POST /api/scan-protection/toggle?enabled=true     # on
  POST /api/scan-protection/toggle?enabled=false    # off
  ```
  This requires dashboard authentication and a CSRF check, and takes effect in memory.
- Other options (`block_duration`, `global_rules`, `site_policies`, ...) support **hot reload**; after a reload the policy is recompiled and takes effect immediately.

> ✅ **The runtime switch is authoritative**: configuration reloads **do not override** the switch set from the dashboard/API. `UpdateConfig` keeps the current `enabled` state, updates only the other fields and recompiles the policy with the current state. So "turn it off temporarily under heavy load and keep it off" works — even if a reload happens, `enabled: true` in the file won't turn it back on. The file's `enabled` is only the initial value at **process start**.

---

## 8. Performance and resource limits

The module bounds its own resources so it can't become an amplifier under targeted scanning:

- **Sharded state table**: 32 shards, at most 1560 entries each (about 50,000 IPs in total). When full, expired entries are evicted first; if still full, new IPs are not tracked.
- **Background cleanup**: every 10 seconds, removing IPs inactive for over 1 hour that aren't banned.
- **At most 64 404 timestamps per IP**; the **multi-path set** is released as soon as multi-path scanning is triggered.
- **Dashboard event queue capped at 100**; tracked paths truncated to 256 bytes, dashboard paths to 512 bytes.
- **Hot path cost**: a normal request does "one atomic read of the master switch + one shard read lock to check IP state + one linear scan of global rules". The more `global_rules` and path patterns, the costlier the OnRouteResolved scan — keep the rule set lean. Requests hitting legitimate routes get no 404 scoring.

---

## 9. Tuning and troubleshooting

- **Observe first, block later**: start high-risk rules as `observe`/`score`, and switch them to `deny` after the dashboard shows no false positives.
- **Your own frontend bugs pollute scores**: a frontend repeatedly requesting nonexistent paths (such as URLs containing `undefined`) builds up score for that real user's IP. Fix the frontend rather than relying on this module; as a stopgap add `allow` rules for those paths.
- **Allow-list sensitive paths**: use `global_rules` with `action: "allow"` for precise exceptions.
- **More aggressive**: lower `max_404_attempts`, shorten `observation_period`, or add `deny` rules.
- **More lenient**: raise `max_404_attempts` and trim the rule set.

---

## 10. FAQ

**Q: Will legitimate `curl` / Python / Go SDK clients get banned?**
A: No — as long as they access **configured sites**. Weak signals (UA, unknown Host) are scored only when no site matches.

**Q: Will a legitimate `.php` site be hurt because `forbidden_paths` contains `.php`?**
A: No. `forbidden_paths` only matches on **404**; a legitimate `.php` site responds normally and produces no 404s.

**Q: Does it protect against DDoS / CC?**
A: No. It is white-box detection and opportunistic mitigation by source IP; it doesn't replace dedicated DDoS/CC protection or a front WAF.

---

## Related docs

- Implementation: [scan_protection.go](../../../../internal/middleware/scan_protection.go)
- Multi-replica state: [ha-state.md](../10-deployment/ha-state.md)
- Dashboard and observability: [dashboard.md](../08-observability/dashboard.md)
- IP restriction: [ip-restriction.md](ip-restriction.md)
- Rate limiting: [rate-limit.md](rate-limit.md)
