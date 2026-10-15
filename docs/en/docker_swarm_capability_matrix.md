# Docker and Swarm capability matrix

Updated 2026-10-15. Accepted P0/P1/P2 work is implemented within the boundaries below. The final combined gateway passed the scoped three-node Swarm suites, standalone Docker checks and named L4 acceptance. Exact owned-resource cleanup and unchanged business Service specifications/versions were verified. These results do not imply unrestricted feature parity or production HA.

Only registered DSL fields configure LiteGate; arbitrary Docker labels do not. YAML support does not automatically imply label support. Docker reads container labels; Swarm reads Service `deploy.labels`. IDS requires a linked/registered provider, its capabilities, configured resources and operator permissions: labels cannot install plugins or grant access. The discovery alias is `litegate.http.services.<name>.discovery.name`; top-level `litegate.discovery.name` is not equivalent.

| Capability | YAML | Docker labels | Swarm labels | Implemented behavior and boundary |
|---|---|---|---|---|
| HTTP routers/services and matching | Supported | Supported | Supported | Known properties, validated references, Host/path/header/query rules |
| IDS and response hook | Supported | Supported | Supported | Provider/options/failure policy/trusted-header projection/selector merge; capabilities and isolation enforced |
| Active upstream health | Supported | Supported | Supported | Enable/timeout/protocol/gRPC service/thresholds; enabled checks with `initialready=false` gate traffic until success |
| Retry | Supported | Supported | Supported | Extra attempts, status/method gates and bounded body replay; real connection failure remains 502 |
| Sticky cookie | Supported | Supported | Supported | Name/TTL/Secure/HttpOnly/SameSite/path/domain across ordinary and upgrade responses; excluded from graphs |
| Router TLS | Site/listener policy | Finite options | Finite options | Per-host options preserve certificate source; no arbitrary workload certificate paths or named cert-resolver DSL |
| Upstream transport | Supported | Supported | Supported | SNI/trust/timeouts/pooling; operator central trust references |
| Shared resources | Central/local | Local or explicit `@file` | Local or explicit `@file` | Middleware/transport/TLS options validate and reload transactionally, including graph leaves; no implicit cross-provider lookup |
| Container/Task health | Discovery dependent | `starting`/unhealthy excluded | Running Tasks initially eligible | Task state is not HTTP application readiness; active checks provide that gate |
| Zero/deletion/API failure | Declared routes persist | Last container gone removes declaration | Zero Tasks retain declaration/empty pool | HTTP unavailable pool 503; Service deletion removes route; failed full snapshots retain last good state |
| Multiple ports/publishing | Per-Service | Typed TCP/UDP host maps | Task network ports | Protocol/container-port mapping, IPv6, missing-map exclusion and pure UDP publishing; no Swarm host-published-port resolution claim |
| Source ownership | Explicit Docker source | Per-container records | Physical Service owns Tasks/VIP | Explicit same-alias multi-Service lookup rejects ambiguity even with instance selected; standalone grouping/legacy alias union preserved |
| Network and VIP | Operator catalog | Container network | Explicit Service VIP | Validated non-ingress network; ambiguous/missing network, DNSRR or absent VIP has no Task fallback; zero stays empty |
| VIP selection limits | Enforced | Not applicable | Enforced | Static instance policies reject; final IDS selectors/metadata/tags/gray fail closed even with override |
| Constraints and SSH | Operator catalog | Applies | Applies | Strict Label/LabelRegex/`!`/`&&`/`||` across source paths; pure Go SSH, verified known_hosts pins/host CA, bounded setup/cleanup, no URL passwords |
| HTTP weighted/failover graphs | Static/explicit Docker leaves | Registering-source leaves | Registering-source leaves | Real group weights independent of replicas; nested graphs, strict refs/cycles, distinct leaf port/TLS/health/pools; other explicit source providers unsupported |
| Graph request governance | Supported | Supported | Supported | One IDS/body buffer/root timeout/retry budget/final hook; hard conditions intersect final IDS; unresolved templates reject whole request |
| Named TCP/UDP | Stream YAML | Implemented | Implemented | Raw TCP/UDP, shared-port TLS SNI passthrough and atomic admission locally tested; real Swarm update/zero/recovery and same-alias source isolation passed |

Graphs support ordinary HTTP(S). Cookies and child retry/timeout policies are rejected; upgrades return 503 and gRPC/gRPC-Web return RPC unavailable (14) without upstream traffic. Primary-only conditions are not inherited by sibling fallback: declare common tenant boundaries on the group/root. Empty/unhealthy fallback consumes no actual attempt; retryable failures share the root budget.

Named L4 excludes IDS, middleware, graphs and named TLS termination/certificate paths/resolvers. Operator TCP attachment must explicitly handle non-TLS/no-SNI traffic and existing HTTP/operator routing; conflicting admission is rejected. Shared transport caps apply to the same endpoint plus policy, not separate per-Service quotas.

## Traefik Proxy OSS 3.4 comparison and remaining gaps

The lab pins **3.4.4**, not Hub/Enterprise. This is behavior/configuration comparison, not a performance ranking.

