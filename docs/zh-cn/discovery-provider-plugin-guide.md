# Discovery 插件开发：以 Nomad 为例

本文按“开发 → 注册 → 编译接入 → 部署配置 → 验证”介绍完整流程。Nomad 是已经实现的样例；Nacos 等注册中心可以复用相同结构，但必须自己实现目标注册中心的查询、认证和订阅。

完整代码：[Nomad 实现](../../pkg/plugins/nomad/nomad.go)、[测试](../../pkg/plugins/nomad/nomad_test.go)、[公共接口](../../pkg/plugin/discovery.go)。下文 Go 片段为简化摘录，需结合完整实现阅读，不是独立可编译文件。

## 1. 创建插件并确定分工

第三方插件是独立 Go module，只依赖公共 `pkg/plugin`，不导入 LiteGate 的 `internal`。建议拆分为 `provider.go`（客户端与查询）、`register.go`（注册）、`provider_test.go` 和用户配置 README。

使用与目标 LiteGate 兼容的 Go 工具链和 SDK 版本。生产锁定依赖版本；本地可在插件 module 中通过 `go mod edit -replace github.com/jamesleeon/LiteGate=../LiteGate` 引用相邻源码，再执行 `go get github.com/jamesleeon/LiteGate`。

例如，在 LiteGate 源码目录的父目录执行以下命令，创建独立插件 module：

```bash
mkdir litegate-discovery-nacos
cd litegate-discovery-nacos
go mod init example.com/acme/litegate-discovery-nacos
go mod edit -replace github.com/jamesleeon/LiteGate=../LiteGate
go get github.com/jamesleeon/LiteGate
```

后续源文件使用插件自己的包名（例如 `package nacos`）。`example.com/acme` 是占位路径，发布时换成实际仓库路径。

插件提供目录和实例；宿主完成 Endpoint 校验、深拷贝、筛选、标签解析、多源融合、路由及负载均衡。不要直接操作 Router 或连接池。

## 2. 实现目录与实例查询

最小契约只有两个方法：

```go
type DiscoveryProvider interface {
    ListServices(ctx context.Context) ([]plugin.DiscoveredService, error)
    Resolve(ctx context.Context, query plugin.DiscoveryQuery) ([]plugin.DiscoveredEndpoint, error)
}
```

Nomad 的 `ListServices` 请求 `/v1/services`，返回 `DiscoveredService{Name, Namespace, Tags}`；`Resolve` 请求 `/v1/service/:service_name`，使用 `query.Namespace` 并把注册记录转换为 Endpoint：

```go
result = append(result, plugin.DiscoveredEndpoint{
    ID: value.ID, Address: value.Address, Port: value.Port,
    Weight: 1, Healthy: true, Protocol: p.protocol,
    ServiceName: value.ServiceName, Namespace: value.Namespace,
    Tags: value.Tags,
    Metadata: map[string]string{"nomad.alloc_id": value.AllocID},
})
```

`Address` 不带 URL scheme，`Port` 是实际可访问端口，`Protocol` 单独指定。Nomad 样例中的 `Healthy: true` 仅表示可参与选择；该接口没有应用检查结果，不能视为就绪证明。其他注册中心应映射真实健康语义，必要时配合 LiteGate 主动健康检查。

实现时注意：

- `ListServices` 和 `Resolve` 可并发调用；返回的切片、Tags、Metadata 必须是之后不再修改的快照。
- 返回真实 namespace。Catalog 优先使用服务返回值，否则回退到外层 Catalog namespace 或 `default`。
- 使用 context、有限超时和完整分页。失败返回 error，不能伪装成成功空列表；成功空结果会下线实例，错误则保留最后成功快照。
- `litegate.*` 路由声明通过 Tags 或适当的 Metadata 交给宿主解析。
- 明确查询字段支持范围；不支持时应报错，例如 Nomad 不支持 job 端口标签 `PortName`。
- `Validate` 做纯配置校验，不连接网络；Factory 构造客户端。不要记录 Token 或可能含凭据的 API 错误正文。

Nomad 的 `parse`、`New`、`get` 展示了严格字段校验、Token 文件轮换、TLS/mTLS、超时、响应大小限制和不完整分页快照保护。

## 3. 注册 Provider 和 Dashboard 元数据

在插件包的 `init()` 中注册。下面的 `parse`、`New` 和 `configExample` 都由完整 Nomad 实现定义：

```go
func init() {
    if err := plugin.RegisterManifest(plugin.Manifest{
        Kind: "discovery", Name: "nomad", Version: "0.1.0",
        APIVersion: plugin.APIVersion, DisplayName: "Nomad",
        Capabilities: []string{"namespace", "tags", "metadata"},
        ConfigExample: configExample,
    }); err != nil {
        panic(err)
    }
    if err := plugin.RegisterDiscoveryProvider("nomad", plugin.DiscoveryRegistration{
        Validate: func(config map[string]string) error {
            _, err := parse(config)
            return err
        },
        Factory: func(config map[string]string, _ *plugin.Dependencies) (plugin.DiscoveryProvider, error) {
            return New(config)
        },
        Info: plugin.DiscoveryProviderInfo{
            Name: "nomad", DisplayName: "Nomad",
            SupportsNamespace: true, SupportsTags: true, SupportsMetadata: true,
            RequiredConfig: []plugin.DiscoveryConfigField{
                {Name: "address", Required: true, Description: "Nomad HTTP API URL"},
            },
        },
    }); err != nil {
        panic(err)
    }
}
```

