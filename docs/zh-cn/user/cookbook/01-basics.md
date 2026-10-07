# 入门：一个站点跑起来

每个案例都是一份完整的站点文件，放进 `sites/` 目录（例如 `sites/app.yaml`）即可热加载。
「请求效果」一栏写的是：发出这个请求，LiteGate 会怎么处理。

> 读法约定：`=> 8080 /orders` 表示请求被转发到 `localhost:8080`，后端收到的路径是 `/orders`；
> `=> 404` 表示网关直接返回 404。这些案例都由自动化测试逐条执行，复制即可用。

---

## 1. 反向代理一个后端

最常见的场景：域名进来，全部转给本机 8080。

<!-- case: reverse-proxy -->
```yaml
site: api.example.com
proxy: localhost:8080
```

请求效果：

```check
GET http://api.example.com/v1/users       => 8080 /v1/users
GET http://api.example.com/?page=2        => 8080 /?page=2
# 不是这个域名的请求不会进入本站点
GET http://other.example.com/             => 404
```

- 路径和查询参数原样转给后端。
- `proxy` 后面也可以是 `192.168.1.20:8080`、`http://backend:8080`。

---

## 2. 多个后端负载均衡 + 健康检查

<!-- case: load-balance -->
```yaml
site: api.example.com
proxy:
  to: [localhost:8080, localhost:8081]
  lb: least_conn        # 默认 round_robin；还有 ip_hash、p2c、cookie 等
  health: /health       # 定期探测，失败的节点自动摘除
  timeout: 5s
  retry: 2              # 连接失败时换一个节点重试
```

```check
GET http://api.example.com/orders         => 8080|8081 /orders
```

- 只是多个地址、不需要其他参数时，可以简写为 `proxy: localhost:8080, localhost:8081`。
- 多个站点要共用同一组后端时，见 [命名 Service](../03-configuration/services.md)。

---

## 3. 静态网站

<!-- case: static-site -->
```yaml
site: www.example.com
file_server: ./public
```

```check
GET http://www.example.com/               => 200 "<h1>public</h1>"
GET http://www.example.com/about.html     => 200 "<h1>about</h1>"
GET http://www.example.com/missing.html   => 404
```

- `file_server` 和 `serve` 是同一个东西，选你顺手的写。
- 需要指定首页文件、缓存头时，写成对象：`file_server: {root: ./public, index: home.html, cache_control: "max-age=3600"}`。

---

## 4. 只按端口提供服务（不关心域名）

内网工具、测试环境常常只有 IP + 端口，没有域名。

<!-- case: port-only -->
```yaml
site: :9090
proxy: localhost:8080
```

```check
GET http://192.168.1.10:9090/dashboard    => 8080 /dashboard
GET http://anything.local:9090/           => 8080 /
```

- `:9090`、`"*:9090"`、`0.0.0.0:9090` 写法等价：在 9090 端口接收任意 Host。
- 以 `*` 开头时 YAML 必须加引号：`site: "*:9090"`。
- 写了 `site: :9090` 就不要再写 `port:`，会报错。

---

## 5. 开启 HTTPS

<!-- case: https -->
```yaml
site: www.example.com
https: true
file_server: ./public
```

```check
GET http://www.example.com/about.html     => 308; Location: https://www.example.com/about.html
```

- `https: true` 会把 HTTP 请求永久跳转到 HTTPS；证书由全局自动证书负责申请，见 [Auto-Cert](../06-certificates/auto-cert.md)。
- **v2 写法默认 `https: false`**，和 Caddy 不同：即使写 `site: example.com:443` 也不会自动开启，需要显式写 `https: true`。

---

## 6. 直接返回内容（健康检查、维护页）

<!-- case: respond -->
```yaml
site: status.example.com
respond: ok
```

```check
GET http://status.example.com/ping        => 200 "ok"
```

> `/healthz`、`/readyz`、`/metrics`、`/_litegate` 等是网关自身保留的路径，站点里不要用它们做路由——例如 `/healthz` 会直接由网关回答。

需要自定义状态码和内容类型时写成对象，例如临时维护：

<!-- case: maintenance -->
```yaml
site: shop.example.com
respond:
  status: 503
  content_type: text/html; charset=utf-8
  body: <h1>系统维护中，预计 30 分钟后恢复</h1>
```

```check
GET http://shop.example.com/cart          => 503 "系统维护中"
```
