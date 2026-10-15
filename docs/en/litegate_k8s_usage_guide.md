# Kubernetes deployment and usage

Current code supports EndpointSlice discovery, standard Ingress, Gateway API and status updates. Install required Gateway API CRDs, then the repository Helm chart or native manifests. Entry Services/DNS deliver traffic to the gateway; Ingress/Gateway objects route traffic after arrival. Both are necessary.

Ingress controller is litegate.io/ingress-controller; Gateway controllerName is litegate.io/gateway-controller. Repository class names default to litegate. Use explicit ingressClassName/parentRefs rather than assuming every class is owned. Configure watch switches, namespace scope, RBAC and published status addresses.

HTTPS uses Secrets or gateway certificate capabilities. Cross-namespace backends, TLS Secrets and mirrors require ReferenceGrant. BackendTLSPolicy configures CA/system trust and SNI; invalid security policy fails closed rather than silently downgrading to plaintext. LiteGateTrafficPolicy supplies project-specific retry, timeout, limiting, breaking, WAF, CORS and concurrency policies.

Multiple TLSRoutes on one port are aggregated for SNI routing. TCPRoute/UDPRoute port conflicts use stable precedence arbitration, distinct from the obsolete first-TLSRoute limitation. Replicas can use Lease leader election; this coordinates controller work, not all data-plane memory.

Check Accepted/ResolvedRefs, RBAC, watch logs, ready EndpointSlices, entry Service ports, certificates and real requests. Implemented support is not a claim of full Gateway API conformance.

```bash
helm install litegate ./deploy/helm/litegate -n litegate-system --create-namespace
```

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-app
spec:
  ingressClassName: litegate
  rules:
    - host: app.example.com
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: my-app
                port: {number: 80}
```

## Related documentation and code

- [Capabilities](litegate_kubernetes_capabilities.md)
- [Helm](../../deploy/helm/litegate)
- [Native manifests](../../deploy/k8s)
- [Provider](../../internal/provider/k8s/provider.go)
