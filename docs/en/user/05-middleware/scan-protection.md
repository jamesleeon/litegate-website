# Scan protection and governance rules

scan_protection is disabled by default. It provides in-memory, source-IP risk detection and opportunistic mitigation, complementing WAF and DDoS protection. State and bans are process-local; Redis-shared bans are not implemented. Configure trusted proxies through global real_ip.trusted_proxies to avoid attributing clients to a proxy IP.

Base fields: enabled defaults to false, block_duration to 1h, max_404_attempts to 5, observation_period to 1m. forbidden_paths extends sensitive paths. block_direct_ip defaults to false and blocks bare-IP Hosts only when no site matches.

global_rules supports name, match.path_exact/path_prefix/path_contains, action, score and reason. Actions are deny, tarpit, rate_limit, score, observe and allow. allow adds no score; terminal actions execute even with score 0. tech_profiles defines technology path fingerprints; site_policies.<host>.deny_tech references them and critical_action chooses the action.

The hooks are OnIngress → OnRouteResolved → OnRouteMiss → OnDecisionCommit. Terminal decisions are recorded only when actually executed, avoiding false records from magic-route fallbacks. Repeated 404s for the same method, Host and path are deduplicated within the window. Weak signals alone cap at suspicious, or rate limiting after the distinct-path threshold; they cannot trigger tarpit/bans. Strong signals enable full escalation.

Thresholds are 5 suspicious, 10 rate limiting, 15 tarpit, 20 short ban and 30 long ban. Short bans last block_duration/6, at least one minute; tarpit delays approximately three seconds. New IPs need an initial score of at least 5 to be tracked. Idle scores decay when no penalty is active. Approximately fifty thousand tracked IPs, periodic cleanup and bounded event queues constrain resources.

Dashboard or POST /api/scan-protection/toggle?enabled=true/false toggles protection after authentication and CSRF checks. Runtime state survives reload; configured enabled sets only the initial process state. Start with observe and move to deny after reviewing risk.

```yaml
scan_protection:
  enabled: true
  block_duration: 1h
  max_404_attempts: 5
  observation_period: 1m
  block_direct_ip: false
  global_rules:
    - name: watch-admin
      match: {path_prefix: [/admin]}
      action: observe
      score: 0
      reason: admin_probe
```

## Related documentation and code

- [Implementation](../../../../internal/middleware/scan_protection.go)
- [HA state](../10-deployment/ha-state.md)
