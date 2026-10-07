# 插件编译构建与管理 CLI

LiteGate 提供了类似 Caddy `xcaddy` 的一站式定制编译工具链以及运行期插件自检 CLI。
无论你是需要将内部私有包集成到网关中，还是在独立仓库为开源社区贡献插件，LiteGate 都支持以极低的门槛进行构建与验证。

---

## 方式一：使用 `litegate build` 命令（推荐）

从当前 LiteGate 二进制中直接调用 `build` 子命令，可以在不准备任何网关源码工程的情况下，快速编译出携带指定插件的全新二进制：

```bash
litegate build --with <package>[@version][=local_path] [options]
```

### 1. 核心构建场景示例

#### A. 引入公网/私有 Git 仓库发布的插件

```bash
litegate build \
  --with github.com/acme/litegate-jwt-auth@v1.2.0 \
  --with github.com/acme/litegate-nacos-discovery@v0.5.1 \
  -o custom-litegate
```

> [!TIP]
> 如果使用的是私有 Git 仓库，确保当前机器配置了标准 Go 环境变量（如 `GOPRIVATE=github.com/acme/*`），构建器将直接复用本地的 Git 认证凭据。

#### B. 本地开发与联调模式（本地目录替换）

在本地编写插件源码时，无需先提交并打 Git Tag，可通过 `=<local_path>` 语法直接将包路径映射到本地代码目录：

```bash
litegate build \
  --with github.com/acme/litegate-plugin=../my-plugin-repo \
  -o custom-litegate
```

如果插件存放在一个包含多个子包的工程中，还可以直接在同一命令中指定：

```bash
litegate build \
  --with mycompany/plugins/action/ai=./my-plugins \
  --with mycompany/plugins/middleware/tenant=./my-plugins \
  -o custom-litegate
```

#### C. 锁定或替换 LiteGate 核心版本

若需要基于指定的 LiteGate 核心分支或本地 LiteGate 核心源码进行编译：

```bash
# 替换 LiteGate 核心为本地开发版本
litegate build \
  --replace github.com/jamesleeon/LiteGate=/path/to/LiteGate \
  --with github.com/acme/my-plugin@v1.0.0 \
  -o custom-litegate
```

### 2. `litegate build` 完整参数清单

| 参数 | 说明 | 示例 |
| :--- | :--- | :--- |
| `--with <spec>` | 添加一个插件模块。可多次重复指定。<br>格式：`<module>[@version][=local_path]` | `--with github.com/foo/bar@v1.0.0` |
| `--replace <spec>` | 等价于 `go.mod` 中的 `replace` 指令。可多次重复指定。<br>格式：`<old>[=new]` | `--replace github.com/foo/bar=../bar` |
| `-o, --output <path>` | 指定输出的二进制文件路径。默认为当前平台的默认文件名（如 `litegate` 或 `litegate.exe`）。 | `-o /usr/local/bin/litegate` |
| `--core-version <ver>` | 强制锁定 LiteGate 核心版本。 | `--core-version v1.5.0` |
| `--core-path <path>` | 指向本地 LiteGate 源码目录进行构建。 | `--core-path /data/src/LiteGate` |
| `--race` | 启用 Go 数据竞态检测器（Race Detector），适合压测和自动化集成测试。 | `--race` |
| `--debug` | 关闭编译优化与内联，保留完整符号表，适合 GDB/Delve 调试。 | `--debug` |
| `--keep-work-dir` | 构建完成后保留临时工作目录，便于审查自动生成的 `main.go` 与 `go.mod`。 | `--keep-work-dir` |

---

## 方式二：用户拥有 `main.go` 源码空导入模式

如果你希望将 LiteGate 作为企业内部定制网关的基础底座，并采用单一的代码仓库统一管理定制逻辑与依赖，可以编写属于你自己的 `main.go`：

### 1. 初始化独立 Go 工程

```bash
mkdir my-gateway && cd my-gateway
go mod init my-gateway
go get github.com/jamesleeon/LiteGate
```

### 2. 编写 `main.go` 空导入插件

```go
package main

import (
	"log"

	// 1. 空导入你的自定义插件包（触发其 init() 自注册）
	_ "my-gateway/plugins/custom_audit"
	_ "my-gateway/plugins/ldap_auth"

	// 2. 如果需要 LiteGate 标准发行版内置的插件，按需导入
	_ "github.com/jamesleeon/LiteGate/internal/plugins/nats"
	_ "github.com/jamesleeon/LiteGate/pkg/plugins/forwardproxy"

	// 3. 启动 LiteGate 核心引擎
	"github.com/jamesleeon/LiteGate/pkg/litegate"
)

func main() {
	if err := litegate.Run(); err != nil {
		log.Fatalf("Gateway exited with error: %v", err)
	}
}
```

