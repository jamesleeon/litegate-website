# LiteGate and Traefik container capability matrix

This concise English edition summarizes the [detailed source-based comparison](../zh-cn/litegate_traefik_container_capability_matrix.md), whose row-level source index is retained for audit. It compares implementation paths, not production maturity, throughput or certification.

## Fixed scope and evidence

LiteGate was assessed from the local workspace based on commit `bcc663254dd03c003e9483e62897f52a39d17232`, including changes present at assessment time. Conclusions do not automatically apply to a published binary of that commit. Traefik Proxy open source was checked at v3.6.0, commit `06db5168c0d936a0716cbede56bc2cd332be0d4f`; this is a reproducible baseline, not a claim about the latest release. Commercial products and third-party plugins are excluded.

“Implemented” means configuration, discovery/conversion and execution paths exist. It does not establish full specification coverage or real-cluster acceptance. A missing path in one provider does not prove the entire product lacks a capability. The original assessment did not deploy Docker/Swarm/Kubernetes clusters, run Traefik tests, performance benchmarks or upstream conformance. Later Kubernetes acceptance is separately recorded in the [optimization report](litegate_k8s_optimization_report.md).

## Docker and Compose

| Capability | LiteGate | Traefik v3.6.0 |
|---|---|---|
| Discovery and Compose grouping | Container discovery; defaults to Compose project/service names, with overrides | Container discovery and Compose name handling |
| HTTP labels | Native `litegate.*` resource compilation | `traefik.*` Router/Service/Middleware decoding |
| Exposure defaults | No LiteGate labels means no registration; any `litegate.*` label can trigger it; explicit enable takes priority | ExposedByDefault defaults true; can be disabled with enable-label selection |
| Events and reconnect | Subscribe before snapshot, events, reconnect and default 60-second reconciliation | Events, snapshot rebuild and reconnect backoff |
| Health | Reads health and handles healthy/unhealthy events | Filters health/state; empty-service behavior depends on AllowEmptyServices |
| Networks and host ports | Explicit network, internal/external and usehostport with fallback | Network, UseBindPortIP and host-network handling |
| Transports | Unix/TCP/TLS/SSH/Windows pipe with validation | Docker client and connection configuration; platform behavior depends on environment |
| Constraints | Compiled label constraints | Label constraints |
| Multiple Docker sources | Named catalogs, stable identity and explicit reference/ownership checks | One Endpoint per Docker Provider configuration; not equivalent to named catalogs |
| Named TCP/UDP labels | Explicit entrypoint and local service reference required | TCP/UDP routers and services |
| Named TCP-label TLS termination | Only passthrough: tls.enabled and tls.passthrough must both be true | TCP termination and passthrough |

The label syntaxes are different. LiteGate's TLS support through other entry points does not remove the named TCP-label passthrough restriction. See [catalog identity and transports](docker_catalog_identity_and_transport.md).

## Docker Swarm

| Capability | LiteGate | Traefik v3.6.0 |
|---|---|---|
| Declaration source | Service.Spec.Labels, separate from task endpoints | Service labels |
| Task IP | Available-task and network-address selection | Running tasks and network addresses |
| Service VIP | Explicit `litegate.swarm.lbswarm=true` path | LBSwarm VIP selection |
| VIP constraints | Explicit network required; rejects ingress, dnsrr and ambiguous VIP; no silent Task-IP fallback | VIP/network selection exists; not equivalent to LiteGate validation |
| Updates | Events/debounce plus authoritative polling; fast rolling-update/rollback reconciliation | Swarm Provider ticker polling, separate from Docker container events |
| Default interval | 5 seconds, configurable | 15 seconds, configurable |
| Manager/mode | Explicit swarm mode; optional manager-based auto-detection, disabled by default | Separate Swarm Provider needs manager API access |
| Overlay/stack networks | Network selection and stack prefixes, with task fallback diagnostics | Overlay data and explicit network selection |
| Published-port/routing mesh mode | External setting warns in Swarm; internal tasks or explicit VIP are the main paths | Task/VIP paths confirmed; UseBindPortIP does not establish full routing-mesh support |
| Zero replicas | ServiceSnapshot copies declarations/endpoints under one lock and retains endpoint-free declarations | Service/task dynamic configuration; empty-service behavior is configuration-dependent |
| HTTP/TCP/UDP labels | Shared label compiler; TCP TLS restriction remains | Shared dynamic configuration builder |

