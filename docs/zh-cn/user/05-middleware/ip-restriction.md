# IP Restriction (IP 访问控制)

## 标签和命名中间件

按路由的 IP 白名单可以通过标签中间件配置，例如限制管理后台：

```yaml
labels:
  - "litegate.enable=true"
  - "litegate.http.routers.admin.match.hosts=example.com"
  - "litegate.http.routers.admin.match.path_prefix=/admin"
  - "litegate.http.routers.admin.middlewares=internal-only"
  - "litegate.http.middlewares.internal-only.ip_restriction.allow_ips=10.0.0.0/8,192.168.0.0/16,fd00::/8"
  - "litegate.http.services.app.loadbalancer.server.port=8080"
```

只有引用 `internal-only` 的路由受这条规则限制。命名中间件也可以在站点 YAML 的 `middlewares` 中定义：

```yaml
middlewares:
  internal-only:
    type: ip_restriction
    config:
      allow_ips: "10.0.0.0/8,192.168.0.0/16,fd00::/8"
      deny_ips: "10.1.0.0/16"
```

命名中间件的 `config.allow_ips` 和 `config.deny_ips` 使用逗号分隔的字符串；下文的站点或路由内联配置仍使用 YAML 列表。至少设置一项；空项、无效 IP/CIDR 和未知字段会在加载时被拒绝。IPv4、IPv6 和 CIDR 均支持，deny 优先于 allow。

规则使用网关入口已解析的客户端 IP，不自行信任 `X-Forwarded-For`。它与全局、站点和路由内联规则共同生效，不能放宽已有规则。未通过检查的请求返回 `403 Forbidden`，检查在认证和后端处理之前执行。

---

`ip_restriction` 在边缘按来源 IP 过滤请求,可以建白名单(`allow_ips`)或黑名单(`deny_ips`),支持精确 IP 和 CIDR 网段。

它配置在 **Site 级**(文件顶部,作用于整个域名)或 **Route 级**(作为 `match` / `action` 的同级字段,作用于单条路由)。

---

## 1. 字段

| 字段 | 类型 | 作用 |
| --- | --- | --- |
| `allow_ips` | 列表 | 白名单。设置后只放行这些 IP/网段,其余一律 `403 Forbidden`。 |
| `deny_ips` | 列表 | 黑名单。命中的 IP/网段返回 `403`,其余正常放行。 |

两者都支持精确 IP 和 CIDR(如 `192.168.1.0/24`)。同时设置时,先判 `deny_ips`。

---

## 2. 配置示例

### Route 级白名单(限制后台面板)

```yaml
site: example.com
routes:
  - name: admin-panel
    match:
      path_prefix: /admin
    ip_restriction:
      allow_ips:
        - 127.0.0.1
        - 192.168.1.0/24
    proxy:
      - "localhost:8080"
```

### Site 级黑名单(对整个域名封禁恶意来源)

```yaml
site: service.example.com
ip_restriction:
  deny_ips:
    - 1.2.3.4
    - 5.6.7.0/24
routes:
  - name: app
    match:
      path_prefix: /
    proxy:
      - "localhost:8080"
```

---

## 3. 代理后的真实客户端 IP

当 LiteGate 跑在反向代理、负载均衡或 CDN(Nginx、Traefik、AWS ALB……)之后时,要在 `config.yaml` 里声明前置代理的网段,否则过滤器看到的是代理 IP 而不是真实客户端 IP:

```yaml
real_ip:
  trusted_proxies:
    - 10.0.0.0/8
```

---

## 4. 常见问题

- **请求被 403 拒绝**:这是防火墙的预期行为。想返回自定义页面,可配合 `respond` action。
- **开了白名单后把自己挡在外面**:确认你当前的公网 IP 已经在 `allow_ips` 里。
