# LiteGate Kubernetes capability comparison and improvement plan

Assessment date: 2026-10-15. This concise English edition preserves the scope and acceptance status of the [detailed planning matrix](../zh-cn/litegate_k8s_traefik_capability_matrix.md). The comparison targets Traefik open source; commercial features require separate assessment.

This is an implementation and acceptance plan, not a complete support guarantee or Gateway API certification report. See [deployment and usage](litegate_k8s_usage_guide.md), [current capabilities and limits](litegate_kubernetes_capabilities.md) and the [optimization record](litegate_k8s_optimization_report.md).

## Assessment rules

Pin LiteGate, Traefik, Kubernetes and Gateway API versions for comparisons. An implementation path is distinct from a tested scenario; insufficient evidence does not prove absence. Verify source, test binary and deployed image independently. P0 covers production reliability, P1 major functionality and P2 scale/product experience. Existing data-plane functionality does not imply complete Kubernetes YAML configuration support.

The Chinese planning tables retain the pre-implementation baseline. The following table records final delivery for candidate `complete-20261015-12-patched`: all 28 unified stages, five browser states and the full two-hour soak passed. Each result is limited to its tested scope. Raw reports, build identity and the mapping of all 23 tasks are in the [evidence index](../../examples/k8s-acceptance/results/20261015/complete/final12/acceptance-evidence-index.json).

## Unified acceptance matrix

| # | Priority | Task | Delivered evidence and boundary | Status |
|---|---|---|---|---|
| 1 | P0 | Gateway API consistency | Upstream v1.4.1 HTTP 33, GRPC 13, TLS 11; seven declared extensions cover eight tests; zero failures/skips. Profiles share tests; no certification claim. | Passed |
| 2 | P0 | Explicit rejection | Strict validation, retained-field rejection and two-replica valid→invalid→recovered routing. Invalid matches withdraw forwarding; unsupported filters fail closed. | Passed |
| 3 | P0 | List/Watch recovery | Disconnect, 410/429/401/403 and real RBAC removal/recovery; nine fault scenarios. This is not a whole-cluster disaster-recovery claim. | Passed |
| 4 | P0 | Publication/listener reconciliation | Five scaling rounds, 1,694 HTTP and 1,694 TLS connections without error; listener isolation and continuous churn. Readiness waits for initial cache, catalog and listener publication. | Passed |
| 5 | P0 | Replicas and leadership | Lease partition/recovery, state-write fencing, UID/RV CAS and controller coexistence. Lease coordinates status writers, not all data-plane counters. | Passed |
| 6 | P0 | TLS fail-closed behavior | CA/SNI, expired/wrong certificates, Secret rotation/removal and per-port certificate isolation. No plaintext downgrade; not a CRL/OCSP implementation. | Passed |
| 7 | P0 | Tenant isolation | Namespace, AllowedRoutes, ReferenceGrant and controller ownership; cross-namespace backend/certificate/mirror references. ExtensionRef stays within one namespace. | Passed |
| 8 | P0 | Kubernetes compatibility | Main K3s 1.36.5; isolated 1.35.5/1.34.5 install, upgrade and rollback with 30 requests per phase. Limited to tested versions/scenarios. | Passed |
| 9 | P1 | Reusable policies/ExtensionRef | Same-namespace LiteGateTrafficPolicy reference, edit, deletion and recovery. Not arbitrary third-party Middleware support. | Passed |
| 10 | P1 | Backend filters | Backend headers, rewrite, mirror and policy; repeated Service references retain filter identity. Selected backends apply independently. | Passed |
| 11 | P1 | Standard timeouts | HTTPRoute request/backendRequest budgets, cancellation, deadlines and upstream timeout extension. Zero disables the budget. | Passed |
| 12 | P1 | Retries/governance | Replay/backoff, per-Pod limits, concurrency release and retry/circuit-breaker composition. Counters are replica-local; breaker counts upstream attempts. | Passed |
| 13 | P1 | Authentication resources | Basic/JWT Secrets, JWKS, OIDC PKCE/nonce and ForwardAuth; credential rotation/deletion and Redis recovery. Multi-replica OIDC requires shared Redis and keys. | Passed |
| 14 | P1 | BackendTLSPolicy fields | DNS/URI subjectAltNames, separate SNI and CA ConfigMap rotation; seven SAN scenarios. Invalid chains/identities fail closed. | Passed |
| 15 | P1 | gRPC/long connections | 24 client scenarios, h2c/grpcs/trailers/cancellation; 20-second bidirectional streams, WebSocket and SSE across upgrade. No unlimited stream guarantee. | Passed |
| 16 | P1 | Weights/mirroring/persistence | Seven weighted scenarios, invalid-backend probability, mirror isolation and Cookie/Header persistence. Mirror percent supported; fraction rejected. | Passed |
| 17 | P1 | Control-plane observability | List/Watch/status/rejection/leadership/notification metrics and raw fault/churn samples. Bounded labels; notification time differs from request-visible convergence. | Passed |
| 18 | P1 | Helm/rolling upgrades | Three scenarios, 898 API requests without error, three types of 20-second streams and retained shared keys. Explicit CRD upgrades remain required. | Passed |
| 19 | P2 | Scale convergence | Route-only and separate Route+Service+EndpointSlice models at 100/500/1000, 100 changes per size. Single-controller P95/P99 include patch and polling. | Passed |
| 20 | P2 | Soak | 7,200 seconds after 300 Route changes, six fault/rotation/scaling cycles; 71,700 successes, zero unexpected/transport errors. Stable-process RSS +2.34 MiB; goroutine/FD/socket counts unchanged. Limited to this two-hour contract. | Passed |
| 21 | P1 | WebServer/SPA/API integration | Immutable frontend, matching replica hashes, v1/v2/rollback and five browser states. Browser used a local fixed-Host bridge; cluster tests separately checked host routing. | Passed |
| 22 | P1 | Static/dynamic integration | Removed API returns JSON 503 while SPA remains 200; recovery and mixed-source withdrawal regression. Gateway withdrawal differs from native last-good retention. | Passed |
| 23 | P2 | H2 regression | Same source, same node, three alternating stock/overlay rounds each; correctness and regression budgets passed. No cross-round Traefik performance claim. | Passed |

## Delivery and coverage rules

Implementation order was reliability and standard tests, then YAML policy/filter/timeout/authentication support, then scale/upgrade/soak and integrated frontend validation. The first implementation round had not yet completed upstream conformance, SAN, cross-version, streaming, scale or soak checks; it remains historical rather than the current result.

Track implementation coverage, Kubernetes resource configurability and acceptance pass rate separately against fixed lists. Record unrun tests separately. Feature categories do not establish field-level compatibility; package tests do not replace upstream Gateway API tests.

Relevant implementation entry points are the [provider](../../internal/provider/k8s/provider.go), [Gateway resource types](../../internal/provider/k8s/types_gateway.go), [policy types](../../internal/provider/k8s/types_policy.go), [translator](../../internal/loader/gateway_translator.go) and [acceptance scripts](../../examples/k8s-acceptance/).
