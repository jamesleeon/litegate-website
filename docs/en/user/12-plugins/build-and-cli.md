# Plugin Builds and the Management CLI

LiteGate plugins are compiled in, so third-party plugins must be built into a LiteGate binary. LiteGate offers two complementary ways to do that.

---

## Method 1: the `litegate build` command (recommended)

`litegate build` generates a temporary `main.go` and `go.mod` that blank-import the plugins you list, then runs the Go toolchain you have installed to produce a custom binary. You don't need to maintain a gateway entry program of your own.

### 1. Common build scenarios

#### A. Plugins published in public/private Git repositories

```bash
litegate build \
  --with github.com/acme/litegate-jwt-auth@v1.2.0 \
  --with github.com/acme/litegate-nacos-discovery@v0.5.1 \
  -o custom-litegate
```

> [!TIP]
> For private Git repositories, make sure the machine has the standard Go environment variables (such as `GOPRIVATE=github.com/acme/*`); the builder reuses your local Git credentials.

#### B. Local development (local directory replacement)

While developing a plugin you don't need to commit and tag first; map the package path to local code with `=<local_path>`:

```bash
litegate build \
  --with github.com/acme/litegate-plugin=../my-plugin-repo \
  -o custom-litegate
```

When the plugins live in one project with several sub-packages, list them in the same command:

```bash
litegate build \
  --with mycompany/plugins/action/ai=./my-plugins \
  --with mycompany/plugins/middleware/tenant=./my-plugins \
  -o custom-litegate
```

#### C. Pinning or replacing the LiteGate core

To build against a specific LiteGate core branch or a local LiteGate source tree:

```bash
# Replace the LiteGate core with a local development copy
litegate build \
  --replace github.com/jamesleeon/LiteGate=/path/to/LiteGate \
  --with github.com/acme/my-plugin@v1.0.0 \
  -o custom-litegate
```

### 2. All `litegate build` options

| Option | Description | Example |
| :--- | :--- | :--- |
| `--with <package[@version][=replacement]>` | Add a plugin package; repeatable. `=replacement` points to a local plugin module directory. | `--with github.com/foo/bar@v1.0.0` |
| `--dns <[type=]provider[@version]>` | Compile in a libdns (v1 API) DNS provider. A short name means `github.com/libdns/<name>`; a full module path is also accepted; `type` defaults to the last path element. Repeatable. | `--dns huaweicloud --dns route53` |
| `--replace <module[@version]=target[@version]>` | Add a Go module replacement; repeatable. The legacy form `--replace <path>` replaces the LiteGate core with a local source tree. | `--replace github.com/foo/bar=../bar` |
| `--litegate-version <v>` | Select and lock the LiteGate core module version. | `--litegate-version v0.4.2` |
| `-o, --output <path>` | Output binary path; default `./litegate` (`litegate.exe` on Windows). | `-o /usr/local/bin/litegate` |
| `--keep-workdir` | Keep the generated temporary module for dependency diagnostics. | `--keep-workdir` |
| `--tags <tags>` | Go build tags. | `--tags wasmids` |
| `--race` | Enable Go's race detector. | `--race` |
| `--debug` | Disable compiler optimizations and inlining for debuggers. | `--debug` |
| `--no-trimpath` | Keep local filesystem paths in the binary (stripped by default). | `--no-trimpath` |

Related environment variables: `LITEGATE_VERSION`, `LITEGATE_LOCAL_PATH`, `LITEGATE_GO`, `LITEGATE_BUILD_KEEP_WORKDIR`, `GOOS`, `GOARCH`, `GOARM`, `CGO_ENABLED`.

---

## Method 2: your own `main.go` with blank imports

If you use LiteGate as the base of an in-house gateway and want one repository to manage custom logic and dependencies, write your own `main.go`:

### 1. Create a Go project

```bash
mkdir my-gateway && cd my-gateway
go mod init my-gateway
go get github.com/jamesleeon/LiteGate
```

### 2. Blank-import plugins in `main.go`

