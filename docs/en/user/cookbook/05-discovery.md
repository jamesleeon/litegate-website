# Discovery: Services and registration tags

Discovery provides addresses/health while configuration watch supplies site configuration; these are separate roles. A Service chooses either discovery or servers. Catalogs and registration tags can generate routes but still require explicit exposure markers and valid settings.

Check provider authentication, namespace, service name and port before the tag DSL, Selectors, healthy instances and actual balancing. Consul, LiteMesh and Kubernetes have different resource models; changing the provider name alone does not guarantee equivalent behavior.

## Related documentation and code

- [Discovery](../07-discovery/overview.md)
- [Service configuration](../03-configuration/services.md)
- [Tags](../03-configuration/tag-dsl.md)
