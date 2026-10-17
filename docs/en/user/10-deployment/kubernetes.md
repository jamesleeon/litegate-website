# Kubernetes Deployment Guide

This is the entry point for running LiteGate on Kubernetes. It is organized by task: choose a usage, install, then configure your scenario. Field-level details and capability limits are linked at the end.

Inside a cluster LiteGate is both an **Ingress / Gateway API controller** and a complete **web server**. The same Pods can handle ingress routing, static frontends, SPAs, file downloads, Markdown documentation, WebDAV and status pages, without a separate nginx for the frontend. That is the main difference from proxy-only controllers such as Traefik.

---

## 1. Choose a usage

| Usage | Good for | Where routes live |
|---|---|---|
| Ingress controller | Existing Ingress manifests, migrating from ingress-nginx | `Ingress` (`ingressClassName: litegate`) |
| Gateway API controller | New projects, multi-team delegation, L4 (TCP/UDP/TLS) | `Gateway` + `HTTPRoute` / `GRPCRoute` / `TLSRoute` etc. |
| Gateway + web server | SPA frontend + backend API, docs sites, download sites | Native site YAML (mounted into the Pod) + either API above |
| Service annotation shortcut | Exposing simple services directly | Service label `litegate.io/expose=true` + annotation `litegate.io/domain` |

These usages can coexist in one deployment. For the same hostname, native sites and Kubernetes routes merge into one site and are matched by longest path, so a native `/` never shadows an HTTPRoute `/api`.

---

## 2. Install

### 2.1 Prerequisite: Gateway API CRDs

Skip this when you only use Ingress. For Gateway API, install the CRDs of the validated version (currently v1.4.1 experimental):

```bash
kubectl apply --server-side -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.4.1/experimental-install.yaml
```

### 2.2 Install with Helm

```bash
helm install litegate ./deploy/helm/litegate -n litegate-system --create-namespace
```

By default this creates:

- a 2-replica Deployment with Lease leader election (the leader writes status);
- a `LoadBalancer` entry Service (80/443);
- an IngressClass and a GatewayClass named `litegate`, with `litegate` as the default IngressClass;
- a ClusterRole/ClusterRoleBinding and the runtime configuration Secret.

Common values:

| Value | Default | Purpose |
|---|---|---|
| `controller.ingressClass` / `controller.gatewayClass` | `litegate` | Class names to claim; use distinct names per installation in one cluster |
| `controller.isDefaultIngressClass` | `true` | Claim Ingresses without a class |
| `service.type` | `LoadBalancer` | Use an LB in the cloud; `NodePort` or MetalLB on bare metal |
| `config.*` | see values.yaml | Copied into the LiteGate main configuration |
| `existingConfigSecret` | empty | External Secret (key `litegate.yaml`) holding the full configuration |
| `extraVolumes` / `extraVolumeMounts` | empty | Mount site configuration, frontend files, etc. |
| `initContainers` | empty | Prepare files before start, e.g. copy build output from a frontend image |

Without Helm, apply the native manifests in `deploy/k8s/` in this order: RBAC, IngressClass/GatewayClass, Deployment, Service.

### 2.3 Check readiness

```bash
kubectl -n litegate-system get pods
kubectl -n litegate-system logs deploy/litegate | grep -i -E "error|forbidden"
```

`/readyz` returns 200 only after every enabled Kubernetes resource has completed its first sync and routes are published. A Pod that stays unready usually lacks RBAC or a CRD. Fix the permissions or explicitly disable unused watches (for example `disable_tcp_route_watch: true`); do not hide the problem with longer probe delays.

### 2.4 Running outside a cluster (kubeconfig)

For local debugging or deployments outside the cluster, LiteGate reads kubeconfig like kubectl does. When it is not in a cluster and `api_server_url` is not set, it looks for `$KUBECONFIG`, then `~/.kube/config`:

```yaml
service_discovery:
  providers:
    k8s:
      kubeconfig: /home/ops/.kube/config   # optional; a path list like $KUBECONFIG
      kube_context: prod-eks                # optional, defaults to current-context
```

- Supported: token, tokenFile, client certificates (files or `-data`) and **exec credential plugins**, for example `aws eks get-token` for EKS, `gke-gcloud-auth-plugin` for GKE and `kubelogin` for AKS. Plugin credentials are cached until 30 seconds before they expire and fetched again immediately when the API returns 401.
- Legacy `auth-provider` plugins and username/password auth are rejected with an error instead of falling back to anonymous access.
- `token`, `token_file`, `client_cert_file`/`client_key_file` and `ca_file` set explicitly in LiteGate configuration take precedence over the kubeconfig.
- `api_server_url` may carry a path prefix, for example Rancher's `https://rancher.example.com/k8s/clusters/c-xxxxx`; the prefix is preserved.
- Connections to the API server use HTTP/2 by default: all watches share one connection, and pings detect dead connections. Set `disable_http2: true` when a proxy does not support HTTP/2.

---

## 3. Scenario 1: Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: shop
  namespace: shop
