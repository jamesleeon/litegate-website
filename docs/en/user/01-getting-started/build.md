# Build Guide (Build from Source)

This guide describes how to compile LiteGate from source.

---

## 1. Prerequisites

- **Go**: 1.22 or higher version
- **Git**: For cloning the source code
- **Make**: (Optional) For shortcut compiling

---

## 2. Clone the Code

```bash
git clone https://github.com/jamesleeon/LiteGate.git
cd LiteGate
```

---

## 3. Compile

### Method 1: Direct Build

```bash
go mod download
go build -ldflags="-s -w" -o bin/litegate ./cmd/litegate
```

### Method 2: Cross Compilation

```bash
# Linux AMD64
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o bin/litegate-linux-amd64 ./cmd/litegate

# Linux ARM64 (Raspberry Pi, etc.)
CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -ldflags="-s -w" -o bin/litegate-linux-arm64 ./cmd/litegate

# Windows
CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -ldflags="-s -w" -o bin/litegate.exe ./cmd/litegate
```

---

## 4. Docker Build

```bash
docker build -t litegate:latest .
```

The Dockerfile uses multi-stage builds. The final image is based on Alpine, containing only the binary executable and CA certificates.

---

## 5. Running Tests

```bash
# Run all unit tests
go test ./...

# Run tests in specific modules
go test ./internal/router/...
go test ./internal/action/...
```

---

## 6. Project Directory Structure

```text
litegate/
├── cmd/
│   ├── litegate/        # Main Entrypoint
│   └── tools/           # Auxiliary Utilities
│       └── jwt_gen/      # JWT Token generator
├── internal/            # Core Business Logic (Encapsulated)
│   ├── action/          # Action Handlers (proxy, serve, webdav...)
│   ├── auth/            # OIDC/OAuth2 Authentication
│   ├── cert/            # DNS Provider implementation
│   ├── certmanager/     # ACME SSL Certificate management
│   ├── config/          # Configuration models and loaders
│   ├── ddns/            # Auto Dynamic DNS sync
│   ├── discovery/       # Service discovery and load balancing
│   ├── health/          # Health check endpoint
│   ├── loader/          # Site/Stream dynamic loader
│   ├── mcp/             # MCP (Model Context Protocol) Server
│   ├── middleware/      # Middlewares (WAF, Auth, CORS, Rate Limit...)
│   ├── proxy/           # Backend Connection pool & WebSocket proxy
│   ├── router/          # High performance Trie routing engine
│   ├── status/          # Admin Dashboard & Control APIs
│   └── webhook/         # Webhook logger & Alert notifier
├── pkg/                 # Reusable public packages
├── scripts/             # Script files and examples
├── docs/                # Documentations
├── sites/               # Site config examples
├── streams/             # Stream L4 proxy config examples
└── certs/               # SSL certificate storage
```
