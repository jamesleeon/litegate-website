# LiteGate Documentation Hub

LiteGate is a dynamic gateway: it unifies static sites, API reverse proxying, automatic certificates, service discovery, and identity-aware entry under one routing model.

> New here? **Start with the User Guide.** Read "Architecture & Design" and "Development" only when you need internals or want to extend the gateway.

> Looking for the Chinese docs? See [中文文档中心](../zh-cn/README.md).

---

## 📖 User Guide (Start Here)

The full manual is at **[User Guide Index](user/README.md)**, organized by usage stage (01 getting-started → 11 troubleshooting).

**Shortest path:**
- [Installation](user/01-getting-started/installation.md) → [Quick Start](user/01-getting-started/quick-start.md) → [Your First Site](user/01-getting-started/first-site.md)
- [CLI Reference](user/01-getting-started/cli-reference.md)

**By goal:**
- Host a static site + proxy an API: [Site Config](user/03-configuration/site-config.md) · [serve](user/04-actions/serve.md) · [proxy](user/04-actions/proxy.md) · [Serve KV / ZIP sync](serve_kv_mode.md)
- Serve PHP / PHP-FPM: [FastCGI Config](fastcgi_config.md)
- Automatic HTTPS: [Auto-Cert](user/06-certificates/auto-cert.md) · [On-Demand TLS](user/06-certificates/on-demand-cert.md) · [DDNS](user/06-certificates/ddns.md) · [Add a DNS provider](user/06-certificates/dns-providers.md)
- Service discovery: [Litemesh](user/07-discovery/litemesh.md) · [Consul](user/07-discovery/consul.md) · [Tag Architecture](user/02-concepts/tag-architecture.md) · [Service Tags Guide](user/03-configuration/tag-dsl.md) · [Tag Reference](user/03-configuration/tag-reference.md)
- SaaS entry controls: [Authentication](user/05-middleware/authentication.md) · [Remote Auth](user/05-middleware/remote-auth.md) · [WAF](user/05-middleware/waf.md)
- Observability: [Dashboard](user/08-observability/dashboard.md) · [Metrics](user/08-observability/metrics.md) · [Access Log](user/08-observability/access-log.md)
- Production: [Best Practices](user/10-deployment/production.md) · [systemd](user/10-deployment/systemd.md)

---

## 🧠 Architecture & Design

Understand LiteGate's tag-driven design and the request lifecycle.

- [Architecture White Paper](ARCHITECTURE_WHITE_PAPER.md)
- [L7 Execution Flow](l7_execution_flow.md): how a request traverses the gateway
- [Tag System Guide](tag_system_v6_guide.md)
- [Magic Ingress Design](magic_ingress_architecture.md): tag and forget
- [TLS / mTLS Security Architecture](tls_mtls_architecture.md)

---

## 🔌 Ecosystem & Integrations

- [Litemesh Integration](litemesh_integration.md)
- [Service Registration & Instant Online](service_registration_instant_online.md) · [Service Tagging Guide](service_registration_guide.md)
- [MCP Server Integration](litegate_mcp_integration.md) · [Capability Matrix](litegate_mcp_capability_matrix.md)
- [On-Demand TLS / mTLS](on_demand_tls.md)
- [Dynamic DNS & Multi-Node](dynamic-dns-multi-node.md)
- [Prometheus Dashboards](https://github.com/jamesleeon/LiteGate/blob/master/docs/en/prometheus)

---

## 🛠️ Development & Extensions

- [IDS Development Guide](ids_development_guide.md)
- [IDS Testing Guide](https://github.com/jamesleeon/LiteGate/blob/master/docs/en/ids_testing_guide.md)


- [NATS realtime subscriptions](user/04-actions/nats-sse.md): `type: nats` / `mode: subscribe`.
