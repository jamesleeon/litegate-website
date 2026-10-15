# Ingress entrypoint plugins

Ingress plugins run on bound HTTP entrypoints before Site matching, supporting HTTP forward proxies and independently recognized requests. ingress_plugins order determines execution. Each binding needs a unique name, registered type and non-empty entrypoints referencing existing entries. Missing compiled plugins fail validation.

Entrypoint constraints, global governance, trusted forwarding headers and client-IP handling run first. A plugin reports whether it handled the request; otherwise processing continues to the next plugin/site. It cannot intercept raw TCP/SNI. Internally injected Forward/Connect requests retain site authorization and bypass ingress plugins.

RegisterTypedIngress uses strict JSON decoding and prepare/factory construction. prepare must be pure and side-effect-free. Instance construction prepares once; independent preflight may prepare separately and discard the result. Follow narrow request/dependency contracts, cancellation, shutdown and concurrency rules. Forward proxies need destination constraints and authentication to avoid becoming open proxies.

## Related documentation and code

- [Public contract](../../pkg/plugin/ingress.go)
- [Entrypoints](user/03-configuration/entrypoints.md)
- [Forward proxy example](../../examples/plugins/ingress/forwardproxy/README.md)
