# 添加 DNS 服务商

默认 LiteGate 支持阿里云（`aliyun`）、腾讯云（`tencent` / `tencentcloud`）和 Cloudflare（`cloudflare`）。如果你使用其他 DNS 服务商，通常可以从 [libdns 服务商目录](https://github.com/libdns) 选择对应实现，用 `litegate build --dns` 编译到自己的 LiteGate 中，无需编写插件代码。

服务商是在构建时下载并编入二进制的；修改 YAML 不会自动下载插件。每个 libdns 服务商都是独立模块，官方默认构建不会因为你的选择增加依赖。部分实现依赖云 SDK，定制二进制的体积取决于所选模块及其依赖。

## 1. 选择服务商

在 libdns 目录中找到服务商仓库，阅读该版本的 README、`Provider` 配置字段和 `go.mod`。LiteGate 的自动接入要求模块根包导出 `Provider` 结构体，并使用 **libdns v1 API**。

| 使用目的 | 所需接口与服务商能力 |
|---|---|
| DNS-01 证书验证 | `RecordAppender`、`RecordDeleter`，支持 TXT |
| DDNS | 再加 `RecordGetter`，支持所需的 A / AAAA |
| ECH DNS 发布 | 再加 `RecordGetter`，支持 HTTPS 记录 |

接口存在并不保证所有记录类型均可用，仍需查看服务商说明和账户权限。[libdns 核心库](https://github.com/libdns/libdns) 只定义接口；实际接入的是具体服务商模块。仓库名字不一定等于品牌名称，例如阿里云模块名为 `alidns`，而 LiteGate 内置配置类型是 `aliyun`。

### 按用途确认要求

**只申请和续期证书最简单。** 不启用 DDNS，也不启用 ECH 时，DNS 服务商只负责写入和清理 DNS-01 验证用 TXT，证书签发由 LiteGate 的 ACME 客户端完成。无需支持 A、AAAA 或 HTTPS 记录，也无需自动更新业务域名的 IP；业务域名的地址由你另行配置。仍需正确的凭证、托管区域和 TXT 传播；同时申请根域与通配符证书时，还应确认能保留同名 TXT 的多个验证值。专门用于证书验证的服务不应被当作完整 DNS 托管服务。

**启用 DDNS 会增加 A/AAAA 管理要求。** 服务商实现需要能查询记录、追加本节点的 IP，并按具体值删除本节点旧记录，同时保留其他节点的地址。只提供“把域名的唯一 IP 改成新 IP”的接口，不满足 LiteGate 多节点 RRset 契约，即使它也称作 DDNS。重复同步同一 IP 应幂等。只有 IPv4 支持时启用 `sync_a`，保持 `sync_aaaa: false`；需要 IPv6 时再确认 AAAA 支持。

**启用 ECH 会增加 HTTPS DNS 记录管理要求。** 服务商的 API、账户权限和所选 libdns 实现都必须支持 HTTPS（类型 65），能读写 ECH 参数，并在轮换、撤回时保留不属于 LiteGate 的记录。普通 HTTPS 证书申请不需要这种 DNS 记录。发布记录只是 ECH 的一部分，网关、客户端和解析链路的其余要求见 [ECH 指南](ech.md)。ECH 不要求开启 DDNS，可以手动维护 A/AAAA。

构建成功、插件列表中的能力声明和 `-t` 校验通过，都不等于上述操作已在真实服务商验证。按实际启用的功能检查；不要因为某模块能做 TXT 验证，就默认它也能做多节点 DDNS 或 ECH。

## 2. 编译需要的服务商

构建机器需要 Git、Go，以及访问所选 Go 模块的网络条件。Go 版本应满足 LiteGate 和服务商模块的 `go.mod` 要求；运行机器无需安装 Go。

```bash
# 短名对应 github.com/libdns/huaweicloud
litegate build --dns huaweicloud -o litegate-custom

# 同时加入多家服务商，包括依赖云 SDK 的可选实现
litegate build --dns huaweicloud --dns route53 -o litegate-custom

# 自定义 YAML 中使用的 type；也可填写完整模块路径
litegate build --dns hw=github.com/libdns/huaweicloud -o litegate-custom
```

Windows 使用现有的 `litegate.exe` 执行上述命令，并将输出命名为 `litegate-custom.exe`。部署后运行新二进制，避免仍使用原来的默认版本。

不指定版本时由 Go 解析服务商版本。确认构建可用后，使用 `litegate-custom plugins list` 查看实际模块版本，下次在 `--dns` 参数后加 `@` 和该版本，固定构建输入。升级 LiteGate 时也需要重新编译所选服务商。源码开发期间使用 `--replace <LiteGate源码目录>`；更多版本、替换和构建选项见 [插件构建与 CLI](../12-plugins/build-and-cli.md)。

内置类型名称保留。如果需要编入另一套 Cloudflare 实现，使用别名，例如 `--dns libdns_cloudflare=cloudflare`；原有 `type: cloudflare` 仍选择内置实现。

## 3. 先配置证书，再按需启用 DDNS

以华为云为例，`type` 填构建时注册的类型；`name` 是该配置项的名称，可由 ECH 等配置引用。使用 `hw=...` 构建时，下例的 `type` 改为 `hw`。

```yaml
auto_cert:
  enabled: true
  email: admin@example.com
  dns_providers:
    - name: huawei-main
      type: huaweicloud
      enabled: true
      domains: ["example.com", "*.example.com"]
      config:
        access_key_id: "env://HW_AK"
        secret_access_key: "env://HW_SK"
        region_id: "cn-south-1"
        zone: "example.com"
        timeout: "2m"
        polling_interval: "10s"
```

运行进程需要提供 `HW_AK`、`HW_SK` 环境变量。示例字段来自 [华为云 Provider](https://github.com/libdns/huaweicloud/blob/master/provider.go)，其他服务商必须使用其 `Provider` 字段的 JSON 名称，不能照搬这些凭证字段。字段值按目标类型转换；复杂字段使用内联 JSON，未知字段会被拒绝。

上例只启用证书 DNS-01，不包含 DDNS 或 ECH。如果已有配置，请显式关闭不需要的 `ddns.enabled` 和 `ech.enabled`；只删除某一个提供商的 DDNS 块不会关闭其他提供商已启用的 DDNS。

确认服务商满足追加与精确删除要求后，在同一个提供商配置项下添加以下 `ddns` 块，与 `config` 同级：

```yaml
ddns:
  enabled: true
  sync_a: true
  sync_aaaa: false
```

启用 DDNS 后，`domains` 用于匹配已加载的 Site / Stream 域名；通配符不会直接生成 DNS 通配符记录。具体同步行为见 [DDNS 动态域名解析](ddns.md)。

`zone`、`ttl`、`timeout`、`polling_interval` 由适配层处理；`secret_token`、`propagation_wait`、`skip_propagation_check`、`disable_complete_propagation`、`recursive_nameservers` 是宿主设置，不传给服务商。省略 `zone` 时通过 SOA 查找权威区域。ECH 的 HTTPS 记录配置见 [ECH 指南](ech.md)，需确认该服务商实际支持 HTTPS。

## 4. 验证和排错

```bash
./litegate-custom plugins list
./litegate-custom -config config.yaml -t
```

`plugins list` 应包含构建时选择的服务商。`-t` 验证配置结构、字段与声明的能力，不会证明远程 API 凭证、权限或传播已正常。部署后应检查证书签发日志，并在 DNS 控制台确认 TXT 清理、A / AAAA 同步或 HTTPS 发布符合预期。

| 问题 | 检查方式 |
|---|---|
| 找不到服务商 | 确认运行的是定制二进制，`type` 与构建别名一致 |
| 提示 libdns v0 API | 选择采用 v1 API 的服务商版本；不能仅升级核心库 |
| 未知配置字段 | 核对所选版本的 JSON 字段名，凭证与 lego 的字段名可能不同 |
| API 授权失败 | 核对凭证、区域、账户的记录读写权限 |
| 找不到 zone | 核对权威托管区域；需要时显式填写 `zone` |
| HTTPS 操作失败 | 核对服务商 API 和实现是否支持 HTTPS，接口声明不代表类型支持 |

libdns 没有对应实现时，可以编写自定义 DNS 插件；仅需要证书 DNS-01 且 lego 有对应实现时，也可以参考 lego 桥接示例。两种方式见 [DNS Provider 插件开发指南](../../dns-provider-plugin-guide.md)。
