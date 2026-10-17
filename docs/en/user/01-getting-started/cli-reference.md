# CLI Reference

LiteGate's startup behaviors and tool capabilities are controlled by command-line parameters.

---

## Basic Usage

```bash
litegate [options]
```

---

## Parameters

### Execution Mode

| Options | Default | Description |
| :--- | :--- | :--- |
| `-config <path>` | `config.yaml` | Specifies the path to the configuration file. Can also be set via the `LITEGATE_CONFIG` environment variable. |
| `-log-level <level>`| Defined in config | Overrides the log level: `debug`, `info`, `warn`, `error`. |
| `-enable-metrics` | `false` | Enables Prometheus metrics exporter. |

### Utility Mode

| Options | Description |
| :--- | :--- |
| `-init` | Generates `config.example.yaml` and creates default directories: `sites/`, `streams/`, `certs/`. |
| `-example` | Generates various example site configuration files under the `./sites` directory. |
| `-hash <password>`| Generates a Bcrypt hash value for the Admin Dashboard password. |
| `-hashfile <path>` | Prints the file SHA256 as a single 64-character lowercase hexadecimal line and exits, for the SPA/serve KV `sha256` field. |
| `-t` | Tests the configuration file syntax and exits (does not launch the gateway). Similar to `nginx -t`. |

### Subcommands

| Command | Description | See |
| :--- | :--- | :--- |
| `litegate build [flags]` | Builds a LiteGate binary with custom plugins (like `xcaddy`). Supports `--with`, `--replace` and `-o`. | [Plugin builds](../12-plugins/build-and-cli.md) |
| `litegate plugins list\|inspect\|doctor` | Lists, inspects and health-checks the plugins compiled into this binary. | [Plugin CLI](../12-plugins/build-and-cli.md) |
| `litegate mcp [-config <path>] [-log-level <level>]` | Runs the MCP server over stdio so AI clients such as Claude Code or Cursor can launch it. Logs go to stderr. | [MCP capability matrix](../../litegate_mcp_capability_matrix.md) |
| `litegate forward --remote <url> --local <addr> --token-file <file>` | Forward client: maps a remote Stream to a local port; `--config` reads a YAML file instead. `litegate forward token --output <file>` generates a token. | [Forward and Connect](../09-advanced/forward-and-connect.md) |
| `litegate connect [http] --remote <url> --name <name> --domain <host> --upstream <url>` | Publishes a local HTTP service through Connect from the command line; `litegate connect token --output <file>` generates a token. | [Connect CLI](../09-advanced/connect-cli-http.md) |
| `litegate systemd [options]` | Prints a systemd unit file (`-user`, `-workdir`, `-config`, `-name`, ...). | [systemd deployment](../10-deployment/systemd.md) |
| `litegate secret keygen\|pubkey\|encrypt` | Generates this host's key pair and seals credentials into `enc://` references so configuration files hold no plaintext. | [Sealed Secrets](../06-certificates/sealed-secrets.md) |
| `litegate ech withdraw -config <path>` | Withdraws published ECH DNS records (stop the ECH instance first). | [ECH](../06-certificates/ech.md) |
| `litegate healthcheck [-config <path>] [-addr <addr>]` | Probes the local gateway health endpoint, suitable for a container `HEALTHCHECK`. | [Production deployment](../10-deployment/production.md) |

### Consul Bootstrapping Parameters

| Options | Environment Variable | Description |
| :--- | :--- | :--- |
| `-consul-addr` | `LITEGATE_CONSUL_ADDR` | Consul server address. Once specified, configurations are remotely loaded from Consul KV. |
| `-consul-token` | `LITEGATE_CONSUL_TOKEN` | Consul ACL Token. |
| `-consul-config-key`| `LITEGATE_CONSUL_KEY` | Path to the master configuration in Consul KV. Defaults to `litegate/config/main`. |

### Litemesh Bootstrapping Parameters

| Options | Environment Variable | Description |
| :--- | :--- | :--- |
| `-litemesh-addr` | `LITEGATE_LITEMESH_ADDR`| Litemesh server address. Once specified, configurations are remotely loaded from Litemesh KV. |
| `-litemesh-token` | `LITEGATE_LITEMESH_TOKEN`| Litemesh Auth Token. |
| `-litemesh-config-key`| `LITEGATE_LITEMESH_KEY` | Path to the master configuration in Litemesh KV. Defaults to `litegate/config/main`. |
| `-sync-litemesh` | — | Synchronously pushes the local configuration files to Litemesh KV, then exits. |

---

## Examples

### Zero-Configuration Startup
```bash
litegate
```
Listens on ports `:80` (HTTP) and `:443` (HTTPS) by default, and automatically scans the `./sites` directory.

### Specifying a Configuration File
```bash
litegate -config /etc/litegate/config.yaml
```

### Initializing Project Directory Structure
```bash
litegate -init
```
Generates `config.example.yaml` and sets up `sites/`, `streams/`, and `certs/` folders.

### Generating Bcrypt Password Hash for Dashboard
```bash
litegate -hash "your-password"
# Outputs Bcrypt hash. Copy it into the dashboard.password field of config.yaml
```

### Testing Configuration Syntax
```bash
litegate -t
# Output:
# litegate: the configuration file config.yaml syntax is ok
# litegate: sites configuration in ./sites syntax is ok
```

### Remotely Bootstrapping from Litemesh
```bash
litegate -litemesh-addr 127.0.0.1:8787 -litemesh-token mytoken
```

### Syncing Local Configurations to Litemesh
```bash
litegate -config config.yaml -sync-litemesh -litemesh-addr 127.0.0.1:8787
```

---

## Environment Variables

The following environment variables take effect if corresponding command-line parameters are not specified:

| Environment Variable | Description |
| :--- | :--- |
| `LITEGATE_CONFIG` | Configuration file path |
| `LITEGATE_CONSUL_ADDR` | Consul address |
| `LITEGATE_CONSUL_TOKEN` | Consul ACL Token |
| `LITEGATE_CONSUL_KEY` | Consul KV configuration path |
| `LITEGATE_LITEMESH_ADDR` | Litemesh address |
| `LITEGATE_LITEMESH_TOKEN` | Litemesh Auth Token |
| `LITEGATE_LITEMESH_KEY` | Litemesh KV configuration path |

> [!TIP]
> Fields within the configuration file also support the `${VAR_NAME}` environment variable substitution syntax.

### Calculate a SPA/serve KV archive checksum

```bash
litegate -hashfile main-12.zip
```

Copy the output line into the KV JSON `sha256` field. The checksum covers the raw bytes of the uploaded ZIP, before extraction. No configuration file is required and no service is started.
