# Unified Entry Model

A core feature of LiteGate is that the final public-facing entrypoint it provides is not necessarily defined by a single static YAML file alone.

In many cases, an entrance under a specific domain is formed by combining two parts:

- **Static Site Configuration**: Declared by `sites/*.yaml` or `sites/*.lite.yaml`.
- **Dynamic Service Entrance**: Generated in real-time by service registrations, service discovery, tags, or Magic Ingress.

These two parts are seamlessly merged inside LiteGate to represent a single unified entrypoint layer.

---

## 1. What is the Static Part?

The static configuration is typically used to declare:

- Frontend site root directories
- SPA routing fallbacks
- Hardcoded `/api` routes
- Stable entrance rules like authentication, middlewares, and certificates

The most common example is:

```yaml
domain: a.example.com
routes:
  - match:
      path_prefix: /
    action:
      type: serve
      root: "/srv/www/app"
      spa: true
```

This part represents the "frontend entrance" or "stable traffic contracts."

---

## 2. What is the Dynamic Part?

The dynamic configuration originates from discovery sources such as Litemesh, LiteDeploy, Docker, Consul, or a blocking-query Discovery aggregation layer.

A microservice can declare its routing intent through named resources, such as:

- `litegate.http.host` (the shortcut, when one domain is enough)
- `litegate.entrypoints.<name>.*`
- `litegate.http.routers.<name>.*`
- `litegate.http.services.<name>.*`
- `litegate.http.middlewares.<name>.*`

LiteGate reads these dynamic attributes and generates routes, instance selection and proxy governance at runtime. A new listening port declared by tags must be allowed in `service_discovery.tag_entrypoints.allowed_ports`.

This part represents the "backend service entry" or "registration is instant routing."

---

## 3. How They Merge

LiteGate does not force you to choose between "static mode" and "dynamic mode."

In real-world production environments, a highly common scenario is:

- Frontend static web pages are hosted via static YAML configurations.
- Backend APIs are automatically integrated via dynamic service discovery.
- Together, they form a complete, unified site under the same domain name.

For instance:

- `https://a.example.com/console` maps to the static frontend site.
- `https://a.example.com/api/...` maps to registered backend microservices.

To clients, they see a seamless, complete website.  
Internally, LiteGate maintains a merged mapping of the "static site declaration + dynamic service routes."

---

## 4. Workable Even Without a Domain Name

This model is not restricted to public domains.

If a service registers with:

```text
litegate.entrypoints.api-9090.address=:9090
litegate.http.routers.api.entrypoints=api-9090
litegate.http.routers.api.match.path_prefix=/
```

Because the Router has no Host condition, it accepts any Host on port 9090:

```text
http://<gateway-ip>:9090/
```

This means LiteGate can gracefully act as a private microservice entrance without domain names:

- Multiple Routers can share one EntryPoint.
- Each Router rule explicitly distinguishes its path.
- Load balancing is automatically performed across multiple healthy instances under the same service.

---

## 5. What the MCP Server Sees

The Model Context Protocol (MCP) allows AI coders to configure and govern LiteGate cleanly:

- Read site configurations.
- Read service lists and service details.
- Generate and save configs.
- Validate configuration syntax.
- Hot-reload the gateway.
- Verify sites online.
- Look up active routes.
- Monitor `recent requests` and `recent errors`.

Thus, AI models are fully capable of completing the full loop of "inspecting environment ➡️ generating config ➡️ applying ➡️ verifying ➡️ debugging."

---

## 6. What MCP Needs Help Explaining

While the MCP server sees:

- Static site segments.
- Dynamic service segments.
- Final routing resolution.

It might not always automatically explain to users:

- Whether a specific endpoint belongs to static YAML files or dynamic service discovery.
- How they are dynamically merged into a unified site at runtime.

Therefore, human operators still need to keep this core model in mind:

> LiteGate's final entrance might not be written in a single file; it is composed of static declarations and dynamic service discoveries working together.

---

## 7. Recommended Mindset

If you think of LiteGate only as a "reverse proxy," you will easily get confused by these options.  
However, if you think of LiteGate as a **"Unified Entrypoint Layer"**, this design becomes completely natural.

You can summarize it in one sentence:

> Static YAML declares the stable entrypoint, dynamic discovery lets backend services grow naturally, and LiteGate converges them into a complete website at runtime.

---

## Next Steps

We recommend continuing your reading:

- [Sites and Routes](./sites-and-routes.md)
- [Discovery](./discovery.md)
- [Routing Priority](./routing-priority.md)
