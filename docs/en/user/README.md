# LiteGate user guide

Start with installation, quick start and your first site, then use the task references. Both editions use the same topics and paths.

[中文](../../zh-cn/user/README.md) · [English](../../en/user/README.md)

## Getting started

- [Build Guide (Build from Source)](01-getting-started/build.md)
- [Build environment setup](01-getting-started/build-environment.md)
- [CLI Reference](01-getting-started/cli-reference.md)
- [First Site Configuration Example](01-getting-started/first-site.md)
- [Installation Guide](01-getting-started/installation.md)
- [Quick Start](01-getting-started/quick-start.md)

## Core concepts

- [Actions Detail: Request Processing Model](02-concepts/actions.md)
- [Service Discovery Integration Principles](02-concepts/discovery.md)
- [Routing Priority](02-concepts/routing-priority.md)
- [Understanding Sites and Routes](02-concepts/sites-and-routes.md)
- [LiteGate Service Tag Architecture](02-concepts/tag-architecture.md)
- [Unified Entry Model](02-concepts/unified-entry-model.md)

## Configuration

- [Control API Reference](03-configuration/api.md)
- [Configuration Structure and Best Practices](03-configuration/config-structure.md)
- [Entrypoints](03-configuration/entrypoints.md)
- [Gateway configuration reference (`config.yaml`)](03-configuration/global-config.md)
- [L4 Stream Guide](03-configuration/l4-guide.md)
- [Rewrite: paths and query parameters](03-configuration/rewrite.md)
- [Named Services and Configuration Layers](03-configuration/services.md)
- [Site configuration reference (`sites/*.yaml`)](03-configuration/site-config.md)
- [Site YAML V2: Structure and Core Concepts](03-configuration/site-yaml-v2-concepts.md)
- [Stream Configuration Reference (Layer 4 Proxy)](03-configuration/stream-config.md)
- [LiteGate Service Tags Guide](03-configuration/tag-dsl.md)
- [LiteGate Service Tag Reference](03-configuration/tag-reference.md)
- [Upstream DNS](03-configuration/upstream-dns.md)

## Actions

- [List Action (Directory Browsing)](04-actions/list.md)
- [Markdown Action (Document Rendering Service)](04-actions/markdown.md)
- [Durable events (persistence, offline replay and application ACK)](04-actions/nats-events.md)
- [NATS live event subscriptions](04-actions/nats-sse.md)
- [Proxy Action (Reverse Proxy)](04-actions/proxy.md)
- [Redirect Action (HTTP Redirection)](04-actions/redirect.md)
- [Respond Action (Raw Responses)](04-actions/respond.md)
- [Serve Action (Static File Serving)](04-actions/serve.md)
- [Status Action (System Status Dashboard)](04-actions/status.md)
- [Template Action (Server-Side Templates)](04-actions/template.md)
- [WebDAV Action (File Management Service)](04-actions/webdav.md)

## Middleware and security

- [Authentication Overview](05-middleware/authentication.md)
- [authentik OIDC configuration example](05-middleware/authentik.md)
- [HTTP Basic Auth](05-middleware/basic-auth.md)
- [Compression (Smart Compression)](05-middleware/compression.md)
- [CORS Middleware (Cross-Origin Resource Sharing)](05-middleware/cors.md)
- [Forward Auth external authorization](05-middleware/forward-auth.md)
- [IDS request governance](05-middleware/ids-governance.md)
- [IP Restriction (Access Control List)](05-middleware/ip-restriction.md)
- [OIDC / OAuth2 Authentication Guide](05-middleware/oidc.md)
- [Path transformations and redirects](05-middleware/path-and-redirect.md)
- [Middleware pipeline and chains](05-middleware/pipeline.md)
- [Proxy Cache (Reverse-Proxy Content Cache)](05-middleware/proxy-cache.md)
- [Rate limiting (V2 configuration)](05-middleware/rate-limit.md)
- [Remote Auth (OIDC / OAuth2 SSO)](05-middleware/remote-auth.md)
- [Scan protection and governance rules](05-middleware/scan-protection.md)
- [Traffic control and upstream policies](05-middleware/traffic-and-upstream.md)
- [WAF (Web Application Firewall)](05-middleware/waf.md)