### 3. 普通 `go build` 编译

```bash
go build -o my-gateway .
```

---

## 插件管理与诊断 CLI

编译完成后，LiteGate 提供了一套完整的内置 CLI 命令，用于审计、自检和调试已载入的插件：

### 1. `litegate plugins list` —— 列出所有已编入的插件

显示当前二进制中所有注册的公共 API 插件，包括扩展点类型、插件标识名、插件版本号以及所遵循的 LiteGate APIVersion 规范：

```bash
litegate plugins list
```

**终端输出样例：**
```text
KIND             NAME                             VERSION        API
action           nats                             1.0.0          v1
ids              openapi_md5                      1.1.0          v1
ingress          forward_proxy                    0.3.0          v1
discovery        memory                           0.1.0          v1
middleware       request_id                       1.0.0          v1
```

支持输出为结构化 JSON，方便在发布流水线中进行机器自动化解析：

```bash
litegate plugins list --json
```

### 2. `litegate plugins inspect` —— 查看插件元数据与配置模板

查看指定插件的详细元数据，包括展示名、开源许可证、功能特性列表（Capabilities）以及**开箱即用的 YAML 配置模板**：

```bash
litegate plugins inspect ingress/forward_proxy
```

**终端输出样例：**
```text
Kind:         ingress
Name:         forward_proxy
Version:      0.3.0
API:          v1
Display Name: HTTP forward proxy
License:      Apache-2.0
Description:  HTTP forward proxy with authenticated HTTP/1.1, HTTP/2 and HTTP/3 CONNECT and destination ACLs.
Capabilities: http1, http2, http3, connect, proxy_auth, destination_acl, probe_resistance

Config Example:
# Global config; generate a hash with litegate -hash 'your-password'.
ingress_plugins:
  - name: my-forward-proxy
    type: forward_proxy
    entrypoints: [websecure]
    config:
      probe_resistance: true
      users:
        admin: "$2a$10$YourBcryptHashHere"
```

### 3. `litegate plugins doctor` —— 插件健康体检与兼容性诊断

在将定制二进制部署到生产环境之前，运行 `doctor` 命令可快速排查潜在隐患：

```bash
litegate plugins doctor
```

`doctor` 会自动执行以下检查：
- **Manifest 规范性**：检查是否所有编译入二进制的插件都声明了统一 `Manifest`。
- **APIVersion 兼容性**：验证各插件声称实现的 `APIVersion`（如 `v1`）是否与当前网关主程序所期待的接口版本完全匹配。
- **配置示例安全性**：检测各插件的 `ConfigExample` 是否合法、是否存在未转义字符或超限数据。

---

## Web Dashboard 可视化查看

LiteGate 的内置运维仪表盘（Dashboard）集成了编译插件的白盒感知：

1. 浏览器访问 LiteGate 管理后台（默认 `https://your-domain:443/__status` 或配置的 Dashboard 地址）。
2. 在导航中点击 **Compiled Plugins**。
3. 界面会分类展示所有已生效的 Action、Middleware、Discovery、DNS 等插件卡片，并提供直接复制配置模版的功能。

---

## 生产环境 CI/CD 自动化构建示例 (Dockerfile)

以下是一个标准的 Multi-stage 多阶段构建 Dockerfile，用于企业自动化构建带自研插件的微型轻量镜像：

```dockerfile
# 阶段 1: 使用官方 Go 环境进行定制构建
FROM golang:1.24-alpine AS builder

WORKDIR /build

# 安装基础编译依赖
RUN apk add --no-cache git ca-certificates tzdata

# 下载基础 LiteGate 工具或直接通过 litegate build 构建
RUN go install github.com/jamesleeon/LiteGate/cmd/litegate@latest

# 通过 litegate build 命令注入企业私有插件
RUN litegate build \
    --with github.com/acme/litegate-plugin-auth@v1.0.0 \
    --with github.com/acme/litegate-plugin-discovery@v0.2.0 \
    -o /build/litegate

# 阶段 2: 生产运行时镜像 (保持极小体积)
FROM alpine:3.20

RUN apk add --no-cache ca-certificates tzdata

WORKDIR /app

# 从构建阶段复制生成的单一静态二进制
COPY --from=builder /build/litegate /usr/local/bin/litegate

# 默认数据卷与配置文件挂载点
VOLUME ["/app/config.yaml", "/app/sites", "/app/certs"]

EXPOSE 80 443

ENTRYPOINT ["litegate"]
CMD ["-config", "/app/config.yaml"]
```
