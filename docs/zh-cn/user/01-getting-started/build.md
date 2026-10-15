# 源码构建指南

先按 [构建环境安装](build-environment.md) 准备 Go、Git 和 GNU Make。Go 版本以仓库 `go.mod` 为准，当前为 1.27.1。

## 获取源码

```bash
git clone https://github.com/jamesleeon/LiteGate.git
cd LiteGate
go mod download
```

## 常用 Make 指令

所有命令都在仓库根目录执行。默认输出到 `cmd/bin/`；平台目标同时构建 LiteGate 和 CredKeeper。

| 命令 | 用途 |
| --- | --- |
| `make / make all` | 全部平台，另含 Linux amd64 whoami 压测后端 |
| `make windows` | Windows amd64 |
| `make linux` | Linux amd64 |
| `make arm` | Linux arm64 |
| `make mac` | macOS amd64 + arm64 |
| `make credkeeper` | 仅构建当前 Go 目标平台的 CredKeeper |
| `make whoami` | Linux amd64 whoami |
| `make assets` | 刷新过期的内嵌 gzip 资源 |
| `make reset_env` | 清除持久化 GOOS / GOARCH |
| `make clean` | 恢复平台环境并清空 cmd/bin/ 产物 |

例如构建 Linux 版本并恢复本机平台：

```bash
make linux
make reset_env
```

`make` / `make all` 在正常完成时会自动恢复平台环境。单个平台目标会通过 `go env -w` 持久化修改 GOOS / GOARCH；单独构建后或构建中断后执行 `make reset_env`。这会清除原有自定义值，如需保留请先记录并自行恢复。`whoami` 还会设置并清除 CGO_ENABLED。

当前 Makefile 共享这些 Go 环境设置，请串行执行，不要使用 `make -j` 或同时启动不同平台的构建。

产物名如 `litegate_linux_amd64`、`credkeeper_linux_amd64`、`litegate_linux_arm64`、`litegate_darwin_arm64`；Windows 输出 `litegate_windows_amd64.exe` 和 `litegate.exe`，以及对应 CredKeeper 文件。可用 `make linux OUT_DIR=dist VERSION=v1.2.3` 指定输出目录和版本；默认版本取 `git describe --tags --always`。

## 可选构建

- `make linux-wasm`：编入实验性 IDS WASM 支持，LiteGate 文件名增加 `_wasm`。也有 `windows-wasm`、`arm-wasm`、`mac-wasm` 和 `all-wasm`。普通构建不含 WASM，CredKeeper 不带该后缀。
- `make linux H2PATCH=1`：编入 HTTP/2 写合并补丁；LiteGate 文件名增加 `_h2coalesce`，版本增加 `+h2coalesce.1`。默认使用官方标准库；补丁严格校验工具链版本和源码哈希，当前固定列表为 Go 1.27.1，不匹配会失败。可与 WASM 目标组合。
- `make h2patch-overlay`：仅生成补丁 overlay；`make h2patch-test`：测试补丁及标准库 HTTP/2 / HTTP，默认带 `-race`，需要支持 race 的本机工具链及 C 编译器。
- `make test-backlog`：Windows backlog 回归测试，仅在 Windows 上运行。

## 不使用 Make

先确认 Go 目标平台为本机（需要时执行 `go env -u GOOS GOARCH`）。编译整个包，不要只编译 `main.go`，否则会遗漏同包中的插件注册：

```bash
go build -o litegate ./cmd/litegate
```

Windows 使用以下命令启用监听 backlog 调整（`make windows` 已自动添加相关参数）：

```powershell
go build -tags winbacklog -ldflags="-checklinkname=0" -o litegate.exe ./cmd/litegate
```

直接构建不会自动刷新资源；修改内嵌资源后先运行 `make assets` 或对应包的 `go generate`。自定义插件构建见 [插件编译与 CLI](../12-plugins/build-and-cli.md)。

## Docker 与测试

```bash
docker build -t litegate:latest .
go test ./...
```

Dockerfile 使用多阶段构建，运行镜像基于 Alpine，包含 CA 证书与时区数据。测试可按包执行，如 `go test ./internal/router/...`。