## Certificates

- [Auto-Cert (Automated Certificate Management)](06-certificates/auto-cert.md)
- [Certificate issuance methods and configuration](06-certificates/certificate-application-guide.md)
- [Connect CSR certificate delegation](06-certificates/connect-csr-delegation.md)
- [CredKeeper centralized credential storage](06-certificates/credkeeper.md)
- [DDNS (Dynamic DNS)](06-certificates/ddns.md)
- [Add a DNS provider](06-certificates/dns-providers.md)
- [Encrypted ClientHello (ECH)](06-certificates/ech.md)
- [Local CA (Self-Signed, Self-Trusted)](06-certificates/local-ca.md)
- [LAN CAs and service mTLS](06-certificates/lan-ca-and-mtls.md)
- [On-Demand TLS (Dynamic SSL Generation)](06-certificates/on-demand-cert.md)
- [Sealed secrets](06-certificates/sealed-secrets.md)

## Discovery

- [Consul Service Discovery](07-discovery/consul.md)
- [Litemesh mTLS Integration Guide](07-discovery/litemesh-mtls.md)
- [Litemesh Service Discovery](07-discovery/litemesh.md)
- [Service Discovery Sources Overview](07-discovery/overview.md)

## Observability

- [Access Log](08-observability/access-log.md)
- [Dashboard REST API Reference](08-observability/dashboard-api.md)
- [Web Dashboard](08-observability/dashboard.md)
- [Prometheus Metrics](08-observability/metrics.md)
- [Trace ID (Distributed Tracing)](08-observability/trace-id.md)

## Advanced scenarios

- [Circuit breaking (V2 configuration)](09-advanced/circuit-breaker.md)
- [Publish an HTTP Service with the CLI](09-advanced/connect-cli-http.md)
- [Connect scenarios and deployment responsibilities](09-advanced/connect-scenarios.md)
- [LiteGate Connect Configuration and Rollout](09-advanced/connect.md)
- [Event notifications and offline delivery](09-advanced/event-notification.md)
- [Forward and Connect](09-advanced/forward-and-connect.md)
- [Magic Ingress (Zero-Configuration Routing)](09-advanced/magic-ingress.md)
- [Notify and application JWT integration](09-advanced/notify-jwt-integration.md)
- [Routing a single OAuth callback](09-advanced/oauth-single-callback.md)
- [Shared port 443: HTTPS and L4 streams](09-advanced/shared-443-l4-stream.md)
- [SNI routing recipes](09-advanced/sni-routing-recipes.md)
- [Selecting upstreams and rewriting paths](09-advanced/two-layer-routing.md)
- [WebSocket Proxying](09-advanced/websocket.md)

## Deployment

- [Benchmarking and performance attribution](10-deployment/benchmarking.md)
- [Replica state and failure isolation](10-deployment/ha-state.md)
- [Production Deployment Best Practices](10-deployment/production.md)
- [Systemd Deployment Guide (Linux)](10-deployment/systemd.md)

## Troubleshooting

- [Troubleshooting & Debugging Guide](11-troubleshooting/debugging.md)
- [Frequently Asked Questions (FAQ)](11-troubleshooting/faq.md)

## Plugins

- [Plugin authoring contracts](12-plugins/authoring-guide.md)
- [Plugin builds and CLI](12-plugins/build-and-cli.md)
- [Plugin configuration locations and validation](12-plugins/configuration.md)
- [Plugin system overview](12-plugins/README.md)

## Cookbook

- [Basics: static sites and APIs](cookbook/01-basics.md)
- [Paths: matching and rewriting](cookbook/02-paths.md)
- [Governance: entry limits and backend policies](cookbook/03-governance.md)
- [Common configuration pitfalls](cookbook/04-pitfalls.md)
- [Discovery: Services and registration tags](cookbook/05-discovery.md)
- [Named request matchers](cookbook/06-matchers.md)
- [Configuration cookbook](cookbook/README.md)


- [Large transfers, bandwidth limits and request body protection](05-middleware/bandwidth.md)
