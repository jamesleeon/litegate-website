# LiteGate Docker Provider Deployment & Configuration Guide

LiteGate features a built-in, highly optimized, non-intrusive **Docker Dynamic Service Discovery (Docker Provider)** engine. By directly listening to the real-time Docker Daemon event stream, LiteGate instantly reacts to container starts, deaths, and health checks, dynamically updating its internal reverse proxy upstream load balancer ring. This achieves true **"route on start, strip on death"** behavior.

This guide provides an in-depth look into the core mechanics, gateway configuration parameters, container label specifications, typical deployment topologies, and production-grade best practices for the Docker Provider.

---

## Core Mechanics & Key Benefits

LiteGate's Docker discovery engine is built with the following advantages:

1. **Instant Event-Driven Discovery**: Subscribed directly to the Docker Socket API event pipeline, completely eliminating polling overhead. Upstream routing updates execute in milliseconds upon receiving `start` or `die` events.
2. **Native Health Check Integration**: Integrates directly with Docker's native container health checks. When a container's status turns `unhealthy`, LiteGate instantly strips it from the active upstream ring, restoring it automatically once it returns to `healthy`.
3. **Debounced Swarm Sync**: During rolling deployments or massive scaling events under Docker Swarm, countless tasks start and stop concurrently. LiteGate's **200ms debounce sync mechanism** aggregates these events, preventing CPU and memory spikes from high-frequency route rebuilds.
4. **Intelligent Port & Network Resolution**: Automatically infers the correct target port from exposed or published port configurations and dynamically bypasses the Swarm ingress network to prevent routing loops.

---

## LiteGate Configuration

To enable the Docker Provider, add a new catalog item under the `service_discovery.catalogs` block in your principal configuration file (e.g., `config.yaml`):

```yaml
# HTTP listener settings
http:
  port: 80
  https_port: 443

# Active Service Discovery Catalogs
service_discovery:
  catalogs:
    - enabled: true
      provider: "docker"
      socket_path: "/var/run/docker.sock"  # Unix path, tcp:///https:// URL, or omit to use DOCKER_HOST
      network_mode: "internal"             # "internal" (container IP) or "external" (host port mapping)
      swarm_mode: false                    # Enable Docker Swarm clustering support
      swarm_auto_detect: false             # Optional; auto-enable only on a Swarm manager
      swarm_network: "litegate-net"        # Preferred shared network in standalone or Swarm mode
      swarm_reconcile_interval: 5s          # Swarm task reconciliation interval
      namespace: "default"                 # Logical namespace for routing isolation
```

### Configuration Parameters Reference

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `enabled` | `bool` | `false` | Enables/Disables this Docker discovery catalog. |
| `provider` | `string` | - | Must be explicitly set to `"docker"` to activate the Docker adapter. |
| `socket_path` | `string` | `"/var/run/docker.sock"` | Unix socket path or `tcp://`, `http://`, or `https://` Docker API endpoint. If empty, `DOCKER_HOST` is used. Standard `DOCKER_TLS_VERIFY` and `DOCKER_CERT_PATH` (`ca.pem`, `cert.pem`, `key.pem`) are supported. |
| `network_mode` | `string` | `"internal"` | **Routing Communication Mode**:<br>• `"internal"`: Proxies directly to internal container IPs/ports.<br>• `"external"`: Proxies to ports published on the host interface. |
| `swarm_mode` | `bool` | `false` | Activates Docker Swarm discovery, querying services and tasks API, and enabling event debouncing. |
| `swarm_auto_detect` | `bool` | `false` | Auto-detects Swarm only when the connected daemon is a manager capable of serving cluster APIs. Workers are rejected. |
| `swarm_network`| `string` | - | Preferred shared network. This applies to standalone containers too; stack-prefixed Swarm names are matched automatically. |
| `swarm_reconcile_interval` | `duration` | `5s` | Interval for authoritative Swarm task reconciliation. |
| `namespace` | `string` | `"default"` | **(Optional)** Logically isolates services under different namespaces when co-hosting multiple catalogs. |

---

## Container Labels Reference

LiteGate utilizes non-intrusive **Docker container labels** to dynamically compile routes. Once your application container is stamped with `litegate.*` labels, the gateway captures it and creates a 7-layer routing binding.

### Standard Labels

| Label Name | Example | Required | Description |
| :--- | :--- | :--- | :--- |
| `litegate.enable` | `"true"` | Recommended | Explicitly signs this container into LiteGate discovery. `false` always disables it; without this switch, any other `litegate.` label opts in. |
| `litegate.http.host` or `litegate.http.routers.<name>.*` | Host / Router properties | Recommended | The shortcut, or a named Router with Host/path rules; attached to web and websecure by default. |
| `litegate.http.services.<name>.discovery.name` | `"mqserver"` | Optional | Docker discovery name; falls back to Compose `<project>-<service>` or the container name. |
| `litegate.http.services.<name>.loadbalancer.server.port` | `"8080"` | Optional | Internal container port; a single exposed or mapped port can be auto-detected. |

### Advanced Network & Routing Labels

