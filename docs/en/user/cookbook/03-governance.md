# Governance: entry limits and backend policies

Authentication, WAF, rate limits and concurrency caps protect routes. Retries, breakers and health checks belong to upstream Services. Do not configure equivalent retry/breaker policies in both Services and deprecated named middleware.

Choose local SSO, Basic, JWT, OIDC or Forward Auth for the actual access flow. Use IDS Selectors for dynamic business-identity isolation. Replicas do not automatically share in-memory quotas or bans.

## Related documentation and code

- [Pipeline](../05-middleware/pipeline.md)
- [Services](../03-configuration/services.md)
- [HA state](../10-deployment/ha-state.md)
