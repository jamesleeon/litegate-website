# Docker Provider Test Guide

The Docker provider discovers containers carrying `litegate.*` labels and builds routes from those labels. See the [Service Tags Guide](user/03-configuration/tag-dsl.md) for how to write them.

## Simplest test

```bash
docker run -d --name mqserver --network litegate-net \
  -l litegate.http.host=mq.saas.local \
  your-mq-image:latest

curl -H 'Host: mq.saas.local' http://127.0.0.1/
```

## Test with policy

```bash
docker run -d --name mqserver --network litegate-net \
  -l litegate.http.routers.mq.match.hosts=mq.saas.local \
  -l litegate.http.services.mq.discovery.name=mq \
  -l litegate.http.services.mq.loadbalancer.server.port=8080 \
  -l litegate.http.services.mq.timeout=30s \
  your-mq-image:latest
```

## Service name and port

- Service name: `discovery.name`; otherwise `<compose project>-<compose service>`; otherwise the container name. Containers with the same name become instances of one service.
- Port: `loadbalancer.server.port` is the container port; it can be omitted when the container exposes or maps a single port.
- The global `network_mode: external` uses published host ports; for one container use `litegate.docker.usehostport=true` (not supported on Swarm).
- For a container on several networks, pick one with `litegate.docker.network=<network>`.
- Any container with a `litegate.*` label is discovered; `litegate.enable=false` opts it out explicitly.

## Checks

1. The service shows no diagnostics on the dashboard's service tag page.
2. The gateway can reach the container IP (same network, or host ports).
3. Unknown properties and invalid references reject the container instead of being silently ignored.