注册名、`Info.Name` 和 Manifest 名称保持一致，不覆盖内置类型，并处理重复注册错误。完整实现还通过 `OptionalConfig` 描述可选参数。`Dependencies` 可提供日志、发现和共享配置能力。

Dashboard 无需主动注册请求：Manifest 提供版本、能力和配置示例，自动出现在 **Plugins → Service Discovery**；启用 Catalog 并成功创建实例后，首页 **Control Plane Providers** 展示运行状态。`ConfigExample` 使用占位凭据，并与实现支持的字段保持一致。

## 4. 选择轮询或订阅，并释放资源

最小实现可以只使用宿主扫描。Nomad 当前在启动时扫描，之后每 30 秒由 Catalog 刷新，没有实现 Watch。

注册中心支持订阅时，可实现 `DiscoveryWatcher.Watch(ctx, notify)`：先更新本地快照再通知，阻塞直到取消或不可恢复错误。声明 `SupportsWatch: true` 必须实现该接口。通知会合并并触发 Catalog 重扫，目前不携带服务级增量。

Watch 返回错误、提前返回或 panic 时，宿主会以 1s 起、最长 30s 的指数退避重启它，并在每次重启时触发一次重扫；推荐直接返回错误交给宿主重启：这样 Dashboard 的 watch 状态能反映故障；不要在插件内部静默重试，否则 watch 会一直显示为正常而实际已失效。既要覆盖目录增删，也要覆盖实例扩缩容、地址和健康变化。可选 `Start(ctx)` 目前收到 Background context，因此初始化应自行设限；若启动后台任务，`Close(ctx)` 必须负责取消和等待退出。Nomad 的后台工作只有 Watch 长轮询（随 ctx 退出），Close 仅关闭空闲 HTTP 连接。

## 5. 将插件编译进系统

### 构建已有 Nomad 插件

仓库根目录执行：

```bash
go build -o litegate-nomad ./cmd/litegate
./litegate-nomad plugins inspect discovery/nomad
```

`cmd/litegate/plugins.go` 已空导入 Nomad；不要复制后以同名再次注册。Windows 可把输出文件名设为 `litegate-nomad.exe`。

### 编译独立第三方插件

下面的 Nacos 包名是占位示例，需要先实现本地插件或发布对应版本。第一条用于本地开发，第二条用于发布后固定版本：

```bash
litegate build --with example.com/acme/litegate-discovery-nacos=../litegate-discovery-nacos --replace ../LiteGate -o litegate-custom
litegate build --with example.com/acme/litegate-discovery-nacos@v0.1.0 -o litegate-custom
```

本地替换路径必须指向插件自己的 `go.mod` 所在目录；`--replace ../LiteGate` 指定本地核心源码，请按实际位置修改。需要可用的 Go 工具链及依赖访问权限。

也可在自己的 module 中创建 main，空导入插件并调用 LiteGate 启动入口：

```go
package main

import (
    "log"
    "github.com/jamesleeon/LiteGate/pkg/litegate"
    _ "example.com/acme/litegate-discovery-nacos"
)

func main() {
    if err := litegate.Run(); err != nil {
        log.Fatal(err)
    }
}
```

该 main 只显式导入示例插件；若配置还依赖其他外置插件，也要加入相应导入。新增 Go 插件需要重新构建和部署，不是上传文件热安装。更多选项见[构建与 CLI](user/12-plugins/build-and-cli.md)。

## 6. 部署后由用户配置并使用

把构建产物部署为实际运行的 LiteGate，挂载配置、Token 和 CA 文件。Nomad 的全局 `config.yaml`：

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
```

`provider` 必须等于注册名。Factory 只收到内层 `config`，外层 namespace 是 Catalog 回退，不会自动变成插件的 API 查询范围。Token 文件必须位于 LiteGate 可读取的位置。

接下来在 Nomad 注册业务服务，通过 `litegate.*` Tags 声明路由。完整参数、Nomad job、域名配置、ACL、TLS、健康限制和排错步骤见 [Nomad 用户配置说明](user/07-discovery/nomad.md)。

```bash
./litegate-nomad plugins inspect discovery/nomad
./litegate-nomad plugins doctor
./litegate-nomad -config config.yaml -t
./litegate-nomad -config config.yaml
```

CLI 清单和配置预检不能证明连通性。验证目录读取、路由生成和真实请求，并测试扩容、缩容、注册删除、API 故障和恢复。开发测试还应覆盖 Token/TLS、namespace 隔离、成功空结果、错误及取消；样例测试命令为 `go test ./pkg/plugins/nomad ./internal/status`。

## 7. 按这个样例接入 Nacos

| 环节 | 可复用 | 必须适配 |
| :--- | :--- | :--- |
| 服务目录 | ListServices 返回标准列表 | 目标版本 SDK/API、认证、分页、namespace/group |
| 实例查询 | Resolve 返回 Endpoint | 实际地址、端口、稳定 ID、权重、健康与启用状态 |
| 路由元数据 | 宿主统一解析 Tags/Metadata | 注册元数据到 `litegate.*` 的映射和冲突规则 |
| 更新 | Watch 和生命周期接口 | SDK 订阅、快照同步、重连、取消及资源释放 |
| 接入 | 注册、Manifest、编译、Catalog、Dashboard | 唯一注册名 `nacos`、配置校验与用户示例 |

可以照结构开发，但不能只换名字和 URL。必须约定 Nacos group 如何表示、namespace 如何映射，并测试健康及订阅行为。本文未实现 Nacos；选择 SDK/API 时应核对目标部署版本。
