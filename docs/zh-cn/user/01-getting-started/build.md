# 构建指南 (Build from Source)

本指南介绍如何从源码编译 LiteGate。

---

## 1. 前置要求

- **Go**: 1.22 或更高版本
- **Git**: 用于克隆代码
- **Make**: (可选) 用于快捷编译

---

## 2. 克隆代码

```bash
git clone https://github.com/jamesleeon/LiteGate.git
cd LiteGate
```

---

## 3. 编译

### 方式一：直接编译

```bash
go mod download
go build -ldflags="-s -w" -o bin/litegate ./cmd/litegate
```

### 方式二：交叉编译

```bash
# Linux AMD64
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o bin/litegate-linux-amd64 ./cmd/litegate

# Linux ARM64 (树莓派等)
CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -ldflags="-s -w" -o bin/litegate-linux-arm64 ./cmd/litegate

# Windows
CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -ldflags="-s -w" -o bin/litegate.exe ./cmd/litegate
```

---

## 4. Docker 构建

```bash
docker build -t litegate:latest .
```

Dockerfile 采用多阶段构建，最终镜像基于 Alpine，仅包含二进制文件和 CA 证书。

---

## 5. 运行测试

```bash
# 运行所有单元测试
go test ./...

# 运行特定模块的测试
go test ./internal/router/...
go test ./internal/action/...
```

---

## 6. 目录结构

```text
litegate/
├── cmd/
│   ├── litegate/        # 主入口
│   └── tools/           # 辅助工具
│       └── jwt_gen/      # JWT Token 生成器
├── internal/            # 核心业务逻辑 (不对外暴露)
│   ├── action/          # Action 处理器 (proxy, serve, webdav...)
│   ├── auth/            # OIDC/OAuth2 认证
│   ├── cert/            # DNS Provider 实现
│   ├── certmanager/     # ACME 证书管理
│   ├── config/          # 配置模型与加载
│   ├── ddns/            # DDNS 自动同步
│   ├── discovery/       # 服务发现与负载均衡
│   ├── health/          # 健康检查
│   ├── loader/          # 站点/Stream 配置加载器
│   ├── mcp/             # MCP (Model Context Protocol)
│   ├── middleware/       # 中间件 (WAF, Auth, CORS, Rate Limit...)
│   ├── proxy/           # 连接池与 WebSocket
│   ├── router/          # Trie 路由引擎
│   ├── status/          # Dashboard & API
│   └── webhook/         # Webhook 日志告警
├── pkg/                 # 可复用的公共包
├── scripts/             # 测试脚本与示例
├── docs/                # 文档
├── sites/               # 站点配置示例
├── streams/             # Stream 配置示例
└── certs/               # 证书存储
```
