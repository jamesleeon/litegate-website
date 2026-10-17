# Current Kubernetes capabilities and limits

This is an index of implementation capabilities, not a certification report or a promise of drop-in replacement.

| Capability | Current implementation |
|---|---|
| Service/EndpointSlice | REST list/watch, reconnect/relist, readiness/termination filtering |
| Ingress/IngressClass | Class ownership, host/path/defaultBackend, Secrets and status |
| GatewayClass/Gateway | controllerName ownership, listeners, AllowedRoutes, TLS and status |
| HTTPRoute/GRPCRoute | Translation, parentRefs, matching, weighted Service backends and status |
| HTTP filters | Implemented subset including request/response headers, redirects, URLRewrite and mirrors |
| ReferenceGrant | Cross-namespace backend, certificate and mirror authorization |
| BackendTLSPolicy | CA/system trust, SNI, upstream TLS and fail-closed handling |
| TLSRoute | Same-port aggregation and SNI passthrough dispatch |
| TCPRoute/UDPRoute | L4 forwarding with stable precedence for port conflicts |
| LiteGateTrafficPolicy | Project-specific traffic policy and status |
| HA deployment | Helm/native manifests, RBAC and Lease leader election |

Only a subset of ingress-nginx annotations is supported, not its full policy surface. GRPCRoute, extension filters, non-Service backends and version support follow the actual types, validation and tests. Code/unit tests are not Gateway API conformance; avoid claiming complete support without a published report.

Status writes keep other controllers' parent entries. BackendTLSPolicy and LiteGateTrafficPolicy report one `status.ancestors` entry (with `controllerName`) per Gateway this controller owns and keep other controllers' entries; a controller that does not own the target writes nothing and removes its own entries when it loses ownership. The top-level LiteGateTrafficPolicy `status.conditions` is deprecated: it holds the conditions of the sole owner (a controller that drops out promotes the remaining owner's) and is cleared while several controllers own the target, so read `status.ancestors` instead.

Watch/namespace scope can be reduced and insufficient permissions may disable capabilities. Validate large-cluster performance, API budgets, watch recovery and listener exposure in the target environment. TLSRoute aggregation fixes the obsolete first-route-only limitation; historical audits are not current behavior.

## Related documentation and code

- [Usage](litegate_k8s_usage_guide.md)
- [Provider tests](../../internal/provider/k8s/provider_test.go)
- [Gateway translator](../../internal/loader/gateway_translator.go)
- [Gateway tests](../../internal/loader/gateway_translator_test.go)
