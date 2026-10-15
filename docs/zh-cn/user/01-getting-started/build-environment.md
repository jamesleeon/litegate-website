# 构建环境安装

需要 Git、GNU Make，以及满足仓库 `go.mod` 中 `go` 声明的 Go 工具链（当前为 1.27.1）。Make 是可选的，直接 `go build` 无需 Make。按 [Go 官方安装说明](https://go.dev/doc/install) 安装对应版本，并确保 `go` 在 PATH 中。

## Linux

Ubuntu / Debian：

```bash
sudo apt update
sudo apt install git make
```

Fedora：

```bash
sudo dnf install git make
```

系统软件源中的 Go 可能较旧，安装后请与 `go.mod` 核对。

## macOS

安装 Apple Command Line Tools，提供 Git 和 Make：

```bash
xcode-select --install
```

检查 `make --version` 输出为 GNU Make。Go 可使用官方安装包；如已使用 [Homebrew](https://docs.brew.sh/Installation)，也可运行 `brew install go git`，再核对 Go 版本。

## Windows

安装 Go 官方 MSI 和 [Git for Windows](https://git-scm.com/downloads/win)。Git Bash 本身不保证提供 Make。

一种完整环境是 [MSYS2](https://www.msys2.org/)：安装后在 MSYS2 终端更新系统，按提示关闭并重新打开终端；然后安装 [Make 包](https://packages.msys2.org/packages/make)：

```bash
pacman -Syu
pacman -S --needed make git
```

确保 Windows Go 安装目录在该终端 PATH 中，例如默认目录：

```bash
export PATH="/c/Program Files/Go/bin:$PATH"
cd /d/ecp_source/LiteGate
make windows
make reset_env
```

将 `cd` 路径替换为你的仓库位置。建议直接在 MSYS2 终端使用其 Make；无需将整个 MSYS2 `usr/bin` 加入 Windows 全局 PATH。PowerShell 中也可使用已安装且支持 Windows 的 GNU Make，确认 `make --version` 能正常运行；`nmake` 不能替代 GNU Make。

## 验证环境

在实际执行构建的终端中运行：

```bash
go version
git --version
make --version
go env GOHOSTOS GOHOSTARCH GOOS GOARCH
```

找不到命令时，检查 PATH 并重新打开终端。工具链下载失败时检查网络和 `go env GOPROXY GOTOOLCHAIN`；不要通过降低 `go.mod` 版本绕过要求。准备好后继续阅读 [构建指南](build.md)。
