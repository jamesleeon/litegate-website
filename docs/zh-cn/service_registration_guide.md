# 服务注册与 LiteGate 标签

本文说明各注册中心中标签写在哪里。标签的写法见[服务标签使用指南](user/03-configuration/tag-dsl.md)，每个标签的含义见[服务标签参考](user/03-configuration/tag-reference.md)。

## 两类标签

| 类别 | 例子 | 实例之间 |
| :--- | :--- | :--- |
| 路由与资源标签 | `litegate.http.host=orders.example.com`、`litegate.http.services.orders.timeout=30s` | 必须一致 |
| 实例标签 / metadata | `version=1.0.0`、`sid=c1`、`litegate.instance.weight=2` | 可以不同 |

Service 的 selector 直接匹配实例上报的 metadata(如 `sid=c1`)。注册中心不能上报 metadata 时，改写成 `litegate.instance.labels.sid=c1`。

## 最简注册

大多数服务只需要一个标签：

```properties
litegate.http.host=orders.example.com
```

它会在 80 与 443 上把 `orders.example.com` 的全部请求转发到本服务。需要超时、重试、多个路由等时，改用命名资源：

```properties
litegate.http.routers.orders.match.hosts=orders.example.com
litegate.http.routers.orders.match.path_prefix=/api
litegate.http.services.orders.timeout=30s
litegate.http.services.orders.healthcheck.path=/healthz
```

## 写在哪里

| 注册中心 | 位置 | 说明 |
| :--- | :--- | :--- |
| Litemesh | 服务 `meta` | 键值对 |
| Consul | 服务 `Meta`，或 `Tags` 中的 `key=value` | 两处都会读取 |
| Docker / Swarm | 容器或服务的 labels | 有任何 `litegate.*` label 即被发现；`litegate.enable=false` 可显式排除 |
| Kubernetes | Service annotations，Service 需带 label `litegate.io/expose=true` | 可直接写 `litegate.*`，也可用简写 `litegate.io/host`、`litegate.io/path`、`litegate.io/prefix`、`litegate.io/strip-path`，它们映射到快捷模式 |

Consul 示例：

```json
{
  "ID": "orders-1",
  "Name": "orders",
  "Port": 8080,
  "Meta": {
    "litegate.http.routers.orders.match.hosts": "orders.example.com",
    "litegate.http.routers.orders.match.path_prefix": "/api",
    "litegate.http.services.orders.healthcheck.path": "/healthz",
    "version": "1.0.0",
    "sid": "c1"
  }
}
```

Docker 示例：

```yaml
services:
  orders:
    image: orders:1.0
    labels:
      - "litegate.http.host=orders.example.com"
```

## 上线前检查

1. 同一服务的所有实例携带完全一致的路由与资源标签；每实例不同的值只能是实例标签。
2. 快捷模式的 4 个键不要与 `litegate.http.routers.*` 等命名资源混用。
3. 用 dashboard 的服务标签页或 MCP `preview_service_tags` 确认没有诊断。
