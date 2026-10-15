# Build from source

Prepare Go, Git, and GNU Make with the [build environment setup guide](build-environment.md). The repository's `go.mod` determines the required Go version, currently 1.27.1.

## Get the source

```bash
git clone https://github.com/jamesleeon/LiteGate.git
cd LiteGate
go mod download
```

## Common Make commands

Run all commands from the repository root. Outputs default to `cmd/bin/`; platform targets build both LiteGate and CredKeeper.

| Command | Purpose |
| --- | --- |
| `make / make all` | All platforms, plus the Linux amd64 whoami benchmark backend |
| `make windows` | Windows amd64 |
| `make linux` | Linux amd64 |
| `make arm` | Linux arm64 |
| `make mac` | macOS amd64 + arm64 |
| `make credkeeper` | Only CredKeeper for the current Go target |
| `make whoami` | Linux amd64 whoami |
| `make assets` | Refresh stale embedded gzip assets |
| `make reset_env` | Clear persisted GOOS / GOARCH |
| `make clean` | Reset target settings and remove outputs in cmd/bin/ |

For example, build Linux binaries and restore the host target:

```bash
make linux
make reset_env
```

`make` / `make all` resets target settings after successful completion. Individual platform targets persist GOOS / GOARCH with `go env -w`; run `make reset_env` after an individual build or an interrupted build. This clears previous custom values too; record and restore them yourself if needed. `whoami` also sets and clears CGO_ENABLED.

The current Makefile shares these Go environment settings. Run builds sequentially; do not use `make -j` or launch different platform builds concurrently.

Output names include `litegate_linux_amd64`, `credkeeper_linux_amd64`, `litegate_linux_arm64`, and `litegate_darwin_arm64`. Windows produces both `litegate_windows_amd64.exe` and `litegate.exe`, plus corresponding CredKeeper files. Override the output directory and version with `make linux OUT_DIR=dist VERSION=v1.2.3`; the default version comes from `git describe --tags --always`.

## Optional builds

- `make linux-wasm`: include experimental IDS WASM support and add `_wasm` to the LiteGate filename. Other targets are `windows-wasm`, `arm-wasm`, `mac-wasm`, and `all-wasm`. Standard builds omit WASM; CredKeeper does not use this suffix.
- `make linux H2PATCH=1`: include the HTTP/2 write-coalescing patch. LiteGate filenames gain `_h2coalesce` and versions gain `+h2coalesce.1`. Default builds use the official standard library. The patch validates the toolchain version and source hash; the current pinned list contains Go 1.27.1 and rejects mismatches. This option can be combined with WASM targets.
- `make h2patch-overlay`: generate only the patch overlay. `make h2patch-test`: test the patch and standard-library HTTP/2 / HTTP code, with `-race` by default; this requires a host toolchain supporting race detection and a C compiler.
- `make test-backlog`: run the Windows backlog regression test on Windows only.

## Build without Make

First ensure Go targets the host (run `go env -u GOOS GOARCH` if needed). Build the entire package rather than only `main.go`, which omits plugin registration in other files:

```bash
go build -o litegate ./cmd/litegate
```

On Windows, enable the listener backlog adjustment with these flags (`make windows` adds them automatically):

```powershell
go build -tags winbacklog -ldflags="-checklinkname=0" -o litegate.exe ./cmd/litegate
```

Direct builds do not refresh assets automatically. After changing embedded assets, run `make assets` or the corresponding package's `go generate`. For custom plugins, see [build and CLI](../12-plugins/build-and-cli.md).

## Docker and tests

```bash
docker build -t litegate:latest .
go test ./...
```

The Dockerfile uses a multi-stage build with an Alpine runtime image containing CA certificates and timezone data. Tests can also run per package, such as `go test ./internal/router/...`.