```go
package main

import (
	"log"

	// 1. Blank-import your own plugin packages (their init() registers them)
	_ "my-gateway/plugins/custom_audit"
	_ "my-gateway/plugins/ldap_auth"

	// 2. Import plugins shipped in the standard LiteGate distribution as needed
	_ "github.com/jamesleeon/LiteGate/pkg/plugins/nats"
	_ "github.com/jamesleeon/LiteGate/pkg/plugins/forwardproxy"

	// 3. Start the LiteGate core
	"github.com/jamesleeon/LiteGate/pkg/litegate"
)

func main() {
	if err := litegate.Run(); err != nil {
		log.Fatalf("Gateway exited with error: %v", err)
	}
}
```

### 3. Build with plain `go build`

```bash
go build -o my-gateway .
```

---

## Plugin management and diagnostics CLI

LiteGate has built-in CLI commands to audit, self-check and debug the plugins in a binary:

### 1. `litegate plugins list` — list compiled plugins

Shows every plugin registered through the public API in the current binary: extension kind, plugin name, plugin version and the LiteGate API version it follows:

```bash
litegate plugins list
```

**Sample output (default build):**
```text
KIND             NAME                             VERSION        API
action           nats                             1.0.0          v1
discovery        nomad                            0.1.0          v1
ids              openapi-md5                      1              v1
ingress          forward_proxy                    0.3.0          v1
middleware       forward_auth                     0.1.0          v1
```

Structured JSON output for release pipelines:

```bash
litegate plugins list --json
```

### 2. `litegate plugins inspect` — metadata and configuration template

Shows a plugin's metadata: display name, description, capabilities and a **ready-to-use YAML configuration template**:

```bash
litegate plugins inspect ingress/forward_proxy
```

**Sample output (excerpt):**
```text
Kind: ingress
Name: forward_proxy
Version: 0.3.0
Plugin API: v1
Display name: HTTP forward proxy
Description: HTTP forward proxy with authenticated HTTP/1.1, HTTP/2 and HTTP/3 CONNECT and destination ACLs.
Capabilities: connect, destination_acl, http1, http2, http3, probe_resistance, proxy_auth
Configuration example:
# Global config; generate a hash with litegate -hash 'your-password'.
ingress_plugins:
  - name: forward-proxy
    type: forward_proxy
    entrypoints: [websecure]
    config:
      hosts: [proxy.example.com]
      username: user
      password: '$2a$10$REPLACE_WITH_COMPLETE_BCRYPT_HASH'
      probe_resistance: true
      allowed_destinations: ["*"]
      allowed_ports: [80, 443]
```

### 3. `litegate plugins doctor` — health and compatibility check

Before deploying a custom binary to production, run `doctor` to catch problems early:

```bash
litegate plugins doctor
```

`doctor` checks:
- **Manifest completeness**: every plugin compiled in declares a unified `Manifest`.
- **APIVersion compatibility**: the `APIVersion` each plugin claims (such as `v1`) matches what the gateway expects.
- **Configuration example safety**: each plugin's `ConfigExample` is valid, with no unescaped characters or oversized data.

---

## Viewing plugins in the Dashboard

LiteGate's built-in Dashboard shows compiled plugins:

1. Open the LiteGate Dashboard (default `http://<gateway address>:9999/status`; the port comes from `dashboard.port`).
2. Click **Compiled Plugins** in the navigation.
3. Action, Middleware, Discovery, DNS and other plugins are shown as cards by kind, with configuration templates you can copy.

---

## CI/CD build example (Dockerfile)

A standard multi-stage Dockerfile that builds a small image with in-house plugins:

```dockerfile
# Stage 1: custom build in the official Go image
FROM golang:1.27-alpine AS builder

WORKDIR /build

# Basic build dependencies
RUN apk add --no-cache git ca-certificates tzdata

# Install the LiteGate tool, which provides litegate build
RUN go install github.com/jamesleeon/LiteGate/cmd/litegate@latest

# Inject private plugins with litegate build
RUN litegate build \
    --with github.com/acme/litegate-plugin-auth@v1.0.0 \
    --with github.com/acme/litegate-plugin-discovery@v0.2.0 \
    -o /build/litegate

# Stage 2: minimal runtime image
FROM alpine:3.20

RUN apk add --no-cache ca-certificates tzdata

WORKDIR /app

# Copy the single static binary from the build stage
COPY --from=builder /build/litegate /usr/local/bin/litegate

# Default volumes and configuration mount points
VOLUME ["/app/config.yaml", "/app/sites", "/app/certs"]

EXPOSE 80 443

ENTRYPOINT ["litegate"]
CMD ["-config", "/app/config.yaml"]
```
