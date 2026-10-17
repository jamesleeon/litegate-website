# LiteGate MCP Capability Matrix

LiteGate ships a built-in MCP (Model Context Protocol) server so AI assistants can read configuration, generate and validate sites, save and reload, publish and roll back releases, and troubleshoot. This page lists every tool currently exposed.

## Connecting

LiteGate offers two transports with the same tool list. They differ in which process the AI talks to:

| | stdio | SSE |
|---|---|---|
| How it starts | The AI client runs `litegate mcp -config <path>`, a separate process | The running gateway serves `/sse` on `mcp.port` |
| Best for | Writing, validating and saving configuration locally | Managing a running gateway, remote troubleshooting |
| Read/write, validation, site creation, release and rollback | Yes | Yes |
| Runtime diagnostics (`get_recent_requests`, `get_recent_errors`, `get_gateway_status`, `list_active_tunnels`, `get_connect_status`, ...) | Reflect only the MCP process itself, not gateway traffic | Reflect the running gateway |
| After saving | Files are written; the running gateway hot-reloads them | Files are written and the current gateway reloads |

### stdio: local AI clients

All logs go to stderr and stdout carries only JSON-RPC. If `config.yaml` does not exist, a default configuration and directories are generated.

Relative paths such as `sites_dir`, `streams_dir` and `certs_dir` resolve against the **process working directory**, and AI clients usually do not start the process in the directory that holds `config.yaml`. Use absolute paths for these directories in `config.yaml`, or have the client start LiteGate in the configuration directory.

Claude Code:

```bash
claude mcp add litegate -- litegate mcp -config /etc/litegate/config.yaml
```

Cursor (`.cursor/mcp.json`), Claude Desktop and other clients configured with JSON:

```json
{
  "mcpServers": {
    "litegate": {
      "command": "litegate",
      "args": ["mcp", "-config", "/etc/litegate/config.yaml"]
    }
  }
}
```

### SSE: connect to a running gateway

Enable it in `config.yaml`. After the gateway starts or reloads it listens on `mcp.port`; the endpoint is `/sse`, and the server tells the client its `/message` endpoint during the handshake:

```yaml
mcp:
  enabled: true
  port: 9900                            # default 8080; must not clash with http.port, the dashboard or entrypoints
  token: "REPLACE_WITH_STRONG_TOKEN"    # clients send Authorization: Bearer <token>
  public_url: ""                        # public URL when exposed through a reverse proxy, e.g. https://ops.example.com/mcp
```

An empty `token` disables authentication, so always set one. `litegate -secret` prints a random value.

Claude Code:

```bash
claude mcp add --transport sse litegate http://127.0.0.1:9900/sse --header "Authorization: Bearer <token>"
```

Clients configured with JSON:

```json
{
  "mcpServers": {
    "litegate": {
      "url": "http://127.0.0.1:9900/sse",
      "headers": { "Authorization": "Bearer <token>" }
    }
  }
}
```

### Security

MCP tools can change and delete configuration and write token files. Keep the SSE port on localhost or a private network and never expose it directly to the Internet. For remote use, put it behind an authenticated entrypoint and enable [release control](release_control_guide.md) so the AI's changes land in a draft that you confirm before publishing.

### Putting the AI to work

Once connected, describe what you need in plain language, for example:

- "Forward /api on app.example.com to 127.0.0.1:8080, serve ./dist as an SPA for everything else, and enable HTTPS."
- "List certificates that expire within 30 days."
- "Why does https://api.example.com/v1/orders return 404?"

The AI follows the closed loops below: read the configuration guide, generate the configuration, check it with `validate_*`, review the diff with `preview_config_change`, then save and confirm with `verify_site`.

### Litemesh MCP proxy

With Litemesh enabled, LiteGate discovers MCP services registered in Litemesh and proxies their tools and resources, so AI clients only need to connect to LiteGate.

## Tool Capability Matrix

