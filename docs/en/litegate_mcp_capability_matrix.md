# LiteGate MCP Capability Matrix

This document outlines the Model Context Protocol (MCP) capabilities exposed by LiteGate to LLM/AI agents. It evaluates whether these tools provide sufficient coverage to enable autonomous website provisioning and infrastructure management *without* requiring external configuration documents.

## Executive Summary

LiteGate's active MCP tools cover common website configurations and administrative routines. AI agents can autonomously retrieve system states, generate configurations, validate schemas, apply hot-swaps, and verify endpoints for these primary use cases:
- Inbound Reverse Proxy configurations.
- Static Website hosting (including Single Page Applications).
- Binding domain SNI records to logical discovery services.
- Layer 4 TCP/UDP stream forwarding.
- Diagnostic troubleshooting and telemetry audits.

**Conclusion**: Once an operator integrates LiteGate's MCP and expresses intent (e.g., domain names, upstream endpoints, site profiles), the AI agent requires no external manuals or documents to manage the gateway successfully.

---

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
| **Schema** | `get_config_guide` | Retrieves structural site config schema guides. | Yes | Yes | Reduces AI's reliance on external markdown files. |
| **Schema** | `get_gateway_config_schema`| Retrieves global configuration manuals. | Yes | Yes | Exposes master parameters. |
| **Schema** | `get_stream_config_schema` | Retrieves stream DSL parameters. | Yes | Yes | Exposes L4 parameters. |
| **Validation** | `validate_site_config` | Validates site configs against Go struct checkers. | Yes | Yes | Reuses parser validation libraries. |
| **Validation** | `validate_stream_config` | Validates stream configs. | Yes | Yes | Reuses L4 parser validation libraries. |
| **Validation** | `validate_gateway_config` | Validates global system configurations. | Yes | Partial | Captures semantic errors before hot-swapping. |
| **Planning** | `plan_site_from_intent` | Analyzes intent to yield configuration templates. | Yes | Partial | Useful for designing complex multi-routing sites. |
| **Provision** | `create_proxy_site` | Generates standard reverse proxy site files. | Yes | Yes | Solves common backend proxying needs. |
| **Provision** | `create_static_site` | Generates static folder or SPA site configurations.| Yes | Yes | Sets up dynamic static hosting. |
| **Provision** | `bind_domain_to_service` | Maps SNI hostnames to registry service upstreams. | Yes | Yes | Streamlines mesh discovery. |
| **Provision** | `create_stream_proxy` | Generates L4 TCP/UDP stream rules. | Yes | Yes | Sets up L4 forwarding. |
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

## Core Coverage Review

Excluding specialized OIDC setups, LiteGate's MCP provides total autonomy to AI agents for standard operations:
- Common reverse proxy and static site provisioning: **Fully Covered**
- Stream forwarder configurations: **Fully Covered**
- Pre-execution config validation: **Fully Covered**
- Automated hot-reloads: **Fully Covered**
- Verification testing: **Fully Covered**
- Active telemetry audits: **Fully Covered**
- High-fidelity change diffing: **Partially Covered**
- Backup restoration: **Partially Covered**

---

## Future Enhancements
To improve autonomous operations, we recommend refining the following tools:
- `preview_config_change`: Enhance impact analysis to report affected ports and SNIs.
- `verify_site`: Include matched route and upstream node IP properties in verification payloads.
- `verify_stream`: Verify if the active socket listener maps to LiteGate's process.
- Rollback routines: Improve error handling for failed backup writes.

---

## Autonomous Operations Without Documents

When an operator integrates LiteGate's MCP, the AI agent does not require manual documentation because:
- The MCP tools expose structural configuration schemas directly.
- The MCP tools expose active runtime states and configurations.
- The MCP tools provide validation, execution, verification, and diagnostics natively.

External manuals serve as supplementary material rather than a requirement for autonomous site provisioning.
