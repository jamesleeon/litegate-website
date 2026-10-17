# LiteGate Plugin System Overview

LiteGate uses a **compile-time registry** plugin architecture (similar to the static integration model of Caddy / Traefik). Developers, architects and third-party teams can write plugins in their own repositories and build a custom gateway binary without forking or modifying LiteGate's core.

---

## Design principles

### 1. Why compile-time registration instead of dynamic loading (`.so`)?

Developers often ask why LiteGate doesn't use Go's official `plugin` shared libraries (`.so`):

| Aspect | Go `plugin` dynamic loading (`.so`) | LiteGate compile-time registry |
| :--- | :--- | :--- |
| **Platform support** | ❌ Linux/macOS only, **no Windows** | ✅ Same as Go cross-compilation; the OS, CGO and Go version constraints of the plugin's own dependencies still apply |
| **Dependency and ABI stability** | ❌ Very fragile: the host and `.so` must match Go version, dependency versions and build flags byte for byte, or the process crashes with SIGSEGV at runtime | ✅ Statically linked at build time; types and symbols are checked by the compiler, so there is no runtime ABI mismatch |
| **Runtime performance** | ⚠️ Overhead from cross-boundary calls and dynamic symbol resolution | ✅ Ordinary function calls, like native code, with no dynamic loading overhead |
| **Operations and delivery** | ❌ Ship a set of `.so` files alongside, with risks of environment pollution and missing libraries | ✅ **Single static binary**: copy and run, fits standard container delivery |

> [!NOTE]
> For a few special governance cases (such as lightweight rule scripts), LiteGate also offers a restricted WASM ABI option (see [IDS WASM](../../ids-wasm-plugin-guide.md)); the general data path uses compile-time static registration.

### 2. Two contract layers

To decouple the third-party plugin ecosystem from the core, LiteGate separates two contract layers:

```
┌─────────────────────────────────────────────────────────────────┐
│                     LiteGate core runtime                       │
│  internal/action · internal/router · internal/middleware ...   │
│  (heavy internal types: loader.Site, proxy.Pool, ...)          │
└──────────────────────────────▲──────────────────────────────────┘
                               │ Narrow adapters
┌──────────────────────────────┴──────────────────────────────────┐
│                    Public contract API                          │
│              github.com/jamesleeon/LiteGate/pkg/plugin          │
│  - Narrow interfaces (Context, ActionConfig, DiscoveryClient)   │
│  - Injected capabilities: Dependencies (Logger, Discovery, ...) │
│  - Uniform metadata: Manifest (version, description, caps)      │
└──────────────────────────────▲──────────────────────────────────┘
                               │ Static registration (blank import)
┌──────────────────────────────┴──────────────────────────────────┐
│              External plugins / private packages                │
│  github.com/your-org/litegate-plugins (separate repository)     │
└─────────────────────────────────────────────────────────────────┘
```

- **Internal layer (`internal/...`)**: fast dispatch inside the gateway.
- **Public contract layer ([`pkg/plugin`](../../../../pkg/plugin))**: open to every external developer. It exposes only narrow interfaces and structs, so internal refactoring of the core doesn't require changes in external plugins; changes to the public contract itself are identified by the Manifest API version.

---

## Extension points at a glance

LiteGate opens the following extension points at key seams of the request lifecycle, spanning L4 to L7, control plane and data plane:

