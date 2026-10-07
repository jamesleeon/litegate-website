# CLI 命令行参考

LiteGate 通过命令行参数控制启动行为和工具功能。

---

## 基础用法

```bash
litegate [options]
```

---

## 参数列表

### 运行模式

| 参数 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `-config <path>` | `config.yaml` | 指定配置文件路径。也可通过 `LITEGATE_CONFIG` 环境变量设置。 |
| `-log-level <level>` | 配置文件中的值 | 覆盖日志等级：`debug`, `info`, `warn`, `error`。 |
| `-enable-metrics` | `false` | 启用 Prometheus 指标导出。 |

### 工具模式

| 参数 | 说明 |
| :--- | :--- |
| `-init` | 生成 `config.example.yaml` 并创建 `sites/`, `streams/`, `certs/` 默认目录。 |
| `-example` | 在 `./sites` 目录下生成各类示例站点配置文件。 |
| `-hash <password>` | 为 Dashboard 密码生成 Bcrypt 哈希值。 |
| `-t` | 测试配置文件语法并退出（不启动服务）。类似 `nginx -t`。 |

### 插件与定制构建子命令

| 命令 | 说明 | 详见 |
| :--- | :--- | :--- |
| `litegate build [flags]` | 动态编译带自定义插件的 LiteGate 二进制（类似 `xcaddy`）。支持 `--with`、`--replace`、`-o`。 | [插件构建指南](../12-plugins/build-and-cli.md) |
| `litegate plugins list` | 列出当前二进制中编入的所有公共插件列表（类型、名称、版本、契约版本）。 | [插件 CLI 参考](../12-plugins/build-and-cli.md) |
| `litegate plugins inspect <kind>/<name>` | 查看指定已编入插件的详细元数据与官方 YAML 配置示例模板。 | [插件 CLI 参考](../12-plugins/build-and-cli.md) |
| `litegate plugins doctor` | 对当前已编入插件执行健康检查，诊断 Manifest 完整性与 APIVersion 兼容性。 | [插件 CLI 参考](../12-plugins/build-and-cli.md) |

### Consul 引导参数

| 参数 | 环境变量 | 说明 |
| :--- | :--- | :--- |
| `-consul-addr` | `LITEGATE_CONSUL_ADDR` | Consul 地址。指定后将从 Consul KV 远程加载配置。 |
| `-consul-token` | `LITEGATE_CONSUL_TOKEN` | Consul ACL Token。 |
| `-consul-config-key` | `LITEGATE_CONSUL_KEY` | Consul 中存储主配置的 KV 路径。默认 `litegate/config/main`。 |

### Litemesh 引导参数

| 参数 | 环境变量 | 说明 |
| :--- | :--- | :--- |
| `-litemesh-addr` | `LITEGATE_LITEMESH_ADDR` | Litemesh 地址。指定后将从 Litemesh KV 远程加载配置。 |
| `-litemesh-token` | `LITEGATE_LITEMESH_TOKEN` | Litemesh Auth Token。 |
| `-litemesh-config-key` | `LITEGATE_LITEMESH_KEY` | Litemesh 中存储主配置的 KV 路径。默认 `litegate/config/main`。 |
| `-sync-litemesh` | — | 将本地配置文件同步推送到 Litemesh KV，然后退出。 |

---

## 使用示例

### 零配置启动
```bash
litegate
```
默认监听 `:80` (HTTP) 和 `:443` (HTTPS)，自动扫描 `./sites` 目录。

### 指定配置文件
```bash
litegate -config /etc/litegate/config.yaml
```

### 初始化项目结构
```bash
litegate -init
```
生成 `config.example.yaml` 和 `sites/`, `streams/`, `certs/` 目录。

### 生成 Dashboard 密码
```bash
litegate -hash "your-password"
# 输出 Bcrypt 哈希值，复制到 config.yaml 的 dashboard.password 字段
```

### 测试配置语法
```bash
litegate -t
# litegate: the configuration file config.yaml syntax is ok
# litegate: sites configuration in ./sites syntax is ok
```

### 从 Litemesh 远程引导启动
```bash
litegate -litemesh-addr 127.0.0.1:8787 -litemesh-token mytoken
```

### 将本地配置同步到 Litemesh
```bash
litegate -config config.yaml -sync-litemesh -litemesh-addr 127.0.0.1:8787
```

---

## 环境变量

以下环境变量在命令行参数未指定时生效：

| 环境变量 | 说明 |
| :--- | :--- |
| `LITEGATE_CONFIG` | 配置文件路径 |
| `LITEGATE_CONSUL_ADDR` | Consul 地址 |
| `LITEGATE_CONSUL_TOKEN` | Consul ACL Token |
| `LITEGATE_CONSUL_KEY` | Consul KV 配置路径 |
| `LITEGATE_LITEMESH_ADDR` | Litemesh 地址 |
| `LITEGATE_LITEMESH_TOKEN` | Litemesh Auth Token |
| `LITEGATE_LITEMESH_KEY` | Litemesh KV 配置路径 |

> [!TIP]
> 配置文件中的字段也支持 `${VAR_NAME}` 环境变量语法。