spec:
  ingressClassName: litegate
  tls:
    - hosts: [shop.example.com]
      secretName: shop-tls
  rules:
    - host: shop.example.com
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: shop-api
                port: {number: 80}
```

- Certificates come from `kubernetes.io/tls` Secrets and rotate automatically when the Secret changes; cert-manager can maintain them.
- A subset of ingress-nginx annotations is supported (ssl-redirect, proxy-body-size, backend-protocol, timeouts, CORS, rewrite-target and others). Compatibility is not complete; check each annotation when migrating.

## 4. Scenario 2: Gateway API

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: public
  namespace: litegate-system
spec:
  gatewayClassName: litegate
  listeners:
    - name: https
      port: 443
      protocol: HTTPS
      hostname: "*.example.com"
      tls:
        certificateRefs:
          - name: wildcard-example-com
      allowedRoutes:
        namespaces: {from: All}
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: shop-api
  namespace: shop
spec:
  parentRefs:
    - name: public
      namespace: litegate-system
  hostnames: [shop.example.com]
  rules:
    - matches:
        - path: {type: PathPrefix, value: /api}
      backendRefs:
        - name: shop-api
          port: 80
```

- Cross-namespace references to backends, certificates or mirror targets need a `ReferenceGrant` in the target namespace.
- For HTTPS backends, `BackendTLSPolicy` sets the CA and SNI. CAs must be core-group ConfigMaps or Secrets; an invalid policy rejects traffic and never downgrades to plaintext.
- Retries, rate limiting, circuit breaking, WAF, CORS and similar governance attach to routes through the custom `LiteGateTrafficPolicy` resource.
- Non-HTTP ports (TCPRoute/UDPRoute/TLSRoute) must also be opened in `service.extraPorts`.

When troubleshooting, read the resource status first: `kubectl get httproute shop-api -n shop -o yaml`, and check `Accepted` and `ResolvedRefs`.

---

## 5. Scenario 3: Gateway + web server (specific to LiteGate)

With Traefik, static frontend files usually need a separate nginx Pod behind the gateway. LiteGate serves this content directly from the gateway Pods:

| Capability | Native site syntax | Notes |
|---|---|---|
| Static site / SPA | `serve:` / `spa:` | Fallback to index for frontend routes, compression, cache headers, try_files |
| File download site | `list:` | Directory browsing with a page |
| Markdown docs site | `markdown:` | Renders a directory of .md files |
| WebDAV | `webdav:` | Shared read/write directory |
| Template / fixed response | `template` / `respond` | Maintenance pages, error fallbacks, JSON placeholders |
| Status page | `status:` | Status board based on real traffic |
| PHP | FastCGI | Connects to php-fpm |

The setup has three steps:

1. Put the **site YAML** in a ConfigMap, mount it into the Pod, and point `config.sites_dir` at the mount;
2. Deliver the **site files** into the Pod with one of the methods below;
3. Keep declaring dynamic APIs with Ingress/HTTPRoute. The same hostname merges automatically: certificates come from the Secret referenced by the Gateway/Ingress, and requests are matched by longest path.

### 5.1 Site YAML

```yaml
site: shop.example.com
https: false
routes:
  # Return JSON 503 while the API route is missing, instead of SPA HTML
  - name: api-unavailable
    priority: 1
    match: {path_prefix: /api}
    action:
      type: respond
      status: 503
      content_type: application/json
      body: '{"error":"api-route-unavailable"}'
/:
  spa: /frontend
```

`https: false` means the Kubernetes Secret provides the certificate and the site does not pin one itself. If the site YAML explicitly pins certificate files and they are unavailable, the site fails closed and does not fall back to the Gateway certificate.

### 5.2 Four ways to get frontend files into the Pod

| Method | Size | Release / rollback | Good for |
|---|---|---|---|
| Immutable ConfigMap | ≤ 1 MiB | Rename the ConfigMap and `helm upgrade`; `helm rollback` | Demos, very small pages |
| **Frontend image + initContainer** (recommended) | Unlimited (emptyDir) | Change the image tag and `helm upgrade`; `helm rollback` | Production SPAs, versioned with the image |
| Shared volume (RWX PVC, e.g. NFS) | Unlimited | Written externally, effective immediately | Download sites, WebDAV, content edited online |
| Serve KV mode | Unlimited | Update a KV pointer; each Pod downloads the ZIP, verifies SHA256 and switches atomically, no rollout | Frequent frontend releases decoupled from Pod releases |

**Recommended: frontend image + initContainer.** Frontend CI packages the build output into a small image, for example `FROM busybox` plus `COPY dist /dist`. When the Pod starts, an initContainer copies the output into an emptyDir, and LiteGate mounts it read-only and serves it:

```yaml
# values-web.yaml
config:
  sites_dir: /app/sites
frontendImage:
  repository: registry.example.com/shop/frontend
  tag: "1.4.2"
initContainers:
  - name: frontend
    image: "{{ .Values.frontendImage.repository }}:{{ .Values.frontendImage.tag }}"
    command: ["sh", "-c", "cp -R /dist/. /frontend/"]
    volumeMounts:
      - name: frontend
        mountPath: /frontend
extraVolumes:
  - name: frontend
    emptyDir: {sizeLimit: 512Mi}
  - name: sites
    configMap:
      name: shop-sites
extraVolumeMounts:
  - name: frontend
    mountPath: /frontend
    readOnly: true
  - name: sites
    mountPath: /app/sites
    readOnly: true
```