| # | Extension type | Key interface | Registration function | Use cases |
|---|---|---|---|---|
| 1 | **Ingress** (entry interception) | `IngressHandler` | `plugin.RegisterIngress` / `RegisterTypedIngress` | Take over port traffic before Site routing and normalization (HTTP CONNECT forward proxies, protocol tunnels, ...) |
| 2 | **Middleware** | `MiddlewareHandler` | `plugin.RegisterMiddleware` | Process requests along the chain (authentication, rewrites, custom auditing, CORS, ...) with 8-phase ordering |
| 3 | **Action** | `Handler` | `plugin.RegisterAction` | Terminal request handling and response generation (NATS publishing, custom rendering engines, AI LLM proxies, ...) |
| 4 | **LoadBalancer** | `LoadBalancer` | `plugin.RegisterLoadBalancer` | Custom upstream selection (weighted least connections, consistent hashing, canary weighting, ...) |
| 5 | **Discovery Provider** | `DiscoveryProvider` | `plugin.RegisterDiscoveryProvider` | Non-built-in registries (Nacos, Eureka, Zookeeper, in-house CMDB) feeding the service catalog and routes |
| 6 | **DNS Provider** | `CertDNSProviderV2` / `DDNSProvider` / `HTTPSDNSProvider` | `plugin.RegisterDNSProviderV2` | ACME DNS-01 challenges, public DDNS, and HTTPS records for ECH |
| 7 | **IDS Provider** | `IDSProvider` | `plugin.RegisterIDSProvider` | Unified governance before any Action (signature checks, session authentication, bot blocking, routing labels) |
| 8 | **KV Provider** | `KVProvider` | `plugin.RegisterKVProvider` | Dynamic content watching for `serve` / `template` actions (Redis/etcd/S3 asset pushes, ...) |
| 9 | **Template Func** | `template.FuncMap` | `plugin.RegisterTemplateFunc` / `RegisterTemplateFuncs` | Business-specific functions for the built-in `template` action (masking, encryption, time formatting, ...) |
| 10 | **Stream / Stream Filter / Datagram** (L4) | `StreamHandler` / `StreamFilter` / `DatagramHandler` | `plugin.RegisterStream` / `RegisterStreamFilter` / `RegisterDatagram` | Custom TCP/UDP protocol handling and connection filtering (e.g. a read-only Redis guard) |
| 11 | **Response Filter** | `ResponseBodyFilter` | `plugin.RegisterResponseFilter` | Streaming rewrites of proxied response bodies (masking, injection) |
| 12 | **Exporters** | `AccessLogExporter` / `TraceExporter` / `MetricsExporter` | `plugin.RegisterAccessLogExporter` / `RegisterTraceExporter` / `RegisterMetricsExporter` | Push access logs, traces and metrics to external systems asynchronously |
| 13 | **Cert Issuer** | `CertIssuerProvider` | `plugin.RegisterCertIssuer` | Private PKI integration; the issuer receives only the CSR, never the private key |
| 14 | **Upstream Transport** | `UpstreamTransport` | `plugin.RegisterUpstreamTransport` | Custom RoundTripper for upstreams (e.g. enterprise mTLS) |
| 15 | **Config Source** | `ConfigSourceProvider` | `plugin.RegisterConfigSource` | Load global and site configuration snapshots from an external system |
| 16 | **Notify Transport** | `NotifyTransport` | `plugin.RegisterNotifyTransport` | Message channel for the plugin notify bus (built into the NATS plugin) |

Items 10–15 are bound in the global `extension_plugins`; see the [configuration guide](configuration.md#8-global-extension-plugin-bindings-extension_plugins).

---

## Built-in plugins

Official LiteGate release binaries include these reference plugins, all registered through the same public API as third-party plugins:

1. **`nats` (Action)**: publishing, request-reply and reliable JetStream publishing between HTTP and NATS, plus SSE subscriptions.
2. **`openapi-md5` (IDS)**: compatibility with legacy enterprise API MD5 body signatures.
3. **`forward_proxy` (Ingress)**: forward proxy with HTTP CONNECT, mTLS client restrictions, bcrypt authentication and destination ACLs.
4. **`forward_auth` (Middleware)**: per-request authentication against external services such as Authelia.
5. **`nomad` (Discovery)**: HashiCorp Nomad service discovery, also the reference Discovery plugin.

---

## Inspecting compiled plugins

Run these CLI commands to see which plugins the current LiteGate binary contains:

```bash
# 1. List all compiled plugins (kind, name, version, API contract)
litegate plugins list

# 2. Show one plugin's metadata and configuration example
litegate plugins inspect ingress/forward_proxy
litegate plugins inspect action/nats

# 3. Health check for missing Manifests or API version drift
litegate plugins doctor
```

The **Compiled Plugins** tab of the Dashboard also shows plugin cards with copyable YAML configuration examples.

---

## In this chapter

- **[Build and CLI tools](build-and-cli.md)**: custom builds with `litegate build --with`, blank imports in your own `main.go`, `plugins` diagnostics and CI pipelines.
- **[Configuration guide](configuration.md)**: enable and debug each kind of plugin in global `config.yaml` and `sites/*.yaml`.
- **[Plugin authoring guide](authoring-guide.md)**: write your first LiteGate plugin, with interface skeletons for the main extension points, lifecycle management, configuration validation, panic isolation and concurrency pitfalls.
- **[Discovery plugin development: Nomad example](../../discovery-provider-plugin-guide.md)**: a complete example from development and build to integration.
