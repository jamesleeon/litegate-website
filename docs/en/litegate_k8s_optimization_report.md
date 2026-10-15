# Kubernetes optimization and acceptance record

Date: 2026-10-15. This concise English edition summarizes the [detailed Chinese record](../zh-cn/litegate_k8s_optimization_report.md), including its build provenance, measurements and retained failures. It covers the 23 tasks in the [capability plan](litegate_k8s_traefik_capability_matrix.md).

## Implementation and build identity

The delivered work covers Gateway API matching and status semantics; Watch/RBAC recovery; Lease fencing and UID/resourceVersion checks; bounded configuration publication; startup readiness; invalid-route withdrawal; listener/certificate isolation; backend CA/SNI/SAN validation; reusable policies and backend filters; standard timeouts, retries and persistence; authentication resources; gRPC and streaming; Helm and integrated frontend deployment.

Readiness now waits for initial Kubernetes Lists, the first successful catalog commit and successful listener/route publication. Later invalid tenant configuration does not remove an already ready replica. Updating a valid HTTPRoute to an unsupported match withdraws its old forwarding route while preserving valid routes on the same host and legitimate HTTPS certificate placeholders.

- Main environment: three Linux amd64 nodes, K3s v1.36.5+k3s1.
- Gateway API CRDs and unmodified upstream test module: v1.4.1 experimental.
- Toolchain: Go 1.27.1, CGO disabled, trimpath enabled, buildvcs disabled.
- Final candidate: `litegate-lab:complete-20261015-12-patched`.
- Binary SHA-256: `f52a1979863ba74974715babfa481d3d304b7e12e590fa1388ff0f6f88477336`.
- Docker config/runtime imageID: `5c6d105cb7c7a6ca5431e15fe3ca5d77604b13bd1b48dd803d8fb129e9ba7033`.
- Source superset fingerprint: `a2a36f9696f47cd2a614c00febe1d3ab1d66b1cdc614f243fbbd5bb1574cf13e`.

The [build proof](../../examples/k8s-acceptance/results/20261015/complete/build-image12.json) records source, embedded inputs, toolchain patch, binary, archive and Docker config digests. Its 621 non-test Go files are a source superset, not a claim that every file was compiled into the main binary. Runtime identity is checked against the archived binary and ready Pod imageIDs; a tag alone is insufficient provenance. Local full Go testing passed 71 packages, four startup/withdrawal race checks passed, and the native-tag mixed-source regression passed the loader package. `go mod verify` passed against the same dependency inputs.

## Final acceptance

All 28 stages passed. After the full soak, a full-plan `--resume` without `--only` matched all original successful evidence and input fingerprints. See the [stage summary](../../examples/k8s-acceptance/results/20261015/complete/final12/stages/summary.json) and [23-task evidence index](../../examples/k8s-acceptance/results/20261015/complete/final12/acceptance-evidence-index.json).

| Unmodified upstream v1.4.1 scope | Passed | Failed | Skipped |
|---|---:|---:|---:|
| HTTP core | 33 | 0 | 0 |
| GRPC core | 13 | 0 | 0 |
| TLS core | 11 | 0 | 0 |
| Tests for seven declared extensions | 8 | 0 | 0 |

Profiles share Gateway tests; these counts must not be summed as unique cases or interpreted as certification. The second HTTP run is the final candidate attribution snapshot; the first retained observations of terminating older replicas.

Five independent `1→2→1` scaling rounds completed 1,694 new HTTP and 1,694 new TLS connections without error. All six measured ready Pods matched the candidate imageID. Helm upgrade/rollback sustained 898 API requests without errors and retained bidirectional gRPC, WebSocket and SSE connections for 20 seconds each. Two replicas had identical frontend hashes and retained shared keys. Browser checks passed v1/Connected, v2/Connected, API removal/Unavailable, recovery/Connected and rollback/v1/Connected. The first manual browser attempt is retained as a failure; the second checked replica hashes and ingress convergence first.

Isolated K3s v1.34.5+k3s1 and v1.35.5+k3s1 installations, configuration upgrades and rollbacks each passed 30 requests per phase with matching imageIDs. This is evidence for those versions and scenarios only.

## Scale, soak and H2

