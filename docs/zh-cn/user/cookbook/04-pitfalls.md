# 常见错误与报错对照

下面每个例子都是**错误写法**，后面是 LiteGate 加载时给出的报错（原文片段），以及正确写法。
遇到报错时可以直接在本页搜索报错里的英文关键词。

运行 `litegate -t -config config.yaml` 可以在不重启的情况下检查全部站点文件。

---

## 1. 从旧配置复制了 `domain`

<!-- expect-error: site and domain cannot be combined -->
```yaml
site: app.example.com
domain: app.example.com
proxy: localhost:8080
```

新写法只用 `site`。旧格式的 `domain`、`force_https`、`routes[].action` 不要混进来，对照表见 [站点配置](../03-configuration/site-config.md#旧标准字段与-v2-对照)。

---

## 2. 一条路由写了两个动作

<!-- expect-error: exactly one terminal action is required -->
```yaml
site: app.example.com
/static:
  file_server: ./public
  spa: ./dist
```

`proxy`、`file_server`/`serve`、`spa`、`respond`、`redirect` 等每条路由只能有一个。要「先找文件、找不到回首页」就只写 `spa`。

---

## 3. 端口写了两遍

<!-- expect-error: port is already specified in site -->
```yaml
site: :9090
port: 9090
proxy: localhost:8080
```

`site: :9090` 已经包含端口，删掉 `port`。

---

## 4. `*` 开头没加引号

<!-- expect-error: did not find expected alphabetic or numeric character -->
```yaml
site: *:9090
proxy: localhost:8080
```

`*` 在 YAML 里有特殊含义，写成 `site: "*:9090"`，或者直接 `site: :9090`。

---

## 5. 同一路径既区分又不区分大小写

<!-- expect-error: duplicate normalized match -->
```yaml
site: api.example.com
/goapi:
  proxy: localhost:8080
~/goapi:
  proxy: localhost:8081
```

二选一：要兼容各种大小写就只留 `~/goapi`。

---

## 6. 精确路径上用 `strip_prefix`

<!-- expect-error: true requires a prefix match -->
```yaml
site: api.example.com
routes:
  - match: {path: /api/login}
    proxy: localhost:8080
    strip_prefix: true
```

`strip_prefix` 只对前缀匹配（路径键 `/api:` 或 `match: {path_prefix: /api}`）有意义。

---

## 7. 给静态文件写了 `request_headers`

<!-- expect-error: route request headers require proxy -->
```yaml
site: www.example.com
/docs:
  file_server: ./public
  request_headers:
    X-Env: prod
```

`request_headers` 是发给后端的，只能用在 `proxy` 上。想给浏览器加头用 `response_headers`。

---

## 8. 有子路由时把 cors 写在站点级

<!-- expect-error: with child routes, put root processing in an explicit / route -->
```yaml
site: api.example.com
cors:
  allowed_origins: ["*"]
/users:
  proxy: localhost:8080
/orders:
  proxy: localhost:8081
```

有子路由时，站点级的 cors / auth / 限流只会作用于兜底的根路由，不会下发到 `/users`、`/orders`。为了避免误以为全站生效，这种写法直接报错。
只想给兜底路由加，就写进显式的 `/:` 路由；想给每个接口加，写到对应路由上，或者用 [snippets](03-governance.md#5-多个接口共用一套策略snippets) 复用：

<!-- case: cors-per-route -->
```yaml
site: api.example.com
snippets:
  open: {cors: {allowed_origins: ["*"]}}
/users:
  import: open
  proxy: localhost:8080
/orders:
  import: open
  proxy: localhost:8081
```

---

## 9. 片段里放了后端地址

<!-- expect-error: snippets accept route governance only -->
```yaml
site: api.example.com
snippets:
  backend:
    proxy: localhost:8080
/users:
  import: backend
```

片段只放治理策略，`proxy` 写在使用片段的路由里。多处共用同一组后端请用 `services` + `service: 名称`。

---

## 10. 片段和本地重复写了同一个策略

<!-- expect-error: field conflicts with imported configuration -->
```yaml
site: api.example.com
snippets:
  limited: {rate_limit: 100}
/sms:
  import: limited
  rate_limit: 5
  proxy: localhost:8080
```

除了请求头 / 响应头，片段里的字段不能在本地再写一次（避免「以为改成了 5，其实是 100」）。
需要不同的值就拆成两个片段，或者这条路由不导入它。

---

## 11. 引用了没定义的中间件

<!-- expect-error: undefined middleware reference -->
```yaml
site: api.example.com
use: [audit-log]
proxy: localhost:8080
```

`use` 引用的名字必须在同一文件的 `middlewares` 下定义，见 [中间件](../05-middleware/pipeline.md)。

---

## 不报错但容易踩的坑

- **HTTPS 默认关闭。** 新写法默认 `https: false`，写 `site: example.com:443` 也不会自动开启，要显式写 `https: true`。
- **保留路径。** `/healthz`、`/readyz`、`/metrics`、`/_litegate` 等由网关自身使用，站点里不要用它们做路由（会被网关接管，发布校验也会报错）。
- **前缀按路径段匹配。** `/api` 不匹配 `/apix`；要匹配任意前缀字符请用 `routes` + `match.rule`。
- **`redirect: 地址` 简写是 302。** 永久跳转要写成 `redirect: {location: ..., status: 301}`。