| Area | Difference / remaining gap |
|---|---|
| Empty pool | LiteGate retains declared Swarm routes with 503; the pinned lab returned Traefik 404. Traefik's configurable `allowEmptyServices` means this is not universal behavior. [Official Swarm provider](https://doc.traefik.io/traefik/v3.4/providers/swarm/#allowemptyservices) |
| Retry | LiteGate status/method gates add behavior beyond Traefik Retry, which stops after any HTTP response regardless of status. [Official Retry](https://doc.traefik.io/traefik/v3.4/middlewares/http/retry/) |
| Composition | Traefik 3.4 documents service WRR for File/IngressRoute and failover for File; do not infer Docker/Swarm label equivalence. LiteGate implements its own restricted named graph labels. [Official Services](https://doc.traefik.io/traefik/v3.4/routing/services/) |
| Certificates | Traefik names static certificate resolvers and associates routers with them. LiteGate retains site/auto-cert sources and finite TLS options; resolver/provider ecosystem parity remains open. [Official ACME](https://doc.traefik.io/traefik/v3.4/https/acme/) |
| L4 | Traefik documents TCP TLS termination/passthrough and UDP routing; LiteGate named L4 is narrower. [Official Routers](https://doc.traefik.io/traefik/v3.4/routing/routers/) |

IDS is LiteGate-specific, not a Traefik equivalence test. Remaining gaps include broader graph providers, composition cookies/upgraded protocols, named L4 termination/governance and certificate-resolver ecosystem coverage. No benchmark, manager/node-failure HA or production reliability conclusion is claimed.

## Final acceptance evidence

Artifacts are local paths under `artifacts/swarm-acceptance/`, not public download links. Frozen manifests identify uncommitted implementation by hashes; base Git revision alone is insufficient. P8 gateway SHA-256: `c3f47480b84f9fb3246c5b8c49b6f85440cd00bca5760d7ea8ab49c9ebd56f7c`. Later repairs are not attributed to this binary.

- `baseline-report.json`: eight of eleven passed, three failed and retained. `docker-baseline-report.json`: standalone discovery/IDS/trusted headers.
- `p1-report.json`: staged lifecycle/ports/zero/health/readiness/IDS checks passed. `phase6-second-report.json`: central reload, rejected-generation retention and recovery. Main JSON is not watched directly; the lab used the existing watched reload trigger.
- `phase7-fourth-report.json`: VIP/zero/network/DNSRR/constraints/static and IDS rejection/restoration. `ssh-p7-final-report.json`, `ssh-p7-final-wrong-key-report.json`, `ssh-p8-report.json`: strict SSH evidence. `phase8-report.json`: replica-independent ratios and failover/unhealthy/zero/recovery on its frozen build.
- Local tests/race cover host CA verification, health GC/readiness, physical source ownership/ambiguity, pure UDP host mapping and named L4. Warning capture now uses isolated test subprocesses with unchanged assertions; this repairs test interference, not production logging.
- Earlier failed SSH/VIP/central reports remain. An old owned Service VIP refused traffic while its Tasks and a fresh same-spec fixture worked; staged VIP acceptance passed after fixture recreation. This does not establish a LiteGate bug or Docker root cause.
- The final live gateway in the six suites below is the same `gateway:p9` binary, SHA-256 `15787bbd63ffab562cb2de866353f9282557e9b743191a65def398afe3a1068b`: `phase9-second-report.json` (named TCP/UDP/shared SNI and same-alias isolation); `final-swarm-second-report.json` (11/11); `final-docker-report.json` (3/3); `final-central-report.json`; `final-vip-report.json`; `final-graphs-report.json` (all passed). `final-ssh-report.json` verifies all three Managers with strict pins and rejection of a wrong key using the separately hashed connector probe.
- Health comparison retains an earlier observation where Traefik served a newly started, not-yet-ready Task with HTTP 200. The final health-proven unavailable window produced LiteGate 503 and Traefik 503; this is not evidence that Traefik universally routes unhealthy Tasks.
- Full Go `./...` tests, the eleven-package race run, vet and the final 46 Python harness tests passed. Read-only reviews are retained in `requirements-audit-source-fixes.md`, `requirements-audit-phase9-live.md`, `requirements-audit-final-live-progress.md` and `requirements-audit-health-final.md`. Their scope and earlier failure observations remain part of the evidence.
- `final-cleanup-report.json` passed: exact owned Service/network/config IDs were removed, all three nodes had no owned Service/network/config/container inventory, local state was cleared, business specifications and versions matched baseline, and nodes remained Ready/Active. The initial short-ID cleanup failure, corrected recovery and first failed report are retained in `final-cleanup-first-failed-report.json` and `final-cleanup-state-recovery.json`.
- Owned images and owner-scoped temporary build assets remain for reproduction; cleanup is not a disk-pruning claim. `phase10-source.zip` and `phase10-build.json` freeze the final source/manifest after documentation and harness/test updates. The actual P10 build produces exactly the same SHA-256 as the live-tested P9 gateway above; it is the verified same binary, not a newly unverified executable.

See the [isolated acceptance lab](../../examples/swarm-acceptance/README.md). Remaining feature limits in this matrix continue to apply after acceptance.
