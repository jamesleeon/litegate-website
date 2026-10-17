# 治理：跨域、响应头、限流、访问控制

这些能力都直接写在路由（或站点）下面，和 `proxy` / `file_server` 平级，不需要先定义中间件。

---

## 1. 给 API 开跨域（CORS）

前端在 `https://web.example.com`，接口在 `api.example.com`：

<!-- case: cors -->
```yaml
site: api.example.com
/api:
  proxy: localhost:8080
  cors:
    allowed_origins: [https://web.example.com]
    allowed_methods: [GET, POST, PUT, DELETE, OPTIONS]
    allowed_headers: [Content-Type, Authorization]
    allow_credentials: true
    max_age: 86400          # 预检结果缓存 1 天，减少 OPTIONS 请求
```

```check
# 浏览器的预检请求由网关直接应答，不会打到后端
OPTIONS http://api.example.com/api/orders Origin: https://web.example.com Access-Control-Request-Method: POST => 204; Access-Control-Allow-Origin: https://web.example.com; Access-Control-Allow-Credentials: true
GET     http://api.example.com/api/orders Origin: https://web.example.com => 8080 /api/orders; Access-Control-Allow-Origin: https://web.example.com
# 不在白名单里的来源拿不到跨域许可
GET     http://api.example.com/api/orders Origin: https://evil.example   => 8080 /api/orders; Access-Control-Allow-Origin: (none)
```

- 公开接口、不带 Cookie 时可以写 `allowed_origins: ["*"]`；`*` 不能和 `allow_credentials: true` 同时使用。

---

## 2. 安全响应头 + 给后端传请求头

<!-- case: headers -->
```yaml
site: app.example.com
response_headers:                 # 站点级：所有响应都带上
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  Strict-Transport-Security: max-age=31536000
/api:
  proxy: localhost:8080
  request_headers:                # 只发给后端
    X-Gateway: litegate
    X-Client-IP: "{ip}"
  response_headers:
    Cache-Control: no-store       # 路由级：和站点级合并，同名时路由级优先
file_server: ./public
```

```check
GET http://app.example.com/              => 200 "<h1>public</h1>"; X-Frame-Options: DENY; Cache-Control: (none)
GET http://app.example.com/api/me from 198.51.100.7 => 8080 /api/me; Echo-X-Gateway: litegate; Echo-X-Client-Ip: 198.51.100.7; X-Frame-Options: DENY; Cache-Control: no-store
```

- `request_headers` 只对 `proxy` 生效；写在静态文件路由上会报错。
- 常用变量：`{ip}` 客户端 IP、`{host}` 请求域名、`{header.X-Name}` 某个请求头、`{query.name}` 查询参数。

---

## 3. 限流

<!-- case: rate-limit -->
```yaml
site: api.example.com
/api/sms:
  proxy: localhost:8080
  rate_limit: 2            # 每秒 2 个请求（突发容量也是 2）
/api:
  proxy: localhost:8080    # 其他接口不限
```

```check
POST http://api.example.com/api/sms/send   => 8080 /api/sms/send
POST http://api.example.com/api/sms/send   => 8080 /api/sms/send
POST http://api.example.com/api/sms/send   => 429
GET  http://api.example.com/api/orders     => 8080 /api/orders
```

- 这里的额度是**这条路由所有客户端共享**的：一个人刷满了，其他人也会被拒。

按客户端 IP 分别计数（相当于 Nginx 的 `limit_req zone=$binary_remote_addr`）：

<!-- case: rate-limit-per-ip -->
```yaml
site: api.example.com
/api/login:
  proxy: localhost:8080
  rate_limit: {rate: 1, key: ip}    # 每个 IP 每秒 1 次
```

```check
POST http://api.example.com/api/login from 198.51.100.1  => 8080 /api/login
POST http://api.example.com/api/login from 198.51.100.1  => 429
# 另一个 IP 不受影响
POST http://api.example.com/api/login from 198.51.100.2  => 8080 /api/login
```

- 客户端 IP 按全局可信代理配置识别；网关前有 CDN / 负载均衡时要先配置可信代理，否则所有人共用代理的 IP。
- 按 IP 计数只能配合默认的 `static` 策略；`rate_limit_policy: adaptive` 是按机器负载整体调节，不能按 IP 拆分。
- 同时在线的客户端计数有上限（10 万个），超出后新客户端临时共用路由额度，防止伪造海量 IP 撑爆内存。
- 跨路由共享额度见 [Rate Limit](../05-middleware/rate-limit.md)；`limit_conn` 限制同时处理中的请求数，适合保护慢接口。

---

## 3.1 隐藏后端信息、防止伪造身份头

在头名前加 `-` 表示删除（相当于 Nginx 的 `proxy_hide_header` 和 `proxy_set_header X "";`）：

<!-- case: header-delete -->
```yaml
site: api.example.com
response_headers:
  -Server: ""             # 去掉后端暴露的软件和版本
  -X-Powered-By: ""
/api:
  proxy: localhost:8080
  request_headers:
    -X-User-Id: ""        # 客户端自己带的身份头一律丢弃，由后端鉴权后自行设置
```

```check
GET http://api.example.com/api/me X-User-Id: admin => 8080 /api/me; Echo-X-User-Id: (none); Server: (none)
```

- 删除的头值必须写空字符串；同一个头不能既删除又设置。
- 站点级删除、路由级重新设置同名头时，以路由级为准。

---

## 4. 只允许内网访问管理后台

<!-- case: ip-restriction -->
```yaml
site: app.example.com
/admin:
  proxy: localhost:8081
  ip_restriction:
    allow_ips: [10.0.0.0/8, 192.168.0.0/16]
proxy: localhost:8080
```

```check
GET http://app.example.com/admin/users from 10.1.2.3      => 8081 /admin/users
GET http://app.example.com/admin/users from 203.0.113.9   => 403
GET http://app.example.com/products    from 203.0.113.9   => 8080 /products
```

- 也可以反过来用 `deny_ips` 拉黑。写在站点级则对整站生效。
- 网关前面还有 CDN / 负载均衡时，要在全局配置里设置可信代理，否则看到的是代理的 IP。

---

## 5. 多个接口共用一套策略（snippets）

几个后端都要同样的跨域、响应头，不想每处复制一遍：

<!-- case: snippets -->
```yaml
site: api.example.com
snippets:
  public-api:
    cors:
      allowed_origins: ["*"]
      allowed_methods: [GET, POST, OPTIONS]
      allowed_headers: [Content-Type]
    response_headers:
      X-Content-Type-Options: nosniff
      X-Api-Version: "1"
/users:
  import: public-api
  proxy: localhost:8080
/orders:
  import: public-api
  response_headers:
    X-Api-Version: "2"     # 本地写的同名头覆盖片段里的
  proxy: localhost:8081
```

```check
GET http://api.example.com/users/1  Origin: https://any.example => 8080 /users/1; Access-Control-Allow-Origin: *; X-Content-Type-Options: nosniff; X-Api-Version: 1
GET http://api.example.com/orders/1 Origin: https://any.example => 8081 /orders/1; Access-Control-Allow-Origin: *; X-Api-Version: 2
```

- 片段里只能放治理类字段（cors、auth、限流、响应头、strip_prefix、use 等），**不能放 proxy / file_server 等动作和路径**。
- 除了请求头 / 响应头可以本地覆盖，其他字段（如 cors）在片段和本地重复写会直接报错，避免「以为生效其实被覆盖」。
- 一处可以导入多个片段：`import: [public-api, audit]`。
