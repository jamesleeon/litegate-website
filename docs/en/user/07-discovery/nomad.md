# Nomad Service Discovery

The Nomad plugin reads native Nomad service registrations directly. Tags generate LiteGate routes and upstream pools without a LiteDNS discovery agent. The Nomad job must use `provider = "nomad"`; services using `provider = "consul"` should use [Consul discovery](consul.md).

Developers should start with [Developing a Discovery Plugin: the Nomad Example](../../discovery-provider-plugin-guide.md), covering implementation, registration, compilation and user configuration in order. This page is the detailed configuration reference for deployment users.

## 1. Check plugin availability

The standard `cmd/litegate` binary includes the plugin. After deploying the updated binary, run:

```bash
litegate plugins inspect discovery/nomad
```

The output should contain `Name: nomad`. A custom main must blank-import `github.com/jamesleeon/LiteGate/pkg/plugins/nomad` and rebuild. Configuration alone cannot install a plugin into an older binary. See [Plugin build and CLI](../12-plugins/build-and-cli.md).

## 2. Configure global config.yaml

```yaml
service_discovery:
  catalogs:
    - name: nomad-prod
      enabled: true
      provider: nomad
      namespace: default
      config:
        address: "https://nomad.example.com:4646"
        namespace: "default"
        token_file: "/run/secrets/nomad-token"
        region: "global"
        # ca_file: "/etc/nomad/ca.pem"
        # cert_file: "/etc/nomad/client.pem"
        # key_file: "/etc/nomad/client-key.pem"
        # timeout: "10s"
        # protocol: "http"
```

Replace the API address and region. Mount the token file into the **LiteGate process or container**. The file contains only the token text, without an `X-Nomad-Token:` prefix. It is read for every request, supporting file-based rotation. When ACLs are enabled, grant service read access in the target namespaces; the plugin does not write to Nomad.

The outer `name` identifies the LiteGate discovery instance, not a Nomad job or service. `config.address` is the Nomad API endpoint. The plugin does not consume the Catalog's outer `url` or `token` as connection parameters.

### Configuration fields

All fields below belong under `catalogs[].config` and use string values. Unknown fields are rejected.

| Field | Default | Meaning |
| :--- | :--- | :--- |
| `address` | Required | HTTP/HTTPS API URL; URL credentials, query parameters and fragments are rejected |
| `namespace` | `default` | Nomad API scope; `"*"` lists namespaces authorized for the token |
| `region` | Nomad agent's region | API region; replace the example `global` with the deployment's region |
| `token_file` | None | Token file path; mutually exclusive with `token` |
| `token` | None | Inline ACL token; do not commit real tokens to source control |
| `ca_file` | System trust store | Additional PEM CA bundle for private Nomad server certificates |
| `cert_file` | None | PEM mTLS client certificate; requires `key_file`; reloaded when the files change |
| `key_file` | None | PEM mTLS client private key |
| `timeout` | `10s` | Positive HTTP request timeout, such as `"5s"` |
| `protocol` | `http` | Backend protocol: `http`, `https`, `h2c`, `grpc`, `grpcs`, `tcp`, `tls`, or `udp` |

HTTPS in `address` secures the Nomad API connection; `protocol` selects the application backend protocol independently. HTTP API connections do not encrypt tokens; use HTTPS in production. Server certificate verification is enabled and cannot be skipped.

### Namespaces and multiple clusters

**The outer `namespace` does not reach the plugin Factory and cannot replace `config.namespace`.** It is a Catalog fallback; the service's returned namespace takes precedence. For `prod`, set `config.namespace: "prod"` and preferably set the outer namespace to `prod` as well.

Use `config.namespace: "*"` for discovery across authorized namespaces. Instance resolution then uses each service's concrete namespace. For multiple Nomad clusters, create separate catalogs with distinct names, API addresses and credentials. Services sharing a name and namespace can be merged across sources; use distinct namespaces or service names when isolation is required.

## 3. Register a Nomad service and declare a route

Define a network port and a service in an existing task group. Place this fragment inside the group, and configure the application task to use the `http` port label:

```hcl
network {
  port "http" {
    to = 8080
  }
}

service {
  name         = "orders"
  provider     = "nomad"
  port         = "http"
  address_mode = "host"
  tags = [
    "litegate.http.host=orders.example.com",
    "litegate.http.path_prefix=/"
  ]
}
```

Replace `8080` with the application port and configure the task for its Nomad driver and network mode. LiteGate uses the registered `Address` and actual numeric `Port`, including dynamically assigned host ports. These endpoints must be reachable from LiteGate. Point DNS for `orders.example.com` at the LiteGate ingress, not the Nomad API.

Tags use LiteGate's common tag parser; this example generates a hostname route. Do not define the same route again through site YAML or another tag model. See [Tag DSL](../03-configuration/tag-dsl.md). `protocol` only selects the backend protocol; TCP/UDP entrypoints and routes require separate configuration.

Endpoint metadata includes `nomad.job_id`, `nomad.alloc_id`, `nomad.node_id`, and `nomad.datacenter`. The registration API does not return job port labels, so `port_name` selection is unsupported. Register separate service names for multiple ports.

## 4. Updates, health and Dashboard

- The plugin long-polls `/v1/services` with Nomad blocking queries; any registration change (scaling, removal, address/port/tag change) triggers a Catalog rescan immediately. The 30-second periodic Catalog scan remains as a fallback. A failed blocking query ends Watch with its error, so the Dashboard shows the watch as failed with the reason; the host then restarts it with backoff and rescans.
- Successful empty responses remove registrations. API errors retain the host's last successful snapshot, currently without a maximum stale age.
- Registration presence means eligibility for backend selection, not application readiness. The plugin does not query Nomad checks or Allocation health. Configure LiteGate active health checks when application readiness is required.
- Find Nomad and configured instances under **Plugins** in the Dashboard. **Control Plane Providers** on the overview shows runtime status. A newly loaded instance may show Active before its first query; use the last-success timestamp, errors and logs to assess connectivity. API failures show Degraded.

## 5. Troubleshooting

| Symptom | Check |
| :--- | :--- |
| `unregistered provider` | Whether the running binary includes Nomad and the updated build was deployed |
| HTTP 403 | Token validity and read permission for the target namespace |
| Certificate or connection error | API address, CA, mTLS files, network and timeout; do not confuse application and API ports |
| No services found | Job provider must be `nomad`; verify region and `config.namespace` |
| Discovery succeeds but requests fail | Registered address/dynamic port reachability, backend protocol, application readiness, and DNS pointing at LiteGate |
| Removed instances remain visible | Allow the next scan; persistent API failures can retain stale snapshots, so check Degraded status |

[Discovery overview](overview.md) · [Plugin overview](../12-plugins/README.md)
