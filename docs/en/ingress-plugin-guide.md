# Ingress Entry Plugins

Ingress plugins handle requests on a given HTTP entrypoint before Site domain matching. They suit standard forward proxies or other HTTP services that recognize their own requests. Actions and Middleware keep serving matched site routes. Plugins are still registered at compile time; the public contract lives in `pkg/plugin/ingress.go`.

## Where they run

```text
Entrypoint identification and Forward target constraints
  → Global Ingress governance and IP restrictions
  → Trusted source headers and client IP resolution
  → The current entrypoint's Ingress plugin chain
  → Path cleaning, control endpoints, Site matching and HTTPS redirect
  → Site / Route middleware → Action
```

The array order of `ingress_plugins` is the execution order. Each binding declares a unique `name`, a registered `type` and non-empty `entrypoints`; the entrypoints must exist in the global `entrypoints`. A plugin missing from the build fails configuration validation, so configuration never silently does nothing. An empty configuration takes over no traffic; without configured plugins, ordinary requests don't take the plugin lifecycle lock. Plugins cannot take over raw TCP/SNI; that belongs to entrypoint transport routes. Internal requests injected through Forward or Connect always go through the normal site authorization path and never run entry plugins.

## Minimal plugin

```go
package ping

import (
    "net/http"
    "github.com/jamesleeon/LiteGate/pkg/plugin"
)

type config struct { Path string `json:"path"` }
type handler struct { path string }

func (h *handler) Claim(r *http.Request, m plugin.IngressRequest) http.Handler {
    if r.Method != "GET" || r.URL.Path != h.path { return nil }
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        w.Write([]byte("pong from " + m.EntryPoint))
    })
}

func init() {
    err := plugin.RegisterTypedIngress("ping",
        func(cfg config) (config, error) { return cfg, nil },
        func(cfg config, deps *plugin.Dependencies) (plugin.IngressHandler, error) {
            return &handler{path: cfg.Path}, nil
        },
    )
    if err != nil { panic(err) }
}

```

Configuration goes in a separate `config` object, which may contain nested structures, lists and numbers:

```yaml
entrypoints:
  tools:
    address: 127.0.0.1:9000
ingress_plugins:
  - name: local-ping
    type: ping
    entrypoints: [tools]
    config:
      path: /ping
```

Plugins parse JSON tags with `IngressConfig.Decode`; the data comes from an independent immutable snapshot, and unknown fields are errors. `Validate` is a required side-effect-free check: it must not create resources, read the live environment or make network calls. `Factory` is runtime initialization and may read secrets, build transports or start resources; it runs once per binding, and multiple entrypoints of the same binding share the instance. Dependencies provides logging, service discovery and a view of the shared plugin configuration. Plugins can register `Manifest{Kind: "ingress", ...}` for the CLI, Dashboard and MCP.

## Request and lifecycle contract

- `IngressHandler.Claim(r, meta) http.Handler` is the only way to take over a request and may be called concurrently. Return nil to continue routing; return a handler and the host runs it, recording logs, metrics and Dashboard data. Claim receives no ResponseWriter and must not modify the request or read the body.
- The request target is the one before path cleaning. A forward proxy must keep absolute-form target semantics; it must not match the destination host by the proxy's own domain, nor mistake ordinary paths for proxy requests.
- HTTP/1 CONNECT may use `http.NewResponseController(w).Hijack()`; keep any bytes already buffered in the returned reader. HTTP/2/3 don't use Hijack and must be implemented on the protocol's request/response streams.
- A handler must not return until it has released ownership of the connection; it must not start a background tunnel and return immediately. The host drains old instances with an atomic call counter; past `http.shutdown_grace` (30 seconds if unset) they are closed forcibly.
- The optional `IngressCloser.Close(context.Context)` releases resources, cancels work and closes held connections; it should return promptly and respect the Close deadline. Dependencies.Context is managed by the host and cancelled on shutdown. After a successful update the old instance is closed once its calls drain or the grace period expires; on process shutdown Close is called immediately and may run concurrently with Claim and with handlers of claimed requests. Each instance is closed once.
- If Factory returns both a non-nil handler and an error, the host closes that partially initialized instance. If Factory panics or cannot return an instance, it must prevent leaking whatever it initialized.
- Uncommitted candidate instances are closed; a published instance stays when a candidate fails. Unchanged bindings are not rebuilt, and updating only Sites neither interrupts nor rebuilds entry plugins.
- Claimed requests do not go through Site middleware or certificate authorization checks. Access logs, metrics and Dashboard data are recorded by the host and aggregated as `ingress:<binding name>`; CONNECT duration is recorded as stream lifetime, not ordinary request latency. Authentication, destination policy and rate limiting are the plugin's job.
- Bindings are compared with `reflect.DeepEqual`. Changing only the value of the environment variable named by `password_env` does not rebuild the instance; change the binding or restart to load the new password.
- The hook runs after global IP rules and IDS and before Site selection. The host has already stripped authoritative trust headers, `X-Forwarded-Proto` / `X-Forwarded-Host` from untrusted connections and `X-Selector-Sid` from untrusted routing clients, and injected source and forwarding-protocol metadata. The host's `Server` and `Alt-Svc` response headers are set only after plugins decline.