| Category | MCP Tool Name | Purpose / Action | Direct AI Use | Closed Loop | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Discovery** | `detect_environment` | Resolves node hostnames, egress IPs, active ports. | Yes | Partial | Essential for verifying routing entrypoints. |
| **Audit** | `list_sites` | Lists active logical websites. | Yes | Yes | Establishes the baseline before applying mutations. |
| **Audit** | `get_site_config` | Reads site YAML configuration block payloads. | Yes | Yes | Enables precise audit-to-edit cycles. |
| **Audit** | `list_streams` | Lists active Layer 4 stream configs. | Yes | Yes | Covers stream configurations. |
| **Audit** | `get_stream_config` | Reads stream YAML configuration blocks. | Yes | Yes | Enables stream audits. |
| **Audit** | `get_gateway_config` | Reads master `config.yaml` values. | Yes | Yes | Exposes global system settings. |
| **KV Sync** | `get_kv` | Reads key values from Litemesh/Consul KV. | Yes | Yes | Reads dynamic frontend versions or site pointers. |
| **KV Sync** | `set_kv` | Writes key values to Litemesh/Consul KV. | Yes | Yes | Injects zip URLs and SHA256 checksums for hot-swaps. |
| **KV Sync** | `list_kv` | Scans KV registries matching specific prefixes. | Yes | Yes | Useful for auditing dynamic cluster states. |
| **Discovery** | `list_services` | Lists mesh or discovery registry microservices. | Yes | Partial | Helps AI discover backend upstreams. |
| **Discovery** | `get_service_detail` | Retrieves endpoints and tags for a service. | Yes | Partial | Maps domains to healthy discovery upstreams. |
| **Schema** | `get_config_guide` | Retrieves site, L4 Stream or traffic configuration guides. | Yes | Yes | `topic=site` / `stream` / `traffic`, with `lang=zh` / `en`; includes load-balancing policies and scope. |
| **Schema** | `get_gateway_config_schema`| Retrieves global configuration manuals. | Yes | Yes | Exposes master parameters. |
| **Schema** | `get_stream_config_schema` | Retrieves stream DSL parameters. | Yes | Yes | Exposes L4 parameters. |
| **Validation** | `validate_site_config` | Validates site configs against Go struct checkers. | Yes | Yes | Reuses parser validation libraries. |
| **Validation** | `validate_stream_config` | Validates stream configs. | Yes | Yes | Reuses L4 parser validation libraries. |
| **Validation** | `validate_gateway_config` | Validates global system configurations. | Yes | Partial | Captures semantic errors before hot-swapping. |
| **Provision** | `create_proxy_site` | Generates standard reverse proxy site files. | Yes | Yes | Solves common backend proxying needs. |
| **Provision** | `create_static_site` | Generates static folder or SPA site configurations.| Yes | Yes | Sets up dynamic static hosting. |
| **Provision** | `bind_domain_to_service` | Binds an HTTP domain to a registry service. | Yes | Yes | Accepts `lb_policy` for instance selection; defaults to round robin. |
| **Provision** | `create_stream_proxy` | Creates a TCP/UDP Stream with one static backend. | Yes | Yes | For multiple backends, weights, discovery or policies, use `get_config_guide(topic=stream)` then `validate_stream_config` and `save_stream_config`. |
| **Diffing** | `preview_config_change` | Shows unified diffs and operational impact. | Yes | Partial | Outlines mutations, though impact details are basic. |
| **Execution** | `save_site_config` | Writes site files to disk. | Yes | Yes | Triggers automatic hot-reloads instantly. |
| **Execution** | `save_stream_config` | Writes stream files to disk. | Yes | Yes | Triggers L4 stream reloads instantly. |
| **Execution** | `save_gateway_config` | Writes master config files. | Yes | Yes | Triggers global system reloads instantly. |
| **Manual** | `reload_gateway` | Triggers explicit gateway configuration reloads. | Yes | Yes | Useful for forced sync checks. |
| **Rollback** | `rollback_last_change` | Rollbacks configurations to backup states. | Yes | Partial | Restores backups using local `.bak` files. |
| **Verify** | `test_upstream` | Assesses TCP reachability of raw upstreams. | Yes | Partial | Basic network reachability checks. |
| **Verify** | `verify_site` | Triggers HTTP/HTTPS checks to active SNIs. | Yes | Most | Assures SSL and HTTP code correctness. |
| **Verify** | `verify_stream` | Triggers active connection checks to L4 ports. | Yes | Most | Assures L4 port binding correctness. |
| **Telemetry** | `get_recent_errors` | Retrieves recent error log traces. | Yes | Yes | Essential for debugging failed reloads. |
| **Telemetry** | `get_gateway_status` | Audits memory consumption and Goroutine counts. | Yes | Yes | Evaluates node health. |
| **Telemetry** | `list_certificates_status` | Audits expiration timelines for certificates. | Yes | Yes | Aids SSL diagnostics. |
| **Telemetry** | `inspect_certificate` | Pulls detailed SAN and issuer metrics. | Yes | Partial | Mapped for debugging cert handshakes. |
| **Interactive**| `explain_missing_inputs` | Asks the operator for missing details. | Yes | Yes | Reduces guessing by the AI. |

---

## Other tools

These tools cover authentication, release control, service tags, routing diagnostics, certificates and Connect.

