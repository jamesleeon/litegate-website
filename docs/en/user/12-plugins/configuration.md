# Plugin Usage and Configuration Reference

Plugins compiled into LiteGate are used **exactly like built-in features**. Declare the plugin name in the global `config.yaml` or in `sites/*.yaml`, and the configuration loader recognizes it, parses it and runs pure configuration validation.

---

## Quick reference

| Extension point | Where it is configured | Key fields |
| :--- | :--- | :--- |
| **Action** | Route definitions in `sites/*.yaml` | `action.type: "<plugin_name>"`, with private parameters inline |
| **Middleware** | Site or route in `sites/*.yaml` | `middlewares: { <instance>: { type: "<plugin_name>", config: {...} } }`, referenced from the site or a route with `use: [<instance>]` |
| **LoadBalancer** | Route definitions in `sites/*.yaml` | `action.lb_policy: "<plugin_name>"` |
| **KV Provider** | Route definitions in `sites/*.yaml` | `action.kv_provider: "<plugin_name>"`, `action.kv_key: "..."` |
| **Ingress** | Global `config.yaml` | `ingress_plugins: [{ name: "...", type: "<plugin_name>", ... }]` |
| **Discovery** | Global `config.yaml` | `service_discovery.catalogs: [{ provider: "<plugin_name>", ... }]` |
| **DNS Provider** | Global `config.yaml` | `auto_cert.dns_providers: [{ name, type: "<plugin_name>", domains, config, ddns }]` |
| **IDS Provider** | Site or route in `sites/*.yaml` | `ids: { provider: "<plugin_name>", options: {...} }` |
| **Template Func** | HTML template sources | Call the registered function by name, such as `{{ maskPhone .User.Phone }}` |
| **Extension plugins** (Stream, Response Filter, exporters, cert issuer, upstream transport, config source) | Global `config.yaml` | `extension_plugins: [{ kind, name, type, config }]`, see section 8 |

---

## 1. Action plugins

Action plugins terminate the request and produce the response. Reference the plugin name with `action.type` in a route; other non-core fields are passed to the plugin's `ActionConfig` as private parameters:

```yaml
# sites/api-site.yaml
site: api.example.com

routes:
  # Case A: the NATS Action plugin compiled in by default
  - name: publish-order-event
    match:
      path: /v1/events/order
      method: [POST]
    action:
      type: nats                     # registered plugin name
      mode: jetstream_publish        # plugin-private parameters
      connection: default            # connections are defined in the plugin config file under plugins.nats.connections
      subject: orders.created

  # Case B: a custom AI gateway proxy plugin
  - name: llm-chat-proxy
    match:
      path_prefix: /v1/chat/completions
    action:
      type: llm_proxy                # custom Action plugin name
      model: "gpt-4o"
      token_budget_per_min: 100000
      upstream_endpoint: "https://api.openai.com"
```

For all NATS Action fields see the [NATS capability matrix](../../nats_capability_matrix.md).

> [!TIP]
> Action plugins should provide a `Validate` function. A missing required field or a wrong type in YAML is then rejected by `litegate -t` or at hot reload, instead of surfacing only when a request arrives.

---

## 2. Middleware plugins

Middleware plugins process the HTTP request chain. Define named middleware at site level, then reference them from the site or individual routes with `use`; a definition alone is not applied to every route:

```yaml
# sites/app.yaml
site: app.example.com

# 1. Site-level middleware definitions (for routes to reference)
middlewares:
  enterprise_trace:
    type: custom_trace_id
    config:
      header_name: "X-Enterprise-Trace-ID"
      generate_uuid: true
  finance_auth:
    type: custom_jwt_validator
    config:
      issuer: "https://auth.company.internal"
      audience: "finance-api"

routes:
  - name: sensitive-data
    match:
      path_prefix: /api/finance/
    # 2. Route-level middleware (only for this route)
    use: [enterprise_trace, finance_auth]
    proxy: ["10.0.10.50:8080"]
```

