# 路径：按路径分流、改路径、跳转

先记住两条规则，下面所有案例都基于它们：

1. **路径键按「路径段」匹配。** `/api` 匹配 `/api`、`/api/orders`，但**不匹配** `/apix`。
2. **越具体的路径越优先，站点级动作是兜底。** 和写的先后顺序无关。

---

## 1. 前端 SPA + 后端 API

Vue / React 项目最常见的部署方式：`/api` 走后端，其余都交给前端。

<!-- case: spa-api -->
```yaml
site: app.example.com
/api:
  proxy: localhost:8080
  strip_prefix: true      # 后端不需要 /api 前缀时打开
spa: ./dist
```

```check
GET http://app.example.com/api/orders         => 8080 /orders
GET http://app.example.com/                   => 200 "<h1>dist</h1>"
# 前端路由刷新也能拿到 index.html
GET http://app.example.com/settings/profile   => 200 "<h1>dist</h1>"
GET http://app.example.com/assets/app.js      => 200 "console.log"
```

- `spa` 和 `file_server` 的区别：找不到文件时，`spa` 返回 `index.html`，`file_server` 返回 404。
- 后端本身就带 `/api` 前缀时，删掉 `strip_prefix` 即可。

---

## 2. 多个后端按路径拆分

<!-- case: path-split -->
```yaml
site: api.example.com
/users:
  proxy: localhost:8080
/orders:
  proxy: localhost:8081
/orders/export:           # 更具体的路径优先，和书写顺序无关
  proxy: localhost:8082
respond:
  status: 404
  body: unknown api
```

```check
GET http://api.example.com/users/42           => 8080 /users/42
GET http://api.example.com/orders/7           => 8081 /orders/7
GET http://api.example.com/orders/export/csv  => 8082 /orders/export/csv
# 按路径段匹配：/usersx 不属于 /users
GET http://api.example.com/usersx             => 404 "unknown api"
```

---

## 3. 去掉前缀、换前缀

后端是老系统，接口实际挂在 `/legacy-app/` 下，但对外想暴露为 `/v1`：

<!-- case: prefix-rewrite -->
```yaml
site: api.example.com
/v1:
  proxy: localhost:8080
  strip_prefix: true
  prepend_prefix: /legacy-app
```

```check
GET http://api.example.com/v1/orders?id=3     => 8080 /legacy-app/orders?id=3
```

- `strip_prefix: true` 去掉匹配到的前缀（这里是 `/v1`）；`prepend_prefix` 再加上新前缀。
- 更复杂的改写（正则、改查询参数）用 `rewrite`，见 [路径改写与重定向](../05-middleware/path-and-redirect.md)。

---

## 4. 路径不区分大小写

用户或旧客户端会请求 `/GoApi`、`/GOAPI` 这类大小写不一致的路径。在路径前加 `~` 即可：

<!-- case: ignore-case -->
```yaml
site: api.example.com
~/goapi:
  proxy: localhost:8080
  strip_prefix: true
```

```check
GET http://api.example.com/goapi/orders       => 8080 /orders
GET http://api.example.com/GoApi/orders       => 8080 /orders
# 剩余部分保持原样，大小写不会被改动
GET http://api.example.com/GOAPI/Orders       => 8080 /Orders
GET http://api.example.com/goapix             => 404
```

- 不加 `~` 的 `/goapi` 区分大小写。同一个路径不能同时写 `/goapi` 和 `~/goapi`。
- `~` 不是正则；只保证 ASCII 字母不区分大小写。

---

## 5. 跳转

整站换域名（例如 `www` 跳到主域名），保留原路径：

<!-- case: redirect-domain -->
```yaml
site: www.example.com
redirect:
  location: https://example.com{uri}
  status: 301
```

```check
GET http://www.example.com/blog/post-1?ref=x  => 301; Location: https://example.com/blog/post-1?ref=x
```

单个旧地址跳到新地址，其余照常服务：

<!-- case: redirect-path -->
```yaml
site: example.com
/old-docs:
  redirect:
    location: https://docs.example.com/
    status: 301
file_server: ./public
```

```check
GET http://example.com/old-docs/intro         => 301; Location: https://docs.example.com/
GET http://example.com/                       => 200 "<h1>public</h1>"
```

- `redirect: https://...` 简写默认 302（临时跳转）；永久跳转写成对象并指定 `status: 301`。
- 常用变量：`{uri}` 路径加查询参数，`{path}` 只有路径，`{host}` 请求域名。

---

## 6. 精确路径和复杂条件

路径键都是前缀匹配。只想匹配某一个路径、或者要按方法 / 请求头区分时，用 `routes` 列表：

<!-- case: exact-match -->
```yaml
site: example.com
routes:
  - match: {path: /}                 # 只匹配首页本身
    redirect: /home.html
  - match: {path_prefix: /api, method: [POST, PUT, DELETE]}
    proxy: localhost:8081            # 写请求走主库服务
/api:
  proxy: localhost:8080              # 其余 /api 请求（GET 等）走只读服务
file_server: ./public
```

```check
GET    http://example.com/                    => 302; Location: /home.html
GET    http://example.com/about.html          => 200 "<h1>about</h1>"
POST   http://example.com/api/orders          => 8081 /api/orders
GET    http://example.com/api/orders          => 8080 /api/orders
```