| Category | Tool | Purpose |
|---|---|---|
| Provisioning | `create_template_site` | Create a server-side template site; supports template KV mode |
| Provisioning | `create_status_site` | Create a status dashboard site |
| Provisioning | `create_forward_site` | Create a Forward site binding a public HTTPS hostname to an internal stream or Connect peer |
| Provisioning | `export_lite_config` | Compile .lite.yaml into standard YAML; same as `litegate -export-lite` |
| Authentication | `enable_oidc_for_site` | Enable OIDC on a site's proxy routes; v2 keeps comments and shorthand |
| Authentication | `enable_jwt_for_site` | Enable JWT (JWKS or HS secret reference) on proxy routes; notify routes are not covered |
| Authentication | `enable_apikey_for_site` | Enable API key checks and quota rate limiting on proxy routes |
| Deletion | `delete_site_config` | Delete a site configuration file |
| Deletion | `delete_stream_config` | Delete a stream configuration file |
| Release control | `list_releases` | List drafts and published releases |
| Release control | `get_release_detail` | Show a release's details and configuration artifacts |
| Release control | `get_release_diff` | Diff a release against the active files |
| Release control | `validate_draft` | Dry-run the current draft: schema, port conflicts, reserved paths |
| Release control | `publish_release` | Publish a draft after an automatic dry run |
| Release control | `rollback_release` | Roll back to the previous or a given release |
| Service tags | `get_tag_dsl_guide` | Service-tag guide (four-key shortcut and named resources) |
| Service tags | `get_tag_reference` | Authoritative service-tag reference, searchable by query |
| Service tags | `get_service_tag_templates` | Ready-to-use tag templates |
| Service tags | `preview_service_tags` | Validate tags with the runtime parser and preview generated routes |
| Service tags | `explain_tag` | Classify tag keys as resource, shortcut or retired |
| Routing diagnostics | `lookup_route` | Simulate routing for a request; returns route, upstream and rewritten path |
| Routing diagnostics | `get_recent_requests` | Recently processed HTTP requests |
| Routing diagnostics | `list_active_tunnels` | Active WebSocket/Upgrade tunnels |
| Runtime diagnostics | `get_goroutine_profile` | Full goroutine dump for leak hunting |
| Runtime diagnostics | `list_plugins` | List compiled-in plugins; same as `litegate plugins list` |
| Certificates | `request_certificate` | Request a certificate via ACME immediately (manual management) |
| Certificates | `inspect_on_demand_tls` | Inspect On-Demand TLS settings and mapped domains |
| Connect/Forward | `get_connect_status` | Connect tunnel status: peers, sessions, domain ownership and conflicts |
| Connect/Forward | `generate_connect_token` | Generate a Connect peer token, saved with mode 0600; never overwrites |
| Connect/Forward | `generate_forward_token` | Generate a Forward site token, saved with mode 0600; never overwrites |
| Deployment | `generate_systemd_unit` | Generate a systemd unit; same as `litegate systemd --print` |

## Typical Closed-Loop Operations

### 1. Provisioning a Reverse Proxy Site
**Sequence**:
1. `detect_environment`
2. `test_upstream`
3. `create_proxy_site`
4. `preview_config_change`
5. `save_site_config`
6. `verify_site`
7. `get_recent_errors`

### 2. Binding a Domain to a Discovery Service
**Sequence**:
1. `list_services`
2. `get_service_detail`
3. `bind_domain_to_service`
4. `preview_config_change`
5. `save_site_config`
6. `verify_site`

### 3. Deploying a TCP/UDP Stream Forwarder
**Sequence**:
1. `test_upstream`
2. `create_stream_proxy`
3. `preview_config_change`
4. `save_stream_config`
5. `verify_stream`
6. `get_recent_errors`

### 4. Dynamic Frontend Hot-Swapping (Serve KV)
**Sequence**:
1. `detect_environment`
2. `get_gateway_config` (validates Consul or Litemesh driver settings)
3. `set_kv` (writes the zip URL, SHA256 checksum, and version details to `litegate/config/front/main`)
4. `verify_site` (validates HTTP codes of the hot-swapped front-end)
5. `get_recent_errors` (captures extraction or connection errors)

---

### 5. Release control

With `dashboard.release_control` enabled, changes land in a draft first:

1. `save_site_config` / `save_stream_config` (writes the draft)
2. `validate_draft`
3. `get_release_diff`
4. `publish_release`
5. `verify_site`; on problems, `rollback_release`

### 6. Routing troubleshooting

1. `lookup_route` (matched route, upstream and rewrite result)
2. `get_recent_requests`
3. `get_recent_errors`

## Related

- [Global configuration: MCP](user/03-configuration/global-config.md)
- [Configuration release control](release_control_guide.md)
- [CLI reference](user/01-getting-started/cli-reference.md)
