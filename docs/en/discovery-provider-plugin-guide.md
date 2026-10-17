# Developing a Discovery Plugin: the Nomad Example

Follow the complete workflow: **develop → register → compile into LiteGate → deploy and configure → verify**. Nomad is a working reference. A Nacos provider can reuse this structure, but needs its own registry queries, authentication and subscriptions.

Read the complete [Nomad implementation](../../pkg/plugins/nomad/nomad.go), [tests](../../pkg/plugins/nomad/nomad_test.go), and [public contract](../../pkg/plugin/discovery.go). Go snippets below are simplified excerpts, not standalone compilable files.

## 1. Create a plugin and define responsibilities

An external plugin is an independent Go module using public `pkg/plugin`, never LiteGate's `internal` packages. Suggested files are `provider.go` (client and queries), `register.go` (registration), `provider_test.go`, and a user configuration README.

Use a Go toolchain and SDK compatible with the target LiteGate. Pin production dependencies. For local development in the plugin module, run `go mod edit -replace github.com/jamesleeon/LiteGate=../LiteGate`, then `go get github.com/jamesleeon/LiteGate`, adjusting the sibling source path.

For example, run these commands from the parent of the LiteGate source directory to create an independent plugin module:

```bash
mkdir litegate-discovery-nacos
cd litegate-discovery-nacos
go mod init example.com/acme/litegate-discovery-nacos
go mod edit -replace github.com/jamesleeon/LiteGate=../LiteGate
go get github.com/jamesleeon/LiteGate
```

Use your plugin's package name in source files, such as `package nacos`. Replace the placeholder `example.com/acme` with your real repository path when publishing.

The plugin supplies services and instances. LiteGate validates and copies endpoints, filters selectors, parses tags, merges sources, creates routes and balances traffic. Do not access the Router or connection pools directly.

## 2. Implement listing and resolution

The minimum contract has two methods:

```go
type DiscoveryProvider interface {
    ListServices(ctx context.Context) ([]plugin.DiscoveredService, error)
    Resolve(ctx context.Context, query plugin.DiscoveryQuery) ([]plugin.DiscoveredEndpoint, error)
}
```

Nomad's `ListServices` queries `/v1/services` and returns `DiscoveredService{Name, Namespace, Tags}`. Its `Resolve` queries `/v1/service/:service_name` using `query.Namespace` and maps registrations:

```go
result = append(result, plugin.DiscoveredEndpoint{
    ID: value.ID, Address: value.Address, Port: value.Port,
    Weight: 1, Healthy: true, Protocol: p.protocol,
    ServiceName: value.ServiceName, Namespace: value.Namespace,
    Tags: value.Tags,
    Metadata: map[string]string{"nomad.alloc_id": value.AllocID},
})
```

`Address` has no URL scheme, `Port` is the actual reachable port, and `Protocol` is separate. Nomad's `Healthy: true` means eligibility for selection: the registration API supplies no application checks and does not prove readiness. Map other registries' actual health semantics and use LiteGate active checks as needed.

Implementation rules:

- Calls may be concurrent. Returned slices, Tags and Metadata must be snapshots that are not mutated afterward.
- Return the actual namespace. Catalog prefers it, otherwise falling back to the outer Catalog namespace or `default`.
- Honor contexts, bounded timeouts and complete pagination. Errors must remain errors; successful empty results remove instances, while errors retain the last successful snapshot.
- Expose `litegate.*` route declarations through Tags or appropriate Metadata for the host to parse.
- Define supported query fields and reject unsupported selectors. Nomad rejects job port-label `PortName` selection.
- `Validate` performs pure configuration checks without networking; the Factory constructs a client. Never log tokens or credential-bearing API error bodies.

Nomad's `parse`, `New` and `get` demonstrate strict fields, token-file rotation, TLS/mTLS, timeouts, response limits and protection against incomplete paginated snapshots.

## 3. Register the Provider and Dashboard metadata

Register from the plugin package's `init()`. The complete Nomad implementation defines `parse`, `New` and `configExample` used here:

```go
func init() {
    if err := plugin.RegisterManifest(plugin.Manifest{
        Kind: "discovery", Name: "nomad", Version: "0.1.0",
        APIVersion: plugin.APIVersion, DisplayName: "Nomad",
        Capabilities: []string{"namespace", "tags", "metadata"},
        ConfigExample: configExample,
    }); err != nil {
        panic(err)
    }
    if err := plugin.RegisterDiscoveryProvider("nomad", plugin.DiscoveryRegistration{
        Validate: func(config map[string]string) error {
            _, err := parse(config)
            return err
        },
        Factory: func(config map[string]string, _ *plugin.Dependencies) (plugin.DiscoveryProvider, error) {
            return New(config)
        },
        Info: plugin.DiscoveryProviderInfo{
            Name: "nomad", DisplayName: "Nomad",
            SupportsNamespace: true, SupportsTags: true, SupportsMetadata: true,
            RequiredConfig: []plugin.DiscoveryConfigField{
                {Name: "address", Required: true, Description: "Nomad HTTP API URL"},
            },
        },
    }); err != nil {
        panic(err)
    }
}
```

