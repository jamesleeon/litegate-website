# IDS plugin constraints and troubleshooting

Providers are concurrent singletons: do not open database connections per request or share request objects. Pass the supplied context to external calls. Plugins may continue after host timeouts; do not ignore cancellation or launch unbounded goroutines. Bound cache capacity/TTL and define failure semantics and tenant-isolated keys; coalesce lookups under controlled limits.

Restore Body after reading. Business denial returns Respond; system failures return error. fail_policy: allow permits system-error bypass and requires deliberate security assessment. Selector provides hard isolation; Meta cannot replace it. Explicitly allowlist projected headers and replace untrusted inputs.

Dynamic configuration/key rotation must invalidate caches appropriately. NotifySubscriber provides online signals and Resync only; resynchronize after reconnection. Check registration, binding, options, real requests and instance status when debugging, without logging secrets.

## Related documentation and code

- [Provider guide](ids-provider-plugin-guide.md)
- [Helper kit](../../pkg/plugin/idskit)
