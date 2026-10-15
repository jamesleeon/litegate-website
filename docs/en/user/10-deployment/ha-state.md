# Replica state and failure isolation

Multiple replicas do not automatically share gateway memory. Plan consistency around the storage and plugins actually enabled; configuring Redis does not share all state.

| State | Behavior across replicas |
|---|---|
| scan_protection risk and bans | Process-local; no shared bans |
| proxy_cache | Local memory; cache hits are split across replicas |
| Breakers and passive health | Process-local, reflecting each replica's results |
| Rate limits | Depends on the mechanism; local buckets are not shared and Redis requires explicit configuration |
| IDS sessions and caches | Provider-managed; the core does not guarantee Redis sessions |
| Sticky sessions | Check cookies and relevant key configuration; cross-replica decryption is not automatic |
| NATS offline subscriptions | Require JetStream, a shared ACK key and consistent business identities |
| Configuration and certificates | Explicitly configure shared backends or synchronization and verify access/recovery |

Local breaker rejections do not count as passive-health failures. Replayable requests can fail over without backoff or consuming the ordinary error retry budget. The load balancer can still select an open circuit; this is not removal from discovery before selection.

With round-robin replicas, another process may not yet have banned a scanner. Apply a common IP policy at the front door when uniform blocking is required. Validate node failover, configuration changes, cache invalidation and credential rotation before deployment.

## Related documentation and code

- [Breaker](../09-advanced/circuit-breaker.md)
- [Scan protection](../05-middleware/scan-protection.md)
- [Proxy implementation](../../../../internal/action/proxy.go)
