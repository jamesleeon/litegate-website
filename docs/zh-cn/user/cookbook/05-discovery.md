# 服务发现 + 站点文件：自动合并（Hybrid）

后端服务通过 litemesh / Consul 注册时带上标签，例如：

```text
litegate.http.host=stock.example.com
litegate.http.pathprefix=/apiv2
```

LiteGate 会自动为 `stock.example.com` 生成 `/apiv2` 路由。如果 `sites/` 里**同一个域名**还有站点文件，两边的路由会合并成一个站点（Dashboard 里显示为 Hybrid），不需要任何额外配置。

合并规则只有三条：

1. **更长的路径优先。** catalog 的 `/apiv2` 比文件里的 `/` 更具体，所以 `/apiv2/...` 走服务发现，其余走文件。
2. **同样的路径，文件优先。** 文件里也写了 `/apiv2` 时，catalog 的 `/apiv2` 不会生效（状态页会提示被遮蔽）。
3. **服务全部下线时，catalog 路由会被移除**，请求落回文件里的路由。

---

## 1. 前端（KV 发布）+ 后端（服务发现）

前端静态资源通过 KV 发布，后端 API 实例自动注册。站点文件只需要描述前端：

<!-- case: hybrid-kv-spa -->
```yaml
site: stock.example.com
spa:
  root: /home/litegate/www/stock
  kv_mode: true                          # 从 KV 同步前端包
  kv_provider: litemesh                  # litemesh / consul / http
  kv_key: litegate/config/front/stock
  keep_versions: 3                       # 本地保留的历史版本数
```

等价的旧格式写法（继续兼容，无需迁移）：

<!-- case: hybrid-kv-spa-legacy -->
```yaml
domain: stock.example.com
routes:
  - match:
      path_prefix: /
    action:
      type: serve
      root: /home/litegate/www/stock
      spa: true
      kv_mode: true
      kv_provider: litemesh
      kv_key: litegate/config/front/stock
      keep_versions: 3
```

两种写法编译出的路由完全相同（包括自动生成的路由名），换写法不需要重新发布前端包。

---

## 2. 服务下线时不要让 SPA 吞掉 API 请求

上面的配置有一个隐患：`stock` 服务的实例**全部**注销时（例如滚动发布中途、服务崩溃），`/apiv2` 路由消失，`/apiv2/quote` 会落到 SPA 兜底，返回 `index.html` 和 **200**。前端拿到 HTML 去解析 JSON，报的错和真实原因毫无关系。

加一个优先级为 -1 的占位路由：服务在线时让位给 catalog 路由，服务不在时返回明确的 503。

<!-- case: hybrid-placeholder -->
```yaml
site: stock.example.com
/apiv2:
  priority: -1             # 低于 catalog 路由（默认 0），只在服务不在时生效
  respond:
    status: 503
    content_type: application/json
    body: '{"error":"service unavailable"}'
spa: ./dist
```

```check
# 服务没有注册时
GET http://stock.example.com/apiv2/quote     => 503 "service unavailable"
GET http://stock.example.com/settings        => 200 "<h1>dist</h1>"
```

服务注册后，`/apiv2/quote` 由 catalog 路由转发给后端实例；服务再次全部下线又回到 503。这个切换过程由测试 `TestHybridPlaceholderYieldsToCatalogRoute` 覆盖。

> 不写 `priority: -1` 的话，同路径时文件优先，catalog 路由将永远不会生效。

---

## 3. 文件里的设置对 catalog 路由生效吗？

| 写在站点文件顶层的 | 对 catalog 路由 |
|---|---|
| `https: true` | 生效（任意一方开启即全站跳转 HTTPS） |
| `ip_restriction` | 生效（站点级访问控制） |
| `max_request_body_size`、`error_pages` | 生效 |
| `use`、`request_headers`、`response_headers` | **不生效**，只作用于本文件定义的路由 |
| `cors`、`auth`、`rate_limit` 等路由治理 | **不生效**，它们属于具体路由 |

catalog 路由的鉴权、限流、跨域请通过服务标签配置，见 [服务标签使用指南](../03-configuration/tag-dsl.md)。

---

## 4. 合并不上的情况

- **站点带了非标准端口。** `site: stock.example.com:8443` 和服务标签里的 `stock.example.com` 是两个不同的站点，不会合并。端口 80 / 443 例外，视为同一站点。
- **域名不完全一致。** 合并按完整域名匹配，`stock.example.com` 和 `www.stock.example.com` 互不相干；通配站点 `*.example.com` 也不会和具体域名的服务合并。