Middleware are inserted into the pipeline by the Descriptor the plugin declared at registration (Phase such as `Security`, `TrafficControl`, `RequestTransform`, plus Order); their order in YAML doesn't decide runtime order. See [Middleware pipeline](../05-middleware/pipeline.md).

---

## 3. Ingress plugins

Ingress plugins work at the shared-port entrypoint layer and can take over connections and requests **before site domain routing and URL normalization**. Typical uses are HTTP CONNECT forward proxies and special protocol multiplexing.

Declare them in the global `config.yaml`:

```yaml
# config.yaml
entrypoints:
  web:
    address: ":80"
  websecure:
    address: ":443"

ingress_plugins:
  - name: enterprise-forward-proxy
    type: forward_proxy            # plugin type (e.g. LiteGate's built-in forward proxy)
    entrypoints: [websecure]       # bound to these entrypoints
    config:
      probe_resistance: true       # anti-probing protection
      allowed_ports: [80, 443, 8443]
      allowed_destinations:
        - "*.internal.corp"
        - "api.github.com"
      username: ops_user
      password_env: LITEGATE_PROXY_PASSWORD  # proxy password from an environment variable
```

---

## 4. Discovery providers

If your services are registered in Nacos, Eureka, Zookeeper or an in-house CMDB, write a Discovery plugin and mount it under `service_discovery.catalogs` in `config.yaml`:

```yaml
# config.yaml
service_discovery:
  catalogs:
    - name: nacos-prod
      enabled: true
      provider: custom_nacos       # registered Discovery name
      config:
        sync_interval: "15s"       # polling interval implemented and parsed by the plugin
        server_addr: "10.0.1.10:8848"
        namespace_id: "production"
        group: "DEFAULT_GROUP"
```

Once mounted, LiteGate's dynamic routing and upstream health pools consume the discovered services and endpoints just as with the native Consul/Litemesh support.

---

## 5. DNS provider plugins (certificate DNS-01 and DDNS)

DNS provider plugins are referenced by `type` in `auto_cert.dns_providers`; `domains` decides which domains they handle. With `ddns` enabled on the same entry, the same plugin also handles DDNS synchronization (the plugin must declare the matching capability):

```yaml
# config.yaml
auto_cert:
  enabled: true
  email: "admin@example.com"
  dns_providers:
    - name: internal-dns
      type: my_internal_dns        # registered DNS provider name
      enabled: true
      domains: ["*.office.corp", "office.corp"]
      config:
        api_key: "env://INTERNAL_DNS_API_KEY"
        nameserver: "192.168.1.1"
      ddns:
        enabled: true
        sync_a: true
```

For developing and building DNS plugins see the [DNS provider plugin development guide](../../dns-provider-plugin-guide.md); for DDNS fields see [DDNS](../06-certificates/ddns.md).

---

## 6. IDS provider plugins

IDS plugins run a unified security decision after route matching and before the Action (enterprise signature checks, risk scoring, canary routing labels, ...):

```yaml
# sites/payment.yaml
site: payment.example.com

routes:
  - name: charge
    match:
      path: /v1/charge
    proxy: ["payment-backend:8080"]
    ids:
      provider: openapi-md5      # registered IDS name
      fail_policy: deny          # failure policy: deny (block) or allow (degrade and pass)
      options:
        secret_ref: orders       # the secret lives in plugin config providers.openapi-md5.secrets
        max_clock_skew: 5m
```

---

## 7. LoadBalancer and KV provider plugins

### A. LoadBalancer algorithms
```yaml
site: api.example.com
routes:
  - name: dynamic-lb-route
    match:
      path_prefix: /api
    action:
      type: proxy
      service_name: order-service
      lb_policy: least_latency   # registered custom LoadBalancer plugin name
```

### B. KV provider dynamic content
```yaml
site: www.example.com
routes:
  - name: dynamic-template-page
    match:
      path: /dashboard
    action:
      type: template
      kv_provider: redis_kv        # registered KV provider plugin name
      kv_key: "cms:pages:dashboard.html"
```

