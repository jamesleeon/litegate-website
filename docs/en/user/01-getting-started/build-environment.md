# Build environment setup

Install Git, GNU Make, and a Go toolchain satisfying the `go` directive in the repository's `go.mod` (currently 1.27.1). Make is optional for direct `go build`. Follow the [official Go installation instructions](https://go.dev/doc/install) for the required version and ensure `go` is on PATH.

## Linux

Ubuntu / Debian:

```bash
sudo apt update
sudo apt install git make
```

Fedora:

```bash
sudo dnf install git make
```

Go from your distribution may be older than required; compare its version with `go.mod`.

## macOS

Install Apple Command Line Tools for Git and Make:

```bash
xcode-select --install
```

Check that `make --version` reports GNU Make. Install Go with the official package, or, if you already use [Homebrew](https://docs.brew.sh/Installation), run `brew install go git` and check the Go version afterwards.

## Windows

Install the official Go MSI and [Git for Windows](https://git-scm.com/downloads/win). Git Bash alone does not guarantee that Make is installed.

[MSYS2](https://www.msys2.org/) provides a complete environment. Update it in an MSYS2 terminal, closing and reopening the terminal when prompted, then install its [Make package](https://packages.msys2.org/packages/make):

```bash
pacman -Syu
pacman -S --needed make git
```

Ensure the Windows Go installation is on PATH in that terminal, for example with the default location:

```bash
export PATH="/c/Program Files/Go/bin:$PATH"
cd /d/ecp_source/LiteGate
make windows
make reset_env
```

Replace the repository path with your own. Use MSYS2 Make from its terminal; you do not need to add the entire MSYS2 `usr/bin` to the Windows global PATH. PowerShell can also use an installed Windows-compatible GNU Make; check `make --version`. `nmake` is not a substitute for GNU Make.

## Verify the environment

Run these commands in the terminal you will use to build:

```bash
go version
git --version
make --version
go env GOHOSTOS GOHOSTARCH GOOS GOARCH
```

If a command is missing, check PATH and reopen the terminal. If toolchain downloads fail, check network access and `go env GOPROXY GOTOOLCHAIN`; do not lower the `go.mod` version to bypass requirements. Continue with the [build guide](build.md).