Polling intervals are control-plane settings, not measured recovery times. Discovery success does not prove gateway connectivity to the overlay network.

## Kubernetes

| Capability | LiteGate | Traefik v3.6.0 |
|---|---|---|
| Service/EndpointSlice | Native paged List/Watch, resourceVersion and endpoint conditions | Kubernetes client/informer discovery |
| Ingress/IngressClass | Ownership, conversion, TLS Secrets and status | Ingress Provider class selection, TLS and status |
| Gateway/HTTPRoute | Ownership, listeners, matching, status, headers, redirect, rewrite and weights | Corresponding Gateway Provider paths |
| Standard RequestMirror | Authorized lowering and execution, including percent; not all extension fields | Gateway loadMiddlewares does not accept RequestMirror; TraefikService mirroring is another entry point |
| Standard timeouts/persistence | Parsing, validation, lowering and execution within supported fields | Complete HTTPRoute field conversion not found in this assessment; transport timeout/sticky settings are separate |
| GRPCRoute | Provider, protocol validation and proxy conversion | grpcroute.go implementation |
| TLSRoute/TCPRoute | Watch/status/L4 publication; TLS listeners require Passthrough, HTTPS terminates | Requires experimentalChannel |
| Gateway UDPRoute | Watch/status/conflict arbitration and stream publication | No Gateway UDPRoute loading path; CRD IngressRouteUDP is available |
| Cross-namespace references | ReferenceGrant for backends, mirrors and certificates | Gateway ReferenceGrant; CRD AllowCrossNamespace has separate semantics |
| BackendTLSPolicy | Hostname, CA/system CA, SAN validation, status and CA watch | Hostname, system CA/ConfigMap CA and ServersTransport; CA references accept ConfigMap |
| Native ExternalName/ClusterIP selection | Service model lacks these native backend-address paths; manual URLs do not count | Provider paths exist; ExternalName sometimes requires explicit permission |
| Governance CRDs | LiteGateTrafficPolicy retry, limits, breaker, WAF, CORS, connection limits and authentication | Middleware, TraefikService, ServersTransport and related CRDs |
| Native JWT/JWKS/OIDC | Policy, Secret and runtime paths | No corresponding native open-source dynamic Middleware configuration; ForwardAuth/plugins are separate |
| Recovery/status coordination | Watch recovery, initial sync, generation checks and Lease write fencing | Client/informer recovery and status paths; equivalent Lease coordination was not established here |
| Official conformance | Not executed during this comparison; no certification conclusion | Certification reports not checked; SupportedFeatures alone is insufficient |

The CRDs are not compatible. Gateway UDPRoute, mirroring and authentication paths do not imply complete Traefik replacement. Local and Redis rate limiting exist in both products; Redis rate limiting is not unique to LiteGate. Retry, circuit-breaker and ForwardAuth fields/semantics differ. No radar score or completion percentage is provided without common weights and equivalent tests.

## Source and local verification

The detailed edition maps each comparison row to LiteGate and pinned Traefik source. Local entry points include the [Docker provider](../../internal/provider/docker/provider.go), [connection client](../../internal/provider/docker/client.go), [label compiler](../../internal/loader/tag_resource_compiler.go), [TCP/UDP label validation](../../internal/loader/tag_stream_resources.go), [Swarm VIP](../../internal/provider/docker/vip.go), [Kubernetes provider](../../internal/provider/k8s/provider.go), [Gateway translator](../../internal/loader/gateway_translator.go) and [rate limiter](../../internal/middleware/ratelimit.go).

The assessment explicitly set GOOS=windows and GOARCH=amd64 and ran:

```powershell
$env:GOOS = 'windows'
$env:GOARCH = 'amd64'
go test ./internal/provider/docker ./internal/provider/k8s ./internal/loader ./internal/action ./internal/app
```

All five packages passed: Docker/Kubernetes were cached; loader took 16.362 seconds, action 21.407 seconds and app 38.849 seconds. An earlier default-platform attempt failed with `%1 is not a valid Win32 application` and is not counted as passed. Package tests do not replace cluster acceptance. The detailed comparison also checked all 53 local source links and Markdown trailing whitespace.
