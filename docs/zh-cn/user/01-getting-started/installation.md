# 安装指南

LiteGate 是一个轻量级、高性能的云原生网关，支持多种安装方式。

## 系统要求

- **操作系统**: Linux, Windows, macOS
- **架构**: amd64, arm64
- **Go 版本**: 1.21+ (仅源码编译需要)

---

## 安装方式

### 方式一：下载预编译二进制文件

访问 [GitHub Releases](https://github.com/jamesleeon/LiteGate/releases) 下载最新版本。

#### Linux (amd64/arm64)
```bash
# 解压
tar -xzf litegate-linux-amd64.tar.gz
# 移动到系统路径
sudo mv litegate /usr/local/bin/
# 验证
litegate --version
```

#### Windows
```powershell
# 解压并将 litegate.exe 添加到 PATH 环境变量
litegate --version
```

### 方式二：使用 Docker (推荐)

```bash
# 运行容器
docker run -d \
  --name litegate \
  -p 80:80 \
  -p 443:443 \
  -v $(pwd)/sites:/app/sites \
  -v $(pwd)/certs:/app/certs \
  jamesleeon/litegate:latest
```

### 方式三：Docker Compose

创建 `docker-compose.yaml`:

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
      - "9999:9999" # Dashboard 入口
    volumes:
      - ./sites:/app/sites
      - ./certs:/app/certs
      - ./config.yaml:/app/config.yaml
```

---

## 首次运行

### 零配置启动
LiteGate 支持即插即用，直接运行即可启动默认网关功能：

```bash
litegate
```

**默认行为**：
- 自动监听 80 和 443 端口。
- 扫描当前目录下的 `./sites` 文件夹并加载站点。
- 自动管理证书存储在 `./certs`。
- Dashboard **默认关闭**;用 `dashboard.enabled: true` 开启后运行在 `http://localhost:9999`。

### 指定配置文件启动
如果你需要自定义 Litemesh 集成或高级安全设置：

```bash
litegate --config config.yaml
```

---

## 验证安装

### 1. 检查进程
```bash
ps aux | grep litegate
```

### 2. 访问控制台(需先开启)
在 `config.yaml` 里设置 `dashboard.enabled: true` 后,打开浏览器访问 `http://localhost:9999`。
- **用户名**: 通过 `dashboard.username` 设置(默认 `admin`)。
- **密码**: 用 `litegate -hash "你的密码"` 生成哈希,填入 `dashboard.password`。

### 3. 健康检查
```bash
curl http://localhost/health
```

---

## 目录结构说明

推荐的 LiteGate 工作目录结构：

```text
litegate/
├── litegate              # 可执行文件
├── config.yaml           # 全局配置文件
├── sites/                # HTTP 站点配置 (v1/*.yaml)
├── streams/              # L4 代理配置 (tcp/udp)
└── certs/                # 自动化证书存储
```

---

## 常见问题排查

### 端口冲突
如果 80/443 被 Nginx 或其他服务占用，请在 `config.yaml` 中修改 `http.port`。

### 权限不足 (Linux)
监听 1024 以下端口需要管理员权限：
```bash
sudo setcap 'cap_net_bind_service=+ep' /usr/local/bin/litegate
```
