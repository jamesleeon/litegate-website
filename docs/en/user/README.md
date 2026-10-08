# LiteGate User Guide

This section is for users and operators, focused on three core questions:

- How do I get LiteGate up and running?
- How do I connect websites and backend services?
- How do I run it stably in production?

---

## Suggested Reading Order

### 1. Getting Started
- [Installation](./01-getting-started/installation.md)
- [Quick Start](./01-getting-started/quick-start.md)
- [Your First Site](./01-getting-started/first-site.md)
- [CLI Reference](./01-getting-started/cli-reference.md)
- [Build from Source](./01-getting-started/build.md)

### 2. Core Concepts
- [Sites and Routes](./02-concepts/sites-and-routes.md)
- [Actions](./02-concepts/actions.md)
- [Routing Priority](./02-concepts/routing-priority.md)
- [Service Discovery](./02-concepts/discovery.md)
- [Unified Entry Model](./02-concepts/unified-entry-model.md)
- [Service Tag Architecture](./02-concepts/tag-architecture.md)

### 3. Configuration
- [Site YAML V2: Structure and Core Concepts](./03-configuration/site-yaml-v2-concepts.md): understanding addresses, routes, actions, inheritance, reuse, and Hybrid merging with service tags
- [Configuration Structure and Best Practices](./03-configuration/config-structure.md): read this first for the overall structure and recommended organization
- [Global Configuration](./03-configuration/global-config.md)
- [Site Configuration](./03-configuration/site-config.md)
- [L4 site syntax and use cases](./03-configuration/l4-guide.md)
- [Stream Configuration](./03-configuration/stream-config.md)
- [Control API](./03-configuration/api.md)
- [Service Tags Guide](./03-configuration/tag-dsl.md)
- [Service Tag Reference](./03-configuration/tag-reference.md)
- [Named Services and Configuration Layers](./03-configuration/services.md): `services` syntax, where a capability belongs, upgrade notes

### 4. Actions
- [Proxy](./04-actions/proxy.md)
- [Serve](./04-actions/serve.md)
- [WebDAV](./04-actions/webdav.md)
- [Markdown](./04-actions/markdown.md)
- [Template](./04-actions/template.md)
- [Status](./04-actions/status.md)
- [Redirect](./04-actions/redirect.md)
- [Respond](./04-actions/respond.md)
- [List](./04-actions/list.md)

### 5. Middleware & Security
- [Authentication](./05-middleware/authentication.md)
- [OIDC](./05-middleware/oidc.md)
- [Remote Auth](./05-middleware/remote-auth.md)
- [WAF](./05-middleware/waf.md)
- [Rate Limit & Concurrency Limit](./05-middleware/rate-limit.md)
- [Proxy Cache](./05-middleware/proxy-cache.md)
- [IP Restriction](./05-middleware/ip-restriction.md)
- [CORS](./05-middleware/cors.md)
- [Compression](./05-middleware/compression.md)

### 6. Certificates & Discovery
- [Auto-Cert](./06-certificates/auto-cert.md)
- [Encrypted ClientHello (ECH)](./06-certificates/ech.md)
- [On-Demand TLS](./06-certificates/on-demand-cert.md)
- [Local CA](./06-certificates/local-ca.md)
- [DDNS](./06-certificates/ddns.md)
- [Discovery Sources Overview](./07-discovery/overview.md)
- [Litemesh Discovery](./07-discovery/litemesh.md)
- [Litemesh mTLS](./07-discovery/litemesh-mtls.md)
- [Consul Discovery](./07-discovery/consul.md)

### 7. Observability & Operations
- [Dashboard](./08-observability/dashboard.md)
- [Dashboard API](./08-observability/dashboard-api.md)
- [Metrics](./08-observability/metrics.md)
- [Access Log](./08-observability/access-log.md)
- [Trace ID](./08-observability/trace-id.md)

### 8. Advanced Capabilities
- [Circuit Breaker](./09-advanced/circuit-breaker.md)
- [Magic Ingress](./09-advanced/magic-ingress.md)
- [WebSocket](./09-advanced/websocket.md)
- [LiteGate Connect](./09-advanced/connect.md)
- [Publish an HTTP Service with the CLI](./09-advanced/connect-cli-http.md)

### 9. Production Deployment
- [Production Best Practices](./10-deployment/production.md)
- [Systemd Service](./10-deployment/systemd.md)

### 10. Diagnostics & Troubleshooting
- [Debugging Guide](./11-troubleshooting/debugging.md)
- [FAQ](./11-troubleshooting/faq.md)

---

## Where Should I Start?

- **Host a static site and proxy an API**:
  [Quick Start](./01-getting-started/quick-start.md) → [Site Configuration](./03-configuration/site-config.md) → [Serve Action](./04-actions/serve.md) → [Proxy Action](./04-actions/proxy.md)
- **Configure automatic HTTPS / SSL**:
  [Auto-Cert](./06-certificates/auto-cert.md)
- **Enable dynamic service discovery**:
  [Discovery Sources Overview](./07-discovery/overview.md) → [Service Tags Guide](./03-configuration/tag-dsl.md) → [Litemesh Discovery](./07-discovery/litemesh.md)
- **Set up SaaS entrance controls**:
  [Authentication](./05-middleware/authentication.md) → [Remote Auth](./05-middleware/remote-auth.md) → [WAF](./05-middleware/waf.md)
- **Build resilient routing and zero-config mesh**:
  [Circuit Breaker](./09-advanced/circuit-breaker.md) → [Magic Ingress](./09-advanced/magic-ingress.md)


- [NATS realtime subscriptions](04-actions/nats-sse.md): `type: nats` / `mode: subscribe`.
