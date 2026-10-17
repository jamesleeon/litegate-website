# 命名条件：给请求条件起个名字

路由条件一复杂，`match: {path: [...], method: [...], header: {...}}` 就会挤在一行里，读配置时要先在脑子里解析一遍才知道这条路由管什么。命名条件（matchers）把条件单独定义、起一个名字，路由只写 `match: "@名字"`：

```text
matchers:
  blocked: {path: [/xmlrpc.php, "*.sql"]}   # 定义：这是什么请求
routes:
  - match: "@blocked"                       # 使用：这类请求怎么处理
    respond: {status: 403}
```

先记住三条：

1. **它只是起名字。** `match: "@blocked"` 和把定义原样写进 `match:` 完全等价，加载时就地展开，运行时没有区别。
2. **顺序和书写位置无关。** 优先级按条件本身决定，见 [第 3 节](#3-谁先匹配优先级规则)。
3. **`@名字` 必须加引号。** `@` 在 YAML 里是保留字符，不加引号会直接报解析错误。

---

## 1. 拦截扫描请求，写请求和读请求分流

最典型的用法：挡掉常见扫描路径，`POST` 转到单独的写服务，其余请求走默认后端。

<!-- case: matchers-basic -->
```yaml
site: example.com
matchers:
  blocked: {path: [/xmlrpc.php, /.env, "*.sql"]}
  post: {method: POST}
routes:
  - match: "@blocked"
    respond: {status: 403, body: forbidden}
  - match: "@post"
    proxy: localhost:8081
proxy: localhost:8080
```

```check
GET  http://example.com/xmlrpc.php          => 403 "forbidden"
GET  http://example.com/.env                => 403 "forbidden"
# * 匹配任意字符，包括 /，所以子目录里的 .sql 也会被拦
GET  http://example.com/backup/db.sql       => 403 "forbidden"
# 通配符匹配整个路径：db.sql.txt 不以 .sql 结尾
GET  http://example.com/db.sql.txt          => 8080 /db.sql.txt
POST http://example.com/orders              => 8081 /orders
GET  http://example.com/orders              => 8080 /orders
```

---

## 2. 条件怎么写

一个命名条件里可以写这些字段，和内联 `match` 完全一样：

| 字段 | 含义 | 例子 |
|---|---|---|
| `path` | 单个字符串：精确匹配；列表：任一命中即可，支持 `*` 通配 | `/login`、`[/a, "/b/*"]` |
| `prefix` | 前缀匹配，按路径段 | `/api` |
| `method` | 单个或列表 | `POST`、`[PUT, DELETE]` |
| `header` | 请求头等于指定值 | `{X-Canary: "1"}` |
| `query` | 查询参数等于指定值 | `{debug: "1"}` |
| `rule` | 规则表达式，兜底复杂情况 | `` PathRegexp(`(?i)^/admin`) `` |

**不同字段之间是「并且」，`path` 列表内部是「或者」。** 下面的 `api-write` 表示「`/api` 下的、`POST`/`PUT`/`DELETE` 请求」，`canary` 表示「带 `X-Canary: 1` 头的请求」：

<!-- case: matchers-combine -->
```yaml
site: api.example.com
matchers:
  api-write: {prefix: /api, method: [POST, PUT, DELETE]}
  canary: {header: {X-Canary: "1"}}
routes:
  - match: "@canary"
    proxy: localhost:8082           # 灰度：带头的请求全部进新版本
  - match: "@api-write"
    proxy: localhost:8081           # 写请求走主库服务
/api:
  proxy: localhost:8080             # 其余 /api 请求走只读服务
respond: {status: 404, body: not found}
```

```check
PUT  http://api.example.com/api/orders/7             => 8081 /api/orders/7
GET  http://api.example.com/api/orders/7             => 8080 /api/orders/7
GET  http://api.example.com/api/orders/7 X-Canary: 1 => 8082 /api/orders/7
# POST 但不在 /api 下：api-write 两个条件只满足一个
POST http://api.example.com/upload                   => 404 "not found"
```

`path` 通配的细节：

- 只有 `*` 是通配符，匹配零个或多个任意字符（包括 `/`）；`?`、`[]` 是普通字符。
- 匹配的是**整个路径**（不含查询参数），所以 `"*.sql"` 是「以 `.sql` 结尾」，`"/admin/*"` 是「`/admin/` 下的任何路径」。
- 以 `*` 开头的字符串在 YAML 里必须加引号。
- **区分大小写**：`/xmlrpc.php` 拦不住 `/XMLRPC.PHP`。做安全拦截时建议用 `rule` 加 `(?i)`：

<!-- case: matchers-ignore-case -->
```yaml
site: example.com
matchers:
  blocked:
    rule: "PathRegexp(`(?i)^/xmlrpc\\.php$`) || PathRegexp(`(?i)\\.sql$`)"
routes:
  - match: "@blocked"
    respond: {status: 403}
proxy: localhost:8080
```

```check
GET http://example.com/xmlrpc.php      => 403
GET http://example.com/XMLRPC.PHP      => 403
GET http://example.com/dump/DB.SQL     => 403
GET http://example.com/index.php       => 8080 /index.php
```

---

## 3. 谁先匹配：优先级规则

和 Caddy 一样，**带条件的路由比只看路径前缀的路由更具体**。同一站点内按下面的顺序尝试，命中即停止：

| 顺序 | 路由类型 | 例子 |
|---|---|---|
| 1 | 显式 `priority` 更高的路由 | `priority: 100` |
| 2 | 精确路径 | `path: /login`、`path: [/login]` |
| 3 | 没有 `path` / `prefix` 的条件路由 | `@blocked`（通配 path）、`@post`、`@canary` |
| 4 | 前缀路由，长的优先 | `/api/v2` 先于 `/api` |
| 5 | 站点级动作（兜底） | 顶层的 `proxy`、`spa` |

所以拦截规则不会被 `/api` 这样的前缀路由「抢走」：

<!-- case: matchers-order -->
```yaml
site: example.com
matchers:
  blocked: {path: ["*.sql"]}
routes:
  - match: "@blocked"
    respond: {status: 403}
  - match: {path: /export/report.sql}   # 精确路径排在条件路由之前
    proxy: localhost:8081
/api:
  proxy: localhost:8080
spa: ./dist
```

```check
# /api 前缀路由排在 @blocked 后面
GET http://example.com/api/backup.sql        => 403
GET http://example.com/api/orders            => 8080 /api/orders
# 精确路径比 @blocked 更优先
GET http://example.com/export/report.sql     => 8081 /export/report.sql
GET http://example.com/settings              => 200 "<h1>dist</h1>"
```

两点要注意：

- **`@post` 这类只看方法的条件，会接走整个站点的该方法请求**，包括 `/api` 下的。只想管某个路径时，把 `prefix` 写进条件里（见第 2 节的 `api-write`）。
- 想让条件路由压过精确路径，给它写更高的 `priority`。

---

## 4. 在命名条件上追加条件

`match` 也可以写成列表，列表里的每一项必须**同时满足**：可以是 `"@名字"`、内联条件，或 `/前缀` 简写。这样同一个命名条件就能被多条路由复用，每条路由各自加上自己的条件：

<!-- case: matchers-compose -->
```yaml
site: api.example.com
matchers:
  api: {prefix: /api, header: {X-Tenant: acme}}
  api-write: ["@api", {method: [POST, PUT, DELETE]}]   # 定义里也能组合
routes:
  - match: "@api-write"
    proxy: localhost:8081
  - match: ["@api", {query: {debug: "1"}}]
    proxy: localhost:8082
  - match: "@api"
    proxy: localhost:8080
respond: {status: 404, body: not found}
```

```check
PUT  http://api.example.com/api/orders/7 X-Tenant: acme          => 8081 /api/orders/7
GET  http://api.example.com/api/orders/7?debug=1 X-Tenant: acme  => 8082 /api/orders/7?debug=1
GET  http://api.example.com/api/orders/7 X-Tenant: acme          => 8080 /api/orders/7
# 缺少 X-Tenant：三条路由都要求 @api，全部不命中
PUT  http://api.example.com/api/orders/7                         => 404 "not found"
```

合并规则：

- `rule` 用「并且」连接；`header`、`query` 合并，但同一个键不能出现两次（`header` 不区分大小写）。
- `prefix`、`path`、`method` 等其余字段只能由一项提供；两项写了相同的值可以，写了不同的值直接报错，而不是悄悄取其中一个。
- 列表不能嵌套；需要分层就在 `matchers` 里定义，再按名字引用。命名条件之间可以互相引用，循环引用会报错。

<!-- expect-error: composed matchers set conflicting prefix -->
```yaml
site: example.com
matchers:
  api: {prefix: /api}
routes:
  - match: ["@api", {prefix: /admin}]
    respond: ok
proxy: localhost:8080
```

---

## 5. 什么时候不用命名条件

- **只有一个路径前缀**：直接写路径键 `/api:`，比 `matchers` 更短。
- **多条路由共用鉴权、限流等策略**：那是治理配置，用 [snippets](03-governance.md#5-多个接口共用一套策略snippets)，不是 matchers。
- **想「所有路由之前统一执行」的安全策略**：`@blocked` 是一条普通的拒绝路由，只在它排在前面时生效；如果你用 `priority` 把别的路由排到它前面，那些路由就不受它保护。全站必须执行的拦截应放进 `use` 中间件。

---

## 6. 常见错误

### 忘了加引号

<!-- expect-error: found character that cannot start any token -->
```yaml
site: example.com
matchers:
  post: {method: POST}
routes:
  - match: @post
    proxy: localhost:8081
proxy: localhost:8080
```

`@` 不能作为 YAML 未加引号字符串的开头，写成 `match: "@post"`。

### 引用了不存在的名字

<!-- expect-error: undefined matcher reference -->
```yaml
site: example.com
matchers:
  post: {method: POST}
routes:
  - match: "@posts"
    proxy: localhost:8081
proxy: localhost:8080
```

名字区分大小写。引用先找本站点的 `matchers`，再找 `sites/_shared.yaml` 里的公共定义；其他站点文件里的定义引用不到。

### 定义是空的或字段写错

<!-- expect-error: at least one match criterion is required -->
```yaml
site: example.com
matchers:
  empty: {}
proxy: localhost:8080
```

没被任何路由引用的定义也会校验，写错字段（例如 `methods`）同样会报错。

### 通配路径没有以 `/` 或 `*` 开头

<!-- expect-error: path must start with / -->
```yaml
site: example.com
matchers:
  blocked: {path: [xmlrpc.php]}
routes:
  - match: "@blocked"
    respond: {status: 403}
proxy: localhost:8080
```

### 同一个条件用在两条路由上

<!-- expect-error: duplicate normalized match -->
```yaml
site: example.com
matchers:
  post: {method: POST}
routes:
  - match: "@post"
    proxy: localhost:8081
  - match: {method: post}      # 展开后和 @post 相同（方法不区分大小写）
    proxy: localhost:8082
proxy: localhost:8080
```

两条路由条件完全相同时，后一条永远不会被命中，所以直接报错。要复用同一个命名条件，用列表给每条路由追加不同的条件（见 [第 4 节](#4-在命名条件上追加条件)）。

完整字段说明见 [站点配置参考](../03-configuration/site-config.md#命名请求条件matchers)。