The complete reference implementation is [forward_proxy](../../examples/plugins/ingress/forwardproxy/README.md), with tests for real HTTP, HTTPS CONNECT, buffered bytes, half-close, DNS address validation and shutdown. Its source is public in `pkg/plugins/forwardproxy` and the standard CLI blank-imports it; the Dashboard, CLI and MCP show it from the same registry and Manifest as type `ingress`. Entry plugins run at a different stage from actions/IDS but use the same compile-time registration and public SDK. Generate a bcrypt hash with `litegate -hash 'your-password'` for `password`, or use `password_env` to read a raw password; the two are mutually exclusive. `hosts` constrains TLS SNI, not the destination host.

## SDK tools and forward proxy safety rules

`RegisterTypedIngress[T, P]` strictly decodes JSON into T, then explicitly produces the prepared value with `prepare func(T) (P, error)` and passes it to `factory func(P, *Dependencies) (IngressHandler, error)`. Building an instance decodes and prepares once; standalone configuration preflight prepares independently and discards the result, so prepare must have no side effects. Duration fields can use `plugin.Duration`, which accepts positive durations such as `"10s"`.
`IngressRequest` carries EntryPoint, ClientIP, ServerName, the raw RequestURI and the protocol major/minor version.
`proxyutil.Tunnel(ctx, w, r, backend, idle)` (import `pkg/plugin/proxyutil`) takes over an authorized, already dialed connection, handling HTTP/1 Hijack, HTTP/2/3 streams, bidirectional copying and cancellation. Half-close is kept only on hijacked HTTP/1 connections; on HTTP/2/3 the upload stops when the download ends and the function returns, signalling end of stream promptly. The caller closes backend; ctx should carry a maximum lifetime deadline.

When sharing an entrypoint with websites, configure `hosts` or enable `probe_resistance`, otherwise absolute-form HTTP/1 requests to normal sites may get 407. `hosts` restricts TLS SNI; plaintext entrypoints should use a dedicated entrypoint or probe_resistance.
Successful bcrypt authentication caches the SHA-256 digest of the request's authentication header for 5 minutes, renewed on hit and compared in constant time; the cache holds one entry, each instance runs at most two bcrypt verifications at once, and waiting for a slot is bound by the request context and at most 100 ms, after which 407 is returned (with probe_resistance, routing to websites continues).
Wildcard domain rules reject local interface addresses, NAT64 `64:ff9b::/96`, `240.0.0.0/4` and `198.18.0.0/15` by default; to reach these on purpose, configure IP/CIDR explicitly. Deny rules always win.
DNS resolution and each address dial have their own dial_timeout, while the whole request stays within max_duration; all DNS answers are validated before dialing.

Dependencies.Context is injected only into ingress plugins; other plugin types get nil.
The interface address snapshot is cached for 30 seconds and refreshed on demand. A cloud host's 1:1 NAT elastic public IP may not be on any interface, so the interface check cannot detect connections back to it; add the gateway's public IP to `denied_destinations`.
Unchanged bindings reuse their instance; changing only `shutdown_grace` doesn't update the retirement grace stored in that instance — change the binding or restart.
