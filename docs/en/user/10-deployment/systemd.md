# Systemd Deployment Guide (Linux)

This guide documents how to install, register, and manage LiteGate as a systemd background daemon service on Linux systems to enable automated startup on boot and robust process monitoring.

---

## 1. Directory Setup & Binary Installation

```bash
# Copy compiled litegate binary to system bin path
sudo cp litegate /usr/local/bin/
sudo chmod +x /usr/local/bin/litegate

# Initialize default workspace directories
sudo mkdir -p /opt/litegate
sudo cp config.yaml /opt/litegate/
sudo mkdir -p /opt/litegate/{sites,streams,certs}
```

---

## 2. Declaring the Systemd Service File

### Option A: One-Command Auto-Generation (Recommended)

LiteGate includes a built-in `systemd --print` command that infers the current directory, executable path, and user, printing a production-ready unit file that can be piped directly into systemd:

```bash
# Navigate to your deployment directory (e.g. /home/litegate or /opt/litegate)
cd /opt/litegate

# Auto-infer environment paths and write unit file directly
litegate systemd --print | sudo tee /etc/systemd/system/litegate.service
```

> [!TIP]
> The auto-generated unit file automatically includes `AmbientCapabilities=CAP_NET_BIND_SERVICE`, enabling non-root users to bind privileged ports (80/443). You can also explicitly override parameters:
> `litegate systemd --user litegate --config /opt/litegate/config.yaml --print | sudo tee /etc/systemd/system/litegate.service`

### Option B: Manual Unit File Declaration

Alternatively, create the systemd configuration file manually at `/etc/systemd/system/litegate.service`:

```ini
[Unit]
Description=LiteGate - Cloud-Native API Gateway
Documentation=https://github.com/jamesleeon/LiteGate
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/litegate -config /opt/litegate/config.yaml
WorkingDirectory=/opt/litegate
Restart=always
RestartSec=5
LimitNOFILE=65535

# Security hardening & Sandbox rules
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/opt/litegate/certs /opt/litegate/sites

# Logging and Telemetry redirection
StandardOutput=journal
StandardError=journal
SyslogIdentifier=litegate

[Install]
WantedBy=multi-user.target
```

### Security Hardening Parameters:
* **`LimitNOFILE=65535`**: Explicitly increases the maximum file descriptor limits for this specific systemd process.
* **`NoNewPrivileges=true`**: Prevents child processes from gaining more privileges than the parent process.
* **`ProtectSystem=strict`**: Mounts the entire OS file directory tree as read-only to sandbox the process, declaring exclusive write permissions solely to `ReadWritePaths` directories.

---

## 3. Starting the Daemon Service

```bash
# Reload systemd configuration files
sudo systemctl daemon-reload

# Enable automated system startup on boot
sudo systemctl enable litegate

# Start the gateway daemon immediately
sudo systemctl start litegate

# Audit daemon execution status
sudo systemctl status litegate

# Inspect real-time gateway journal streams
sudo journalctl -u litegate -f
```

---

## 4. Binding Privileged Ports (Best Practices)

To listen on privileged ports below 1024 (such as HTTP port 80 or HTTPS port 443) without executing the binary as the `root` user, assign Linux kernel networking capabilities to the executable:

```bash
sudo setcap 'cap_net_bind_service=+ep' /usr/local/bin/litegate
```

---

## 5. Rolling Upgrades & Maintenance

```bash
# Terminate active daemon processes gracefully
sudo systemctl stop litegate

# Overwrite the physical binary file
sudo cp litegate-new /usr/local/bin/litegate
sudo chmod +x /usr/local/bin/litegate

# Restart the daemon service
sudo systemctl start litegate
```

> [!TIP]
> Dynamic L7 router configurations (such as files added or edited within `sites/*.yaml`) do not require restarting or reloading the systemd service. LiteGate dynamically monitors and hot-reloads these directory changes.