---

## 8. Global extension plugin bindings (extension_plugins)

LiteGate binds extension instances through one `extension_plugins` array in the global `config.yaml`. There are 8 `kind`s: `stream` (including Stream Filter and UDP Datagram), `response_filter`, `access_log_exporter`, `trace_exporter`, `metrics_exporter`, `cert_issuer`, `upstream_transport` and `config_source`. Adding, removing or changing a `config_source` requires a process restart; the others follow configuration reloads. The example shows several of them:

```yaml
# config.yaml
extension_plugins:
  # 1. L4 TCP/UDP transport plugin
  - kind: stream
    name: redis_guard
    type: redis_readonly          # registered plugin name (RegisterStream)
    config:
      allowed_commands: [GET, MGET, PING]

  # 2. Response stream / body transform (masking, injection)
  - kind: response_filter
    name: pii_masker
    type: pii_filter              # registered plugin name (RegisterResponseFilter)
    config:
      mask_idcard: true

  # 3. Asynchronous log/trace export (to Kafka/Loki/OTLP)
  - kind: access_log_exporter
    name: kafka_audit
    type: kafka_producer          # registered plugin name (RegisterAccessLogExporter)
    config:
      brokers: ["10.0.0.1:9092"]
      topic: "gateway-access-log"

  # 4. Private CA issuance (Vault / private PKI)
  - kind: cert_issuer
    name: internal_vault
    type: vault_ca                # registered plugin name (RegisterCertIssuer)
    config:
      vault_addr: "https://vault.internal:8200"

  # 5. Custom upstream transport (mutual TLS / connection pools)
  - kind: upstream_transport
    name: enterprise_mtls
    type: mtls_transport          # registered plugin name (RegisterUpstreamTransport)
    config:
      client_cert: "/certs/client.pem"
      client_key: "/certs/client.key"
```

### Referencing extensions from routes and Streams

```yaml
# sites/secure-api.yaml
# 1. A site route referencing a Response Filter and an Upstream Transport:
site: api.example.com
routes:
  - name: secure-api
    match: { path_prefix: /api/ }
    action:
      type: proxy
      upstream: ["internal-service:8080"]
      upstream_transport: enterprise_mtls  # name from extension_plugins
      response_filters: [pii_masker]       # name from extension_plugins
```

**L4 Stream configuration**:

```yaml
# streams/redis-proxy.yaml
# 2. An L4 Stream referencing a Stream plugin:
name: redis-proxy
port: 6379
protocol: tcp
plugin_handler: redis_guard                # name from extension_plugins
# plugin_filters: [conn_audit]             # optional: Stream Filters, run before the handler
```

**Global certificate configuration**:

```yaml
# config.yaml
# 3. Auto cert issued through a private CA:
auto_cert:
  issuer: internal_vault                   # name from extension_plugins
```

---

## Common configuration errors

1. **`has unknown action type: xxx`** (for Ingress plugins `ingress plugin "xxx" is not compiled into this binary`, for IDS `ids.provider "xxx" is not registered`)
   - **Cause**: the plugin name referenced in YAML isn't compiled into this binary, or the spelling/case differs.
   - **Check**: run `litegate plugins list` to see supported names; check `cmd/litegate/plugins.go` or your `litegate build` options.
2. **`unsupported plugin manifest kind "xxx"`**
   - **Cause**: the Kind in the plugin's Manifest is invalid. Valid kinds: `action`, `middleware`, `load_balancer`, `kv`, `dns`, `ids`, `discovery`, `ingress`, `template_func`, `stream`, `response_filter`, `access_log_exporter`, `trace_exporter`, `metrics_exporter`, `cert_issuer`, `upstream_transport`, `config_source`.
3. **Load-time validation error: `config validation failed`**
   - **Cause**: the plugin's `Validate` found a missing required field, an out-of-range value or invalid configuration. Fix the YAML from the specific error printed in the terminal.
