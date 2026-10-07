# Installation Guide

LiteGate is a lightweight, high-performance cloud-native gateway supporting multiple installation methods.

## System Requirements

- **Operating System**: Linux, Windows, macOS
- **Architecture**: amd64, arm64
- **Go Version**: 1.21+ (Only required for building from source)

---

## Installation Methods

### Method 1: Download Precompiled Binaries

Visit the [GitHub Releases](https://github.com/jamesleeon/LiteGate/releases) page to download the latest version.

#### Linux (amd64/arm64)
```bash
# Decompress the package
tar -xzf litegate-linux-amd64.tar.gz
# Move to system path
sudo mv litegate /usr/local/bin/
# Verify installation
litegate --version
```

#### Windows
```powershell
# Decompress and add litegate.exe to your PATH environment variable
litegate --version
```

### Method 2: Using Docker (Recommended)

```bash
# Run the Docker container
docker run -d \
  --name litegate \
  -p 80:80 \
  -p 443:443 \
  -v $(pwd)/sites:/app/sites \
  -v $(pwd)/certs:/app/certs \
  jamesleeon/litegate:latest
```

### Method 3: Docker Compose

Create a `docker-compose.yaml` file:

```yaml
version: '3.8'
services:
  litegate:
    image: jamesleeon/litegate:latest
    container_name: litegate
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "9999:9999" # Dashboard entrypoint
    volumes:
      - ./sites:/app/sites
      - ./certs:/app/certs
      - ./config.yaml:/app/config.yaml
```

---

## First Run

### Zero-Configuration Startup
LiteGate supports plug-and-play out of the box. Simply run the command to launch the default gateway configuration:

```bash
litegate
```

**Default Behavior**:
- Automatically listens on port 80 and 443.
- Scans the `./sites` folder in the current directory and loads site files.
- Automatically stores and manages SSL certificates in `./certs`.
- The Admin Dashboard is **off by default**; enable it with `dashboard.enabled: true` (then it runs at `http://localhost:9999`).

### Startup with a Custom Configuration File
If you need custom Litemesh integration or advanced security settings, specify a config file:

```bash
litegate --config config.yaml
```

---

## Verifying the Installation

### 1. Check the Process
```bash
ps aux | grep litegate
```

### 2. Access the Admin Dashboard (if enabled)
With `dashboard.enabled: true` in `config.yaml`, open `http://localhost:9999`.
- **Username**: set via `dashboard.username` (default `admin`).
- **Password**: generate a hash with `litegate -hash "your-password"` and put the result in `dashboard.password`.

### 3. Health Check
```bash
curl http://localhost/health
```

---

## Directory Structure

Recommended working directory structure for LiteGate:

```text
litegate/
├── litegate              # Executable binary
├── config.yaml           # Global configuration file
├── sites/                # HTTP site configurations (v1/*.yaml)
├── streams/              # Layer 4 proxy configurations (TCP/UDP)
└── certs/                # Automatic certificate store
```

---

## Troubleshooting

### Port Conflict
If port 80/443 is already occupied by Nginx or another service, change the `http.port` setting in `config.yaml`.

### Insufficient Privileges (Linux)
Listening on ports below 1024 requires root/administrator privileges. You can grant privileges to the binary using:
```bash
sudo setcap 'cap_net_bind_service=+ep' /usr/local/bin/litegate
```