Keep registration, `Info.Name` and Manifest names consistent, avoid reserved built-in types, and handle duplicate registration errors. The full implementation also describes optional fields using `OptionalConfig`. `Dependencies` provides host logging, discovery and shared configuration capabilities.

No outbound Dashboard registration request is required. Manifest supplies version, capabilities and copyable YAML under **Plugins → Service Discovery**. An enabled Catalog whose instance was constructed appears under **Control Plane Providers** on the overview. Keep `ConfigExample` aligned with supported fields and use placeholder credentials.

## 4. Choose polling or subscriptions and release resources

A minimal plugin can rely on host scans. Nomad currently uses the initial scan and subsequent 30-second Catalog scans, without Watch.

For subscriptions, implement `DiscoveryWatcher.Watch(ctx, notify)`: update the local snapshot before notifying and block until cancellation or an unrecoverable error. Advertising `SupportsWatch: true` requires this interface. Notifications are coalesced into Catalog rescans, without service-scoped deltas.

When Watch returns an error, returns early or panics, the host restarts it with exponential backoff (1s up to 30s) and triggers a rescan on each restart; prefer returning the error and letting the host restart, so the Dashboard watch state reflects the failure; retrying silently inside the plugin leaves the watch reported as healthy while notifications are dead. Cover changes to existing instances, addresses and health as well as service-name additions/removals. Optional `Start(ctx)` currently receives a Background context, so bound initialization yourself. If you create workers, `Close(ctx)` must cancel and join them. Nomad's only background work is the Watch long poll, which exits with its ctx; Close only closes idle HTTP connections.

## 5. Compile the plugin into the system

### Build the existing Nomad plugin

From the repository root:

```bash
go build -o litegate-nomad ./cmd/litegate
./litegate-nomad plugins inspect discovery/nomad
```

`cmd/litegate/plugins.go` already blank-imports Nomad. Do not copy it and register the same name twice. On Windows, use an output name such as `litegate-nomad.exe`.

### Build an independent third-party plugin

The Nacos package below is a placeholder: implement the local plugin or publish the version first. The first command is for local development; the second pins a published version:

```bash
litegate build --with example.com/acme/litegate-discovery-nacos=../litegate-discovery-nacos --replace ../LiteGate -o litegate-custom
litegate build --with example.com/acme/litegate-discovery-nacos@v0.1.0 -o litegate-custom
```

The local plugin replacement must contain its own `go.mod`. `--replace ../LiteGate` selects local core source; adjust paths as needed. Building requires a Go toolchain and dependency access.

Alternatively, create a main in your own module, blank-import the plugin and call LiteGate's entry point:

```go
package main

import (
    "log"
    "github.com/jamesleeon/LiteGate/pkg/litegate"
    _ "example.com/acme/litegate-discovery-nacos"
)

func main() {
    if err := litegate.Run(); err != nil {
        log.Fatal(err)
    }
}
```

This main explicitly imports only the example plugin; import any other external plugins your configuration requires. Adding Go plugins requires rebuilding and deploying, not hot installation. See [Build and CLI](user/12-plugins/build-and-cli.md).

## 6. Deploy, configure and use

Deploy the resulting binary as the running LiteGate and mount configuration, token and CA files. Example global `config.yaml` for Nomad:

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
```

`provider` must match the registration name. Only the inner `config` reaches the Factory; the outer namespace is a Catalog fallback, not the plugin's API scope. The token file must be readable from the LiteGate process.

Next register the application service in Nomad and declare routes through `litegate.*` Tags. Follow the [Nomad user configuration guide](user/07-discovery/nomad.md) for all fields, job configuration, DNS, ACL/TLS, health limitations and troubleshooting.

```bash
./litegate-nomad plugins inspect discovery/nomad
./litegate-nomad plugins doctor
./litegate-nomad -config config.yaml -t
./litegate-nomad -config config.yaml
```

CLI inventory and configuration checks do not prove connectivity. Verify listing, route creation and real requests, then scaling, deregistration, outages and recovery. Unit tests should cover token/TLS, namespace isolation, successful empty results, errors and cancellation. Run the reference tests with `go test ./pkg/plugins/nomad ./internal/status`.

## 7. Adapt the pattern to Nacos

| Step | Reusable structure | Registry-specific work |
| :--- | :--- | :--- |
| Listing | ListServices returns the catalog | Target SDK/API version, authentication, pagination, namespace/group |
| Instances | Resolve returns Endpoints | Actual address/port, stable ID, weight, health and enabled state |
| Metadata | Common Tags/Metadata parsing | Mapping registration metadata to `litegate.*` and conflict rules |
| Updates | Watch and lifecycle interfaces | SDK subscriptions, snapshot synchronization, reconnects, cancellation and cleanup |
| Integration | Registration, Manifest, build, Catalog, Dashboard | Unique `nacos` name, validation and user examples |

Reuse the structure, rather than just replacing a name and URL. Define how groups are represented and namespaces mapped, then test health and subscription behavior. This guide does not implement Nacos; verify SDK/API behavior against the target deployment version.
