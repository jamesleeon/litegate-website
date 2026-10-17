# LiteGate documentation

LiteGate is a single-binary HTTP / TCP gateway. It sits in front of your websites, APIs and private services, accepts traffic, sets up HTTPS automatically and forwards requests by rule. This documentation describes how the current code is used.

[中文](../zh-cn/README.md) · [English](../en/README.md)

You do not need to read everything. Follow four steps: **get it running → find your scenario → look things up when needed → read the deployment notes before going live**.

---

## Step 1: get it running (about 5 minutes)

1. [Installation](user/01-getting-started/installation.md): binary download, Docker or a source build
2. [Quick start](user/01-getting-started/quick-start.md): start with no configuration and write your first site
3. [Basics: get a site running](user/cookbook/01-basics.md): reverse proxy, static site, HTTPS and load balancing; every configuration is verified by automated tests and can be copied as is

---

## Step 2: configure your scenario

Pick the scenario closest to your needs, adapt the "Start" pages to your own domains and backends, and read "More" when you need it.

### Publish a website or frontend app

- Start: [Split by path, rewrite, redirect](user/cookbook/02-paths.md)
- More: [Serve: static files and SPA](user/04-actions/serve.md) · [Markdown documentation sites](user/04-actions/markdown.md) · [Directory browsing](user/04-actions/list.md) · [WebDAV](user/04-actions/webdav.md) · [Server-side templates](user/04-actions/template.md) · [PHP / FastCGI](fastcgi_config.md) · [Frontend bundles via KV](serve_kv_mode.md)

### API gateway for several backends

- Start: [CORS, headers and rate limit recipes](user/cookbook/03-governance.md) · [Proxy action](user/04-actions/proxy.md)
- More: [Named services and configuration layers](user/03-configuration/services.md) · [Traffic and upstream governance](user/05-middleware/traffic-and-upstream.md) · [Circuit breaker](user/09-advanced/circuit-breaker.md) · [Proxy cache](user/05-middleware/proxy-cache.md) · [WebSocket](user/09-advanced/websocket.md) · [Match by method and header](user/cookbook/06-matchers.md) · [Two-layer routing](user/09-advanced/two-layer-routing.md)

### Routes that follow your services (service discovery)

- Start: [Service discovery overview](user/07-discovery/overview.md) · [Service tag guide](user/03-configuration/tag-dsl.md) · [Frontend plus discovered backends](user/cookbook/05-discovery.md)
- More: [Service registration and LiteGate tags](service_registration_guide.md) · [Magic Ingress](user/09-advanced/magic-ingress.md) · [Consul](user/07-discovery/consul.md) · [Litemesh](user/07-discovery/litemesh.md) · [Litemesh mTLS](user/07-discovery/litemesh-mtls.md) · [Nomad](user/07-discovery/nomad.md)
- Docker: [Docker Provider deployment and configuration](litegate_docker_provider_deployment_guide.md) · [Docker catalog identity and transports](docker_catalog_identity_and_transport.md) · [Docker Provider test guide](docker_provider_testing_guide.md)
- Kubernetes: [Kubernetes deployment guide](user/10-deployment/kubernetes.md) · [Kubernetes deployment and usage](litegate_k8s_usage_guide.md) · [Current Kubernetes capabilities and limits](litegate_kubernetes_capabilities.md)

### Publish private services / reach private assets remotely

- Start: [Connect configuration](user/09-advanced/connect.md) · [Connect scenarios](user/09-advanced/connect-scenarios.md) · [Accessing database TCP assets](database-proxy-solution.md)
- More: [Forward or Connect](user/09-advanced/forward-and-connect.md) · [Forward tunnels and HTTP forward proxies](forward-vs-forward-proxy.md) · [Publish an HTTP service with the CLI](user/09-advanced/connect-cli-http.md) · [Ingress entrypoint plugins](ingress-plugin-guide.md)

### Certificates and HTTPS

- Start: [Auto-Cert](user/06-certificates/auto-cert.md) · [Certificate issuance guide](user/06-certificates/certificate-application-guide.md)
- More: [DNS providers](user/06-certificates/dns-providers.md) · [Local CA](user/06-certificates/local-ca.md) · [On-demand certificates](user/06-certificates/on-demand-cert.md) · [On-Demand TLS (SaaS)](on_demand_tls.md) · [Dynamic DNS](user/06-certificates/ddns.md) · [Internal DNS on multiple nodes](dynamic-dns-multi-node.md) · [ECH](user/06-certificates/ech.md) · [LAN CA and mTLS](user/06-certificates/lan-ca-and-mtls.md) · [Connect CSR delegation](user/06-certificates/connect-csr-delegation.md) · [CredKeeper](user/06-certificates/credkeeper.md) · [Sealed Secrets](user/06-certificates/sealed-secrets.md)

### Login and protection

