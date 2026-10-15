# Common configuration pitfalls

Check parsing and the running version before Host, entrypoint, routes and backends. Quote @matcher references. V2 rejects anchors/aliases, duplicate keys and null. Compile unknown plugins first; definitions alone do not bind routes.

Rewrite does not reroute. DNS plugins use auto_cert.dns_providers. Service breakers use circuitbreaker/maxrequests/tripthreshold, whereas compatibility actions use circuit_breaker/max_requests/trip_threshold. Do not mix levels or spellings.

For 401/403 inspect authentication/policy; 429 means limiting. Distinguish concurrency, breakers, missing backends and unavailable dependencies for 503; inspect upstream errors/timeouts for 502/504. Preflight corrected configuration, publish and verify real requests.

## Related documentation and code

- [Debugging](../11-troubleshooting/debugging.md)
- [Configuration](../03-configuration/site-yaml-v2-concepts.md)
