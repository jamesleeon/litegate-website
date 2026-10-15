# Docker catalog identity and transport configuration

## Migrating positional identities

**Breaking change: positional references such as `discovery.instance: docker/0` and `docker/1` no longer work. Replace them with catalog names.** Old references never bind automatically to a different daemon by position.

Give each Docker catalog a unique `name`. For a catalog named `daemon-b`, use either `daemon-b` or `docker/daemon-b` as `discovery.instance`. Reordering catalogs does not change ownership or explicit references.

Site loading and preview require explicit references to identify enabled Docker catalogs. Positional references, misspelled names and disabled catalogs fail immediately with the available names, rather than producing a request-time 503. Main configuration reload also checks existing routes and service-graph leaves and rejects removal of referenced catalogs. Validation uses catalog configuration; the daemon need not be online or have discovered instances.

Unnamed catalogs receive a stable internal SHA-256 identity derived from their connection address and namespace. **Name a catalog whenever you need an explicit reference.** Duplicate identities fail validation; assign distinct names.

```yaml
service_discovery:
  catalogs:
    - name: daemon-b
      enabled: true
      provider: docker
      namespace: default
      socket_path: tcp://docker-b.example:2376
      default_domain: b.example
      tls:
        ca_file: /etc/litegate/docker-b/ca.pem
        cert_file: /etc/litegate/docker-b/cert.pem
        key_file: /etc/litegate/docker-b/key.pem
```

## TLS and transports

TLS settings are isolated per catalog and override the global certificate directory. Specify `cert_file` and `key_file` together. `tls.*` accepts only `tcp://` or `https://` endpoints; SSH, Unix sockets, Windows named pipes and `http://` reject it. When `socket_path` is omitted, validation checks `DOCKER_HOST`. If neither is set, the default local socket does not accept TLS settings.

TCP with TLS uses HTTPS. Unencrypted HTTP/TCP connections emit an initialization warning. Windows defaults to `npipe:////./pipe/docker_engine`, which can also be configured explicitly.

The first API request negotiates through `/version`, selecting a mutually supported version (client maximum: 1.47). Negotiation failures can be retried. Only a 404 from `/version` enables compatibility with old proxies using unversioned paths.

## Reconciliation and Swarm networks

Standalone discovery performs full reconciliation every 60 seconds, mutually exclusive with event updates. Containers on internal networks with explicit ports and complete list summaries use those summaries, preserving health status. Host networking, host-port mapping and incomplete summaries still require inspect.

Swarm normally polls at the configured interval. A service `UpdateStatus.State` of `updating` or `rollback_started` temporarily shortens intervals above one second to one second; completion restores the configured interval.

Network selection tries the explicitly selected network, networks shared with the gateway, then other non-ingress networks sorted by name. If `litegate.docker.network` is explicit but a task has no usable address there, diagnostics warn before fallback. Docker Stack network prefixes participate in matching. Tasks without a valid non-ingress address are skipped with an error diagnostic; duplicate logs are emitted only after task state changes.