- Start: [Authentication overview](user/05-middleware/authentication.md) · [Basic Auth](user/05-middleware/basic-auth.md) · [IP restriction](user/05-middleware/ip-restriction.md) · [Rate limit](user/05-middleware/rate-limit.md)
- More: [OIDC / OAuth2](user/05-middleware/oidc.md) · [authentik example](user/05-middleware/authentik.md) · [Single OAuth callback](user/09-advanced/oauth-single-callback.md) · [Forward Auth](user/05-middleware/forward-auth.md) · [Remote Auth](user/05-middleware/remote-auth.md) · [WAF](user/05-middleware/waf.md) · [Scan protection](user/05-middleware/scan-protection.md) · [CSRF](user/05-middleware/csrf.md) · [CORS](user/05-middleware/cors.md) · [Bandwidth](user/05-middleware/bandwidth.md) · [Compression](user/05-middleware/compression.md)

### Real-time notifications

- Start: [Event notifications](user/09-advanced/event-notification.md) · [NATS integration deployment](nats_deployment_guide.md)
- More: [JWT integration and limits](user/09-advanced/notify-jwt-integration.md) · [Durable events](user/04-actions/nats-events.md) · [NATS SSE](user/04-actions/nats-sse.md) · [NATS capabilities and responsibility boundaries](nats_capability_matrix.md)

### TCP / UDP and sharing port 443

- Start: [L4 guide](user/03-configuration/l4-guide.md)
- More: [HTTPS and L4 TCP on one port 443](user/09-advanced/shared-443-l4-stream.md) · [SNI routing recipes](user/09-advanced/sni-routing-recipes.md)

### Multi-tenant SaaS (IDS)

- Start: [IDS overview](ids-overview.md) · [IDS business decision recipes](ids-recipes.md)
- More: [IDS Provider development and deployment](ids-provider-plugin-guide.md) · [IDS plugin constraints and troubleshooting](ids-plugin-caveats.md) · [IDS Provider acceptance guide](ids_testing_guide.md) · [Choosing Go or WASM](ids-go-vs-wasm.md) · [Experimental IDS WASM](ids-wasm-plugin-guide.md) · [OpenAPI MD5 compatibility Provider](openapi-md5-ids-plugin.md) · [IDS request governance](user/05-middleware/ids-governance.md)

When something goes wrong, start with [Common errors](user/cookbook/04-pitfalls.md). More recipes are in the [Cookbook](user/cookbook/README.md).

---

## Step 3: concepts and reference

- Concepts: [Sites and routes](user/02-concepts/sites-and-routes.md) · [Actions](user/02-concepts/actions.md) · [Routing priority](user/02-concepts/routing-priority.md) · [Unified entry model](user/02-concepts/unified-entry-model.md) · [Service tag architecture](user/02-concepts/tag-architecture.md) · [How discovery works](user/02-concepts/discovery.md)
- Configuration: [Site YAML structure and fields](user/03-configuration/site-yaml-v2-concepts.md) · [Site configuration reference](user/03-configuration/site-config.md) · [Global `config.yaml`](user/03-configuration/global-config.md) · [Configuration structure and best practices](user/03-configuration/config-structure.md) · [Entrypoints](user/03-configuration/entrypoints.md) · [Stream configuration](user/03-configuration/stream-config.md) · [Rewrite](user/03-configuration/rewrite.md) · [Upstream DNS](user/03-configuration/upstream-dns.md) · [Service tag reference](user/03-configuration/tag-reference.md) · [Management endpoints](user/03-configuration/api.md)
- Middleware: [Pipeline order](user/05-middleware/pipeline.md) · [Path and redirect](user/05-middleware/path-and-redirect.md)
- Other actions: [Respond](user/04-actions/respond.md) · [Redirect](user/04-actions/redirect.md) · [Status dashboard](user/04-actions/status.md)
- Command line: [CLI reference](user/01-getting-started/cli-reference.md)
- Full table of contents: [User guide](user/README.md)

---

## Step 4: production and extensions

- Deployment: [Production](user/10-deployment/production.md) · [systemd](user/10-deployment/systemd.md) · [Replica state](user/10-deployment/ha-state.md) · [Benchmarking](user/10-deployment/benchmarking.md) · [Configuration release control](release_control_guide.md)
- Observability: [Dashboard](user/08-observability/dashboard.md) · [Dashboard API](user/08-observability/dashboard-api.md) · [Metrics](user/08-observability/metrics.md) · [Access log](user/08-observability/access-log.md) · [Trace ID](user/08-observability/trace-id.md) · [Official Grafana dashboard](https://github.com/jamesleeon/LiteGate/tree/master/deploy/grafana) · [MCP capability matrix](litegate_mcp_capability_matrix.md)
- Troubleshooting: [Debugging](user/11-troubleshooting/debugging.md) · [FAQ](user/11-troubleshooting/faq.md)
- Extensions: [Plugins](user/12-plugins/README.md) · [Plugin authoring](user/12-plugins/authoring-guide.md) · [Builds and CLI](user/12-plugins/build-and-cli.md) · [Plugin configuration](user/12-plugins/configuration.md) · [Discovery plugin (Nomad example)](discovery-provider-plugin-guide.md) · [DNS Provider plugins](dns-provider-plugin-guide.md)
- Source builds: [Build from source](user/01-getting-started/build.md) · [Build environment setup](user/01-getting-started/build-environment.md)

See [documentation publication notes](../README.md) for maintenance rules.
