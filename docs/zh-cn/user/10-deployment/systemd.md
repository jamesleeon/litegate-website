# Systemd 部署指南 (Linux)

本指南介绍如何在 Linux 系统中将 LiteGate 安装为 systemd 服务，实现开机自启和进程守护。

---

## 1. 安装二进制文件

```bash
# 下载或编译 litegate
sudo cp litegate /usr/local/bin/
sudo chmod +x /usr/local/bin/litegate

# 创建工作目录
sudo mkdir -p /opt/litegate
sudo cp config.yaml /opt/litegate/
sudo mkdir -p /opt/litegate/{sites,streams,certs}
```

---

## 2. 创建 Systemd 服务文件

### 方式 A：一键自动生成（推荐）

LiteGate 提供了内置的 `systemd --print` 辅助命令，可自动根据当前运行目录、二进制路径与系统用户生成配置，并通过管道直接写入 systemd 目录：

```bash
# 进入你的部署目录（例如 /home/litegate 或 /opt/litegate）
cd /opt/litegate

# 自动推断当前路径与用户，并写入 service 文件
litegate systemd --print | sudo tee /etc/systemd/system/litegate.service
```

> [!TIP]
> `litegate systemd` 会自动配置 `AmbientCapabilities=CAP_NET_BIND_SERVICE`，允许以普通非 root 用户直接监听 80/443 等特权端口。如需显式指定用户或配置文件，可追加参数：
> `litegate systemd --user litegate --config /opt/litegate/config.yaml --print | sudo tee /etc/systemd/system/litegate.service`

### 方式 B：手动创建服务文件

你也可以手动创建 `/etc/systemd/system/litegate.service`：

```bash
sudo cat > /etc/systemd/system/litegate.service << 'EOF'
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

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/opt/litegate/certs /opt/litegate/sites

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=litegate

[Install]
WantedBy=multi-user.target
EOF
```

---

## 3. 启用并启动

```bash
# 重新加载 systemd
sudo systemctl daemon-reload

# 启用开机自启
sudo systemctl enable litegate

# 启动服务
sudo systemctl start litegate

# 查看状态
sudo systemctl status litegate

# 查看日志
sudo journalctl -u litegate -f
```

---

## 4. 端口权限

如果需要监听 80/443 等特权端口，推荐使用 `setcap` 而非以 root 运行：

```bash
sudo setcap 'cap_net_bind_service=+ep' /usr/local/bin/litegate
```

---

## 5. 更新/重启

```bash
# 停止服务
sudo systemctl stop litegate

# 替换二进制文件
sudo cp litegate-new /usr/local/bin/litegate

# 重新启动
sudo systemctl start litegate
```

> [!TIP]
> 站点配置文件 (`sites/*.yaml`) 的修改不需要重启服务，LiteGate 会自动检测并热加载。