```bash
kubectl -n litegate-system create configmap shop-sites --from-file=shop.yaml
helm upgrade --install litegate ./deploy/helm/litegate -n litegate-system -f values-web.yaml
# Release a new frontend
helm upgrade litegate ./deploy/helm/litegate -n litegate-system -f values-web.yaml --set frontendImage.tag=1.4.3
```

`initContainers` is rendered through `tpl`, so it can reference your own `frontendImage` value. During a rolling update each new Pod gets the complete output of exactly one tag, so old and new files never mix. The full example is `deploy/helm/litegate/examples/webstack-image-values.yaml`; the ConfigMap variant is `webstack-values.yaml` in the same directory.

**Serve KV mode**: on Kubernetes, mount a writable emptyDir at `root`. `kv_provider` can be `litemesh`, `consul` or `http`; without litemesh, `http` can point at a URL that returns the version JSON. See [Serve KV mode](../../serve_kv_mode.md) for the fields.

### 5.3 Checks after a frontend release

Helm reporting ready does not mean every replica has the new files. After a release, also confirm: every ready Pod has the same file version; browsers actually load the new version; `/api` responds normally and, on failure, returns JSON 503 rather than HTML.

---

## 6. Replicas and high availability

- Every replica watches and serves traffic independently; Lease leader election only decides who writes status. The Lease lives in LiteGate's own namespace by default; expiry is judged by local observation, so clock skew between nodes does not matter; a leader that shuts down cleanly releases the Lease, so its successor does not wait for it to expire.
- Authentication sessions need a shared Redis and the same session key on every replica. Rate-limit and circuit-breaker counters live in each replica's memory and are not shared.
- The chart provides a PDB, topology spreading and graceful shutdown: 5 seconds unready, then 30 seconds to drain requests and connections, within a 45-second termination grace period.
- Chart upgrades do not update CRDs already installed from `crds/`; apply the new `LiteGateTrafficPolicy` CRD with `kubectl apply` first.

## 7. Common problems

| Symptom | Check |
|---|---|
| Pod never becomes ready | 403/404 in the logs: add RBAC or disable unused watches |
| Ingress has no effect | Does `ingressClassName` match `controller.ingressClass`? Are several installations in the cluster? |
| HTTPRoute `Accepted=False` | parentRefs, the Gateway's `allowedRoutes` and the listener hostname |
| `ResolvedRefs=False` | Does the backend Service/port exist? Is a ReferenceGrant missing for a cross-namespace reference? |
| Backend TLS errors | Does the BackendTLSPolicy CA ConfigMap/Secret exist and belong to the core group? Does the hostname match the certificate? |
| Frontend 404 or stale page | The `sites_dir` mount, the directory `spa` points at, the file version on every Pod |
| `/api` returns HTML | Add a JSON fallback route for `/api` (see 5.1) |

## 8. Version support

| Item | Validated | Notes |
|---|---|---|
| Kubernetes | K3s v1.34.5, v1.35.5, v1.36.5 | Other distributions (EKS/GKE/AKS/kind/OpenShift) not yet validated |
| Gateway API CRDs | v1.4.1 experimental | Validated with the official test suite: all HTTP/GRPC/TLS core tests pass (self-run, not submitted upstream) |
| Ingress | networking.k8s.io/v1 | |
| EndpointSlice | discovery.k8s.io/v1 | |
| Lease | coordination.k8s.io/v1 | |

For some Gateway API resources, the version is **chosen by API discovery**: the validated version is preferred; when the cluster no longer serves it, LiteGate switches to the next version it can decode and logs the version in use.

| Resource | Preferred (validated) | Fallback |
|---|---|---|
| BackendTLSPolicy | v1alpha3 | v1 |
| ReferenceGrant | v1beta1 | v1 |
| TLSRoute | v1alpha2 | v1alpha3, v1 |
| TCPRoute / UDPRoute | v1alpha2 | v1 |

GatewayClass, Gateway, HTTPRoute and GRPCRoute always use v1. If a resource's API returns 404, that feature is disabled and a Warn log names the resource and version. After upgrading Gateway API, check the logs for such messages.

## Further reading

- [Kubernetes deployment and usage (topic)](../../litegate_k8s_usage_guide.md)
- [Current Kubernetes capabilities and limits](../../litegate_kubernetes_capabilities.md)
- [Serve Action](../04-actions/serve.md) · [List](../04-actions/list.md) · [Markdown](../04-actions/markdown.md) · [WebDAV](../04-actions/webdav.md) · [Status](../04-actions/status.md) · [FastCGI](../../fastcgi_config.md)
- [Replica state and failure isolation](ha-state.md)
- [Helm chart notes](../../../../deploy/helm/litegate/README.md)