| Label Name | Example | Description |
| :--- | :--- | :--- |
| `litegate.docker.usehostport` | `"true"` | Docker Provider hint that forces use of the mapped host port. |
| `litegate.docker.network` | `"custom-net"` | **Preferred Network Interface**. If a container is attached to multiple virtual networks, use this label to pinpoint which network interface LiteGate should connect to, avoiding unroutable private networks. |

> [!TIP]
> **Instance identity**: keep `version`, `sid`, `zone`, and similar fields as Endpoint Metadata. Match them with Service `discovery.selector.*` or a selector returned by IDS.

---

## Recommended Deployment Topologies

### Topology A: Flat Container Network (Bridge Mode)

**Scenario**: Both LiteGate and your business backend containers are deployed on the same Docker host and share a user-defined bridge network. LiteGate connects to the Docker socket. Traffic flows directly within the virtual Docker networks, minimizing external host interface overhead.

```
                    ┌─────────────────────────┐
                    │      Docker Network     │
                    │     (litegate-net)      │
                    └────────────┬────────────┘
                                 │
         ┌───────────────────────┴───────────────────────┐
         ▼                                               ▼
┌──────────────────┐  Direct Container IP Route  ┌──────────────────┐
│  litegate-edge   ├──────────────────────────►│   saas-mqserver  │
│  (Container IP)  │                           │   (172.25.0.3)   │
└──────────────────┘                           └──────────────────┘
```

#### Steps and Artifacts

1. **Create the shared bridge network**:
   ```bash
   docker network create litegate-net
   ```

2. **Configure your LiteGate `config.yaml`**:
   ```yaml
   http:
     port: 80
     https_port: 443

   service_discovery:
     catalogs:
       - enabled: true
         provider: "docker"
         socket_path: "/var/run/docker.sock"
         network_mode: "internal"             # Direct IP routing
   ```

3. **Deploy LiteGate using `docker-compose.yaml`**:
   ```yaml
   version: '3.8'

   services:
     litegate:
       image: jamesleeon/litegate:latest
       container_name: litegate
       restart: always
       volumes:
         - ./config.yaml:/app/config.yaml
         - /var/run/docker.sock:/var/run/docker.sock  # Mount host engine socket
       group_add:
         - "${DOCKER_GID}"  # export DOCKER_GID=$(stat -c '%g' /var/run/docker.sock)
       ports:
         - "80:80"
         - "443:443"
       networks:
         - litegate-net

   networks:
     litegate-net:
       external: true
   ```
   Launch with the Docker socket group ID:
   ```bash
   export DOCKER_GID=$(stat -c '%g' /var/run/docker.sock)
   docker compose up -d
   ```

4. **Launch your business container with discovery labels**:
   ```bash
   docker run -d \
     --name business-api \
     --network litegate-net \
     -l litegate.enable=true \
     -l litegate.http.routers.business.match.hosts=api.example.com \
     -l litegate.http.services.business.discovery.name=business-service \
     -l litegate.http.services.business.loadbalancer.server.port=8080 \
     my-business-app:latest
   ```

---

### Topology B: External Host Mode (Mixed Deployment)

**Scenario**: LiteGate runs directly as a host binary (on a virtual machine or bare metal), while backend services are inside Docker containers. LiteGate routes traffic through published host interfaces (`HostIP:HostPort`).

```
┌────────────────────────────────────────────────────────┐
│                      Host OS                           │
│                                                        │
│   ┌─────────────────┐    Forward Traffic to       ┌─┴───────────────┐  │
│   │    LiteGate     ├────────────────────────────►│  saas-mqserver  │  │
│   │  (Host Binary)  │    Published Host Port      │   (Container)   │  │
│   │   (Port 80)     │         :8080               │   (Port 8080)   │  │
│   └─────────────────┘                             └─────────────────┘  │
└────────────────────────────────────────────────────────┘
```

#### Steps and Artifacts

1. **Configure `config.yaml`**:
   ```yaml
   http:
     port: 80
     https_port: 443

   service_discovery:
     catalogs:
       - enabled: true
         provider: "docker"
         socket_path: "/var/run/docker.sock"
         network_mode: "external"             # Host mapping mode
   ```

2. **Start the host binary**:
   ```bash
   ./litegate -c ./config.yaml
   ```

3. **Start your container, exposing ports to the host**:
   ```bash
   docker run -d \
     --name business-api \
     -p 8080:8080 \
     -l litegate.enable=true \
     -l litegate.http.routers.business.match.hosts=api.example.com \
     -l litegate.http.services.business.discovery.name=business-service \
     -l litegate.http.services.business.loadbalancer.server.port=8080 \
     my-business-app:latest
   ```
   LiteGate detects the container start event, resolves its host-bound port bindings (such as `127.0.0.1:8080`), and registers it as an active upstream.

