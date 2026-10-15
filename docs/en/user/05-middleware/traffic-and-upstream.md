# Traffic control and upstream policies

Concurrency and rate limits protect entry traffic; retries, breaking and health checks protect attempts to reach backends. Named limit_conn requires a positive limit and key global (default) or ip. Exceeding it returns 503 with Retry-After. See the dedicated rate-limit guide for rate budgets.

Put retry, circuitbreaker and healthcheck in Services for new configurations. Deprecated named retry/circuit_breaker compile into proxy actions; they cannot protect serve/respond or duplicate equivalent inline policies. Retries must satisfy replayability and idempotency constraints. A local breaker rejection guarantees no request was sent, allowing failover without backoff and without recording a passive-health failure.

mirror runs in PostAuth and copies only authenticated requests. Protect mirror destinations and avoid copying private application traffic to untrusted addresses.

## Related documentation and code

- [Rate limits](rate-limit.md)
- [Services](../03-configuration/services.md)
- [Circuit breakers](../09-advanced/circuit-breaker.md)
