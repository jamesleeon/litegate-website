# Unified Entry Model

LiteGate 的一个核心特点，是最终对外提供的入口，不一定只来自一份静态 YAML。

很多时候，一个域名下的入口是由两部分一起组成的：

- 静态站点配置：由 `sites/*.yaml` 或 `sites/*.lite.yaml` 声明。
- 动态服务入口：由服务注册信息、服务发现、Tag 或 Magic Ingress 在运行时生成。

这两部分最终会在 LiteGate 内部合并成同一个入口面。

---

## 1. 静态部分是什么

静态部分通常用于声明：

- 前端站点根目录
- SPA 回退
- 明确写死的 `/api` 路由
- 认证、中间件、证书等稳定入口规则

最常见的例子是：

```yaml
domain: a.example.com
routes:
  - match:
      path_prefix: /
    action:
      type: serve
      root: "/srv/www/app"
      spa: true
```

这部分通常是“前端入口”或“稳定流量契约”。

---

## 2. 动态部分是什么

动态部分通常来自服务发现源，例如 Litemesh、LiteDeploy、Docker、Consul，或通过 blocking query 接入的 Discovery 聚合层。

服务本身可以通过资源标签声明自己的上线意图，例如：

- `litegate.http.host`(快捷模式，只需一个域名时)
- `litegate.entrypoints.<name>.*`
- `litegate.http.routers.<name>.*`
- `litegate.http.services.<name>.*`
- `litegate.http.middlewares.<name>.*`

LiteGate 会读取这些动态信息，在运行时自动生成路由、服务选择策略和部分治理能力。标签新开监听端口需要网关在 `service_discovery.tag_entrypoints.allowed_ports` 中放行。

这部分通常是“后端服务入口”或“注册即上线”能力。

---

## 3. 两者怎么合并

LiteGate 并不是在“静态模式”和“动态模式”之间二选一。

更常见的真实场景是：

- 前端页面由静态 YAML 托管
- 后端 API 由动态服务发现自动接入
- 两者一起构成同一个域名下的完整站点

例如：

- `https://a.example.com/console` 来自静态前端站点
- `https://a.example.com/api/...` 来自已注册的后端服务

用户看到的是一个完整站点。  
LiteGate 内部看到的是“静态站点声明 + 动态服务路由”的合并结果。

---

## 4. 没有域名也能成立

这个模型不只适合公网域名。

如果服务注册了：

```text
litegate.entrypoints.api-9090.address=:9090
litegate.http.routers.api.entrypoints=api-9090
litegate.http.routers.api.match.path_prefix=/
```

该 Router 没有 Host 条件，因此接受 9090 端口上的任意 Host，可以通过：

```text
http://<gateway-ip>:9090/
```

访问。

这意味着 LiteGate 也可以作为内部无域名微服务入口：

- 多个 Router 可共用同一个 EntryPoint
- 通过各 Router 的 Rule 显式区分路径
- 同名多实例仍然可以做负载均衡

---

## 5. MCP 看到了什么

MCP 现在已经能很好地帮助 AI 配置 LiteGate：

- 读取站点配置
- 读取服务列表和服务详情
- 生成和保存配置
- 校验配置
- reload 网关
- verify 站点
- lookup route
- 查看 recent requests 和 recent errors

也就是说，AI 已经能完成“读环境 -> 产出配置 -> 应用 -> 验证 -> 排错”的闭环。

---

## 6. MCP 还不知道什么

MCP 现在已经能看到：

- 静态站点片段
- 动态服务片段
- 最终命中结果

但它不一定总能自动向用户解释清楚：

- 某个入口到底来自静态 YAML 还是动态服务发现
- 两者是如何在运行时合并成一个完整站点的

所以对人类用户来说，仍然需要理解这个核心模型：

> LiteGate 的最终入口，可能不是写在一份文件里的，而是由静态声明和动态发现一起组成的。

---

## 7. 推荐理解方式

如果你把 LiteGate 只看成“反向代理”，就容易困惑。  
如果你把 LiteGate 看成“统一入口层”，这套设计就会非常自然。

可以用一句话理解：

> 静态 YAML 负责声明稳定入口，动态发现负责让服务自己长出来，LiteGate 在运行时把它们收敛成一个完整站点。

---

## Next

建议继续阅读：

- [Sites And Routes](./sites-and-routes.md)
- [Discovery](./discovery.md)
- [Routing Priority](./routing-priority.md)