The final soak ran HTTP/TLS traffic for 7,200.0008 seconds, followed by about 75 seconds of idle/GC sampling. It recorded 71,700 successful requests, 244 expected injected-backend responses (two 502 and 242 503), zero unexpected errors and zero transport exceptions. Six rounds of certificate rotation, controller scaling and backend failure/recovery passed. Only HTTP 502/503/504 during injection windows counted as expected; TLS and transport failures never did.

The stable Pod UID, PID 7, process start time and candidate imageID remained unchanged. RSS rose from 78,147,584 to 80,601,088 bytes: 2.34 MiB, below the predefined 64 MiB threshold. Goroutines stayed 91, FDs 30 and socket FDs 22. This establishes the two-hour contract, not unlimited leak freedom. See the [raw soak report](../../examples/k8s-acceptance/results/20261015/complete/final12/evidence/scale-soak-attempt1/summary.json).

| Route-only model | Changes | P95 seconds | P99 seconds | Maximum seconds | API reads |
|---:|---:|---:|---:|---:|---:|
| 100 | 100 | 0.6436 | 0.8165 | 1.1778 | 216 |
| 500 | 100 | 0.6655 | 0.7358 | 0.7380 | 229 |
| 1000 | 100 | 0.6373 | 0.7097 | 0.7353 | 229 |

An independent model used 100/500/1000 objects of each kind: HTTPRoute, Service and EndpointSlice, with 100 EndpointSlice changes per size.

| Objects per kind | P95 seconds | P99 seconds | API reads | Mean CPU cores | End RSS MiB |
|---:|---:|---:|---:|---:|---:|
| 100 | 0.2075 | 0.2189 | 131 | 0.0360 | 48.43 |
| 500 | 0.2078 | 0.2119 | 30 | 0.0877 | 67.37 |
| 1000 | 0.2138 | 0.2240 | 35 | 0.1601 | 94.41 |

These are single-controller measurements. Convergence includes patch requests and polling; CPU/API windows can include background reconciliation. End RSS is neither a continuous peak nor a long-term growth result. See the [object-scale evidence](../../examples/k8s-acceptance/results/20261015/complete/final12/evidence/object-scale-attempt1/).

H2 compared the same source/toolchain on the same `litegate-be` node in three alternating stock/overlay rounds each. Correctness passed with zero errors. Median successful RPS was 5996.69/6864.86, P99 was 41.118/38.285 ms, CPU 1.3960/1.4014 cores and median per-round maximum sampled RSS 52.76/53.36 MiB. RPS ratio 1.1448 and P99 ratio 0.9311 met the predefined regression limits (RPS ≥0.8; P99 ≤1.5). This is a laboratory regression, not a Traefik performance comparison. See the [H2 report](../../examples/k8s-acceptance/results/20261015/complete/final12/evidence/h2-attempt1/summary.json).

## Retained failures and support limits

Candidate 10 became ready about 1.3–1.7 seconds before HTTPS listening; independent scaling reproduced 19 TLS connection refusals. Candidate 11 fixed startup readiness, but invalid-match testing exposed stale forwarding after a route was rejected. Candidate 12 fixed withdrawal. Candidate 11's soak was interrupted; candidate 10's errors and candidate 5's older error classifier cannot establish final acceptance. Earlier attempts, namespace-deletion races, diagnostic script corrections and superseded results remain recorded in the detailed edition. Candidate 10's H2 rounds used different nodes and are historical only.

Unsupported features include path RegularExpression, the standard CORS filter, mirror fraction, arbitrary non-Service backends and nested policy extensions. Retained unknown fields are rejected; fields pruned by the API server require strict validation. Unsupported matches produce no replacement route; unsupported filters on known matches fail closed. Cross-namespace backends, mirrors and certificates require ReferenceGrant; ExtensionRef is same-namespace only. Multi-replica OIDC requires shared Redis and identical encryption keys. Lease election does not share local rate-limit/circuit-breaker counters. TLS listeners support explicit Passthrough; use HTTPS for termination.

Reproduction uses the [acceptance guide](../../examples/k8s-acceptance/README.md). Plans freeze image, binary, scripts, Chart, CRDs and fixtures; only successful stages with identical fingerprints can be reused. Partial `--only` runs cannot establish full acceptance. Runtime configuration and keys live in Secrets; evidence excludes deployment credentials. Upgrade CRDs explicitly: Helm upgrade does not update installed `crds` resources automatically.
