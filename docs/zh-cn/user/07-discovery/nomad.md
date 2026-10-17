# Nomad 服务发现

Nomad 插件直接读取 Nomad 原生服务注册，通过 Tags 自动生成 LiteGate 路由和后端池，不需要经过 LiteDNS discovery agent。Nomad job 中必须使用 `provider = "nomad"`；使用 `provider = "consul"` 的服务请接入 [Consul 服务发现](consul.md)。

开发者请先阅读 [Discovery 插件开发：以 Nomad 为例](../../discovery-provider-plugin-guide.md)，按接口实现、注册、编译接入、用户配置的顺序完成开发。本文是部署后面向用户的详细配置说明。

## 1. 确认插件可用

标准 `cmd/litegate` 已默认编入 Nomad 插件。部署新的二进制后检查：

```bash
litegate plugins inspect discovery/nomad
```

应显示 `Name: nomad`。自定义 main 需要空导入 `github.com/jamesleeon/LiteGate/pkg/plugins/nomad` 后重新构建；仅修改配置不能给旧二进制安装插件。参见[插件构建与 CLI](../12-plugins/build-and-cli.md)。

## 2. 配置全局 config.yaml

```yaml
service_discovery:
  catalogs:
    - name: nomad-prod
      enabled: true
      provider: nomad
      namespace: default
      config:
        address: "https://nomad.example.com:4646"
        namespace: "default"
        token_file: "/run/secrets/nomad-token"
        region: "global"
        # ca_file: "/etc/nomad/ca.pem"
        # cert_file: "/etc/nomad/client.pem"
        # key_file: "/etc/nomad/client-key.pem"
        # timeout: "10s"
        # protocol: "http"
```

替换 API 地址和 region，并把 Token 文件挂载到 **LiteGate 所在进程或容器**。文件只保存 Token 文本，不包含 `X-Nomad-Token:` 前缀；插件每次请求重新读取，可轮换文件内容。启用 ACL 时，Token 需要目标 namespace 的服务读取权限；插件不会写入 Nomad。

外层 `name` 是 LiteGate 发现源实例名，不是 Nomad job 名或服务名。`config.address` 是 Nomad API 地址；该插件不使用 Catalog 外层的 `url`、`token` 作为连接参数。

### 配置字段

下表字段均位于 `catalogs[].config`，值使用字符串；未知字段会被拒绝。

| 字段 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `address` | 必填 | HTTP/HTTPS API 地址，不允许 URL 用户凭据、查询参数或 fragment |
| `namespace` | `default` | Nomad API 查询范围；`"*"` 列举 Token 可读取的 namespace |
| `region` | 由 Nomad agent 决定 | API 查询 region；示例 `global` 应与实际部署一致 |
| `token_file` | 无 | Token 文件路径，与 `token` 互斥 |
| `token` | 无 | 直接传入 ACL Token；不要把真实 Token 提交到代码仓库 |
| `ca_file` | 系统信任库 | 附加 PEM CA，用于验证私有 CA 签发的 Nomad 服务端证书 |
| `cert_file` | 无 | mTLS 客户端 PEM 证书，必须与 `key_file` 同时配置；文件变更后自动重新加载 |
| `key_file` | 无 | mTLS 客户端 PEM 私钥 |
| `timeout` | `10s` | 正数 HTTP 请求超时，例如 `"5s"` |
| `protocol` | `http` | 后端业务协议：`http`、`https`、`h2c`、`grpc`、`grpcs`、`tcp`、`tls`、`udp` |

`address` 的 HTTPS 控制 LiteGate 到 Nomad API 的连接，`protocol` 控制业务后端协议，两者独立。HTTP API 不加密 Token；生产环境应使用 HTTPS。插件验证服务端证书，不提供跳过校验选项。

### Namespace 与多集群

**外层 `namespace` 不会传给插件 Factory，不能代替 `config.namespace`。** 外层值用于 Catalog 命名空间回退，插件返回的实际 namespace 优先。发现 `prod` 时，应设置 `config.namespace: "prod"`，并建议外层也设置为 `prod`。

跨 namespace 发现时使用 `config.namespace: "*"`；后续实例查询会使用服务返回的具体 namespace。多个 Nomad 集群可以配置多个 Catalog，每个使用不同 `name`、API 地址和凭据。同名同 namespace 的服务可能进入多源合并；需要隔离时请规划不同 namespace 或服务名。

## 3. 在 Nomad 注册服务并声明路由

在现有 task group 中定义端口，并添加 service 块。下面片段应放入 group；业务 task 的网络配置也需要使用 `http` 端口标签：

```hcl
network {
  port "http" {
    to = 8080
  }
}

service {
  name         = "orders"
  provider     = "nomad"
  port         = "http"
  address_mode = "host"
  tags = [
    "litegate.http.host=orders.example.com",
    "litegate.http.path_prefix=/"
  ]
}
```

把 `8080` 替换为应用端口，并按实际 Nomad driver 和网络模式配置 task。LiteGate 使用注册记录中的 `Address` 和实际数字 `Port`，包括动态宿主端口；确保这些地址能从 LiteGate 访问。将 `orders.example.com` 的 DNS 指向 LiteGate 入口，而不是 Nomad API。

Tags 进入 LiteGate 的统一标签解析链路，上例生成域名路由。不要再用站点 YAML 或另一套标签重复定义同一路由。更多声明方式参见 [Tag DSL](../03-configuration/tag-dsl.md)。`protocol` 只设置后端协议；TCP/UDP 入口和路由仍需另外配置。

插件还提供 `nomad.job_id`、`nomad.alloc_id`、`nomad.node_id`、`nomad.datacenter` 元数据。注册 API 不返回 job 端口标签，因此不支持 `port_name` 选择；多端口业务应注册不同服务名。

## 4. 更新、健康与 Dashboard

- 插件通过 Nomad blocking query 长轮询 `/v1/services`，任何注册变化（扩缩容、下线、地址/端口/标签变化）都会立即触发 Catalog 重扫；Catalog 每 30 秒的周期扫描保留作兜底。阻塞查询失败时 Watch 会带错误退出，Dashboard 的 watch 状态显示为失败及原因，宿主随后退避重启并重扫。
- 成功返回空列表时移除对应注册记录；API 错误时沿用宿主的最后成功快照，目前没有最大过期时间。
- 注册存在仅代表可参与后端选择，不代表应用就绪。插件不读取 Nomad check 或 Allocation 健康结果；需要应用级就绪判断时配置 LiteGate 主动健康检查。
- Dashboard 顶部 **Plugins** 中可找到 Nomad 及配置实例；首页 **Control Plane Providers** 显示运行状态。新建实例在首次查询前可能显示 Active，实际连通性应结合最近成功时间、错误和日志判断；失败时显示 Degraded。

## 5. 排查

| 现象 | 检查项 |
| :--- | :--- |
| `unregistered provider` | 当前运行的二进制是否编入插件，是否已部署新版本 |
| HTTP 403 | Token 是否有效，是否有目标 namespace 的读取权限 |
| 证书或连接错误 | API 地址、CA、mTLS 文件、网络与请求超时；不要将应用端口误作 API 端口 |
| 发现不到服务 | Nomad job 的 provider 是否为 `nomad`，region 和 `config.namespace` 是否正确 |
| 已发现但业务访问失败 | 注册地址和动态端口的可达性、后端协议、应用状态，以及域名是否指向 LiteGate |
| 下线后仍看到旧实例 | 等待后续扫描；若 API 持续失败，旧快照可能继续保留，检查 Degraded 状态 |

[服务发现总览](overview.md) · [插件体系](../12-plugins/README.md)