> [!NOTE]
> **Container Host IP Fallback (`LITEGATE_DOCKER_HOST`)**:
> If LiteGate itself is containerized but running in `external` network mode, host port binding IPs are frequently reported by the engine as `0.0.0.0` or `::`.
> To prevent routing failure, LiteGate utilizes an intelligent fallback:
> 1. It checks the environment variables `LITEGATE_DOCKER_HOST` or `DOCKER_HOST_IP` for the host's real IP.
> 2. If missing, it scans `/proc/net/route` inside the container to parse the default gateway IP, utilizing it as the routing destination.

---

### Topology C: Docker Swarm Production Overlay

**Scenario**: An enterprise multi-node Docker Swarm cluster. LiteGate and business microservices are deployed as Swarm services on a shared overlay network, enabling flat, direct routing to individual Task instances.

```
                  ┌─────────────────────────────────┐
                  │       Swarm Overlay Network     │
                  │          (litegate-net)         │
                  └────────────────┬────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  litegate.1.task ├─────►│  mqserver.1.task ├─────►│  mqserver.2.task ├─────► ...
│    (Overlay IP)  │      │   (10.0.15.5)    │      │   (10.0.15.12)   │
└──────────────────┘      └──────────────────┘      └──────────────────┘
```

#### Steps and Artifacts

1. **Create an attachable overlay network**:
   ```bash
   docker network create --driver overlay --attachable litegate-net
   ```

2. **Use the maintained `deploy/swarm/stack.yml` example.** It runs LiteGate globally on labeled edge nodes with host-mode published ports, and puts the Docker socket behind a manager-side read-only Socket Proxy. LiteGate and the proxy share a dedicated internal `docker-api` overlay; business containers join only `litegate-net` and therefore cannot reach the Docker API. Keep the Docker catalog's `socket_path` empty so `DOCKER_HOST=tcp://docker-socket-proxy:2375` takes effect.

   The proxy enables only the Swarm endpoints used by this configuration (`EVENTS`, `INFO`, `SERVICES`, and `TASKS`); `CONTAINERS`, `NETWORKS`, and all POST requests remain disabled. Read-only does **not** mean non-sensitive: service and task responses can expose cluster topology and service configuration, so never attach untrusted workloads to `docker-api`.

3. **Deploy using the stack CLI**:
   ```bash
   docker stack deploy -c deploy/swarm/stack.yml saas-app
   ```

> [!IMPORTANT]
> **Swarm Security: Bypassing the Ingress Network**:
> Tasks inside a Docker Swarm have ingress endpoints (`10.255.x.x`) attached to map external traffic.
> Routing dynamic traffic to these ingress endpoints causes routing loop deadlocks. LiteGate **automatically filters out ingress interfaces**, resolving only the container overlay interfaces to establish healthy peer connections.
> Service discovery labels must be under `deploy.labels`; container-level `labels` are not read in Swarm mode. For ACME with multiple LiteGate replicas, enable `roles.cert_storage: true` in the Consul or Litemesh configuration so certificate state is stored in that shared control plane. It is a boolean role, not a filesystem path.

---

## Troubleshooting Guide

### 1. "Permission Denied" on `/var/run/docker.sock`
* **Cause**: The socket file on the host has restricted permissions (default is owned by root and readable by the docker group).
* **Fix**: Prefer passing the socket's group ID to the container:
  ```bash
  export DOCKER_GID=$(stat -c '%g' /var/run/docker.sock)
  docker compose up -d
  ```
  In production, prefer a restricted Docker Socket Proxy on a dedicated network accessible only to LiteGate. Read-only Docker metadata may still contain secrets and must not be exposed to business containers. Do not make the socket world-writable with `chmod 666`; direct Docker socket access is effectively host-level privilege.

### 2. Containers are Running but LiteGate Logs Do Not React
* **Checkpoints**:
  1. Verify the socket is correctly mounted and not a dead symlink inside the LiteGate container.
  2. Ensure your containers are started with valid labels matching the `litegate.` prefix via `docker inspect`.
  3. A Docker catalog's `namespace` scopes discovery requests; containers do not carry a namespace label. With multiple Docker catalogs, give each catalog a distinct namespace and reference that namespace from the consuming route/catalog configuration.

### 3. Connection Timeouts on Multi-NIC Containers
* **Cause**: Backend containers linked to multiple interfaces might not share every network with LiteGate.
* **Fix**:
  * Stamp your containers explicitly with the target interface selector label:
    ```bash
    -l litegate.docker.network=litegate-net
    ```
    This forces LiteGate to match the `litegate-net` interface. You can instead set catalog-level `swarm_network`; despite its legacy name, it also applies to standalone Docker. When LiteGate itself is containerized, a network shared by both containers is preferred automatically, and the final fallback is sorted for stable results.

When Service `discovery.name` is omitted, Compose containers are grouped as `<project>-<service>`; containers without both Compose labels fall back to the individual container name.

The image healthcheck reads the local `web` entrypoint by default. When the running gateway obtains its configuration from Consul or Litemesh, set `LITEGATE_HEALTH_ADDR` (for example `127.0.0.1:8080`) to the actual listener. `litegate healthcheck --addr ...` takes precedence over that environment variable, and an explicit `--config` takes precedence over `LITEGATE_CONFIG`.
