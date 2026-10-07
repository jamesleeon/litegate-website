# Discovery Provider 插件开发指南

Discovery Provider 允许独立 Go module 向 LiteGate 提供服务和 Endpoint，不需要修改
`internal/discovery` 的 switch。适合 Nacos、Eureka、etcd、ZooKeeper 和企业自研注册中心。

## 1. 能力边界

Provider 负责：

- 列出当前服务快照；
- 按服务名、命名空间、端口名和标签解析 Endpoint；
- 可选监听注册中心变化并通知宿主；
- 可选启动和关闭资源。

LiteGate 负责 Endpoint 校验、数量限制、深拷贝、筛选、健康状态、缓存、多源融合、
负载均衡和 Catalog 动态路由发布。插件不能直接访问 Router、连接池或内部 Endpoint。

Kubernetes Ingress/Gateway 这类“生成路由配置”的控制器不属于 Discovery V1；这里仅处理
服务与 Endpoint，避免注册中心接口被特定编排平台的数据模型污染。

## 2. 最小接口

```go
type provider struct{}

func (provider) ListServices(ctx context.Context) ([]plugin.DiscoveredService, error) {
    return []plugin.DiscoveredService{{Name: "orders", Namespace: "prod"}}, nil
}

func (provider) Resolve(ctx context.Context, q plugin.DiscoveryQuery) ([]plugin.DiscoveredEndpoint, error) {
    return []plugin.DiscoveredEndpoint{{
        ID: "orders-1", Address: "10.0.0.8", Port: 8080,
        Healthy: true, Weight: 1, ServiceName: q.ServiceName,
    }}, nil
}
```

`DiscoveryQuery.Namespace` 表示发现源的命名空间。Catalog 扫描优先使用
`DiscoveredService.Namespace`；为空时回退到 Catalog 的 `namespace`，未配置时为 `default`。
插件需把该值映射到自己的注册中心语义；若 LiteGate 与注册中心使用不同命名空间，应在插件配置中显式定义映射。

实现会被并发调用。宿主不会在调用 `ListServices` 或 `Resolve` 期间持有快照锁；同一实例的服务查询可以并发执行。每次返回的切片、Tags 和 Metadata 都应视为快照；LiteGate 会再次复制，
但插件也不应在返回后继续修改它们。

## 3. 注册、校验和配置

```go
func init() {
    err := plugin.RegisterDiscoveryProvider("my_registry", plugin.DiscoveryRegistration{
        Validate: func(config map[string]string) error {
            if config["endpoint"] == "" { return errors.New("endpoint is required") }
            return nil
        },
        Factory: func(config map[string]string, deps *plugin.Dependencies) (plugin.DiscoveryProvider, error) {
            return newProvider(config["endpoint"], deps.Logger)
        },
        Info: plugin.DiscoveryProviderInfo{
            Name: "my_registry", SupportsWatch: true,
            SupportsNamespace: true, SupportsTags: true, SupportsMetadata: true,
        },
    })
    if err != nil { log.Printf("register discovery provider: %v", err) }
}
```

全局配置使用通用 `config`，不会再为每个服务商向 `CatalogConfig` 添加字段：

```yaml
service_discovery:
  catalogs:
    - name: registry-east
      enabled: true
      provider: my_registry
      config:
        endpoint: "https://registry-east.example.com"
        token: "${REGISTRY_TOKEN}"
    - name: registry-west
      enabled: true
      provider: my_registry
      config:
        endpoint: "https://registry-west.example.com"
        token: "${REGISTRY_WEST_TOKEN}"
```

同一种 Provider 可以配置多个命名实例。`name` 在该 Provider 类型内必须唯一；省略时按配置顺序生成
`my_registry-1`、`my_registry-2`。

## 4. Watch 与生命周期

需要事件驱动时实现：

```go
func (p *provider) Watch(ctx context.Context, notify func()) error {
    for {
        select {
        case <-p.changed:
            notify() // 只通知变化；宿主会合并事件并重新 List/Resolve
        case <-ctx.Done():
            return nil
        }
    }
}
```

可选实现 `DiscoveryStarter.Start(ctx)` 和 `DiscoveryCloser.Close(ctx)`。Factory、Validate、
ListServices、Resolve、Watch 和 Close 的 panic 都不会越过宿主边界。Watch 必须阻塞并监听
ctx，不能每次通知都创建永久 goroutine。

## 5. 安全与错误语义

- Address 只能是主机/IP，不得包含 scheme、路径、查询或反斜线；端口必须在 1..65535。
- Protocol 支持 `http`、`https`、`h2c`、`grpc`、`grpcs`、`tcp`、`tls` 和 `udp`；省略时为 `http`。
- Endpoint 返回的服务名和命名空间必须与查询一致；服务名、命名空间不能包含内部键分隔符 `:`。
- 单次最多返回 10,000 个服务或 Endpoint，超过即拒绝，避免错误插件耗尽内存。
- 服务列表和 Endpoint 快照按 Provider 实例分别保留。列表查询失败时沿用该实例最后一次成功的服务列表和已有 Endpoint；Resolve 失败时沿用同一查询最后一次成功的 Endpoint。尚无快照的失败实例不会产生数据，且会记录告警和降级状态。
- 列表查询失败时，已有 Endpoint 快照的查询直接返回旧数据，暂停调用 Resolve，直到列表查询恢复。因此即使 Resolve 接口仍可用，已有快照也不会在此期间更新。
- 查询成功但返回空列表表示真实删除，会替换旧快照；成功的服务列表还会清理已删除服务的 Endpoint 快照。故障期间的旧快照持续保留至恢复，LiteGate 的主动/被动健康检查仍然有效。
- 非法 Endpoint 单独跳过，并记录 warn 和 failure；其它合法实例继续使用。若整批 Endpoint 均非法，则视为查询失败并尝试沿用旧快照。
- 含非法 Endpoint 的 Resolve 不记录成功，保持 degraded；后续成功查询可恢复 active。状态按实例记录，并非跨服务聚合的持续数据质量状态，成功的 ListServices 或其它 Resolve 也可将其恢复。
- Provider 报告的 `Healthy` 是发现源视角，LiteGate 仍会叠加主动/被动健康检查。
- Token 不应写日志；敏感字段应在 `Info.RequiredConfig/OptionalConfig` 标记 `Secret`。

## 6. 编译和验证

本地插件：

```bash
litegate build --with example.com/acme/registry=../registry-plugin -o litegate
litegate plugins list
litegate -t -config config.yaml
```

`plugins list` 验证插件确实编入；`-t` 会执行纯配置校验，并在 Provider 未注册时直接失败。
启动成功后，Dashboard 的 “Control Plane Providers” 会按实例展示插件名称、实例名和公开能力，
`GET /status/json` 的 `discovery_providers` 字段提供相同的非敏感运行时清单，并包含
`state`、`watch_state`、`last_success`、`last_error` 和 `failure_count`，用于识别发现源降级与 Watch 退出。
完整可编译实现见 [examples/plugins/discovery/memory](https://github.com/jamesleeon/LiteGate/blob/master/examples/plugins/discovery/memory)。
