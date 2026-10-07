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
| `-t` | Tests the configuration file syntax and exits (does not launch the gateway). Similar to `nginx -t`. |

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
