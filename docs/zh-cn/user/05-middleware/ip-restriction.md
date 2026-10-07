# IP Restriction (IP 访问控制)

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
routes:
  - name: admin-panel
    match:
      path_prefix: /admin
    ip_restriction:
      allow_ips:
        - 127.0.0.1
        - 192.168.1.0/24
    action:
      type: proxy
      upstream:
        - "localhost:8080"
```

### Site 级黑名单(对整个域名封禁恶意来源)

```yaml
domain: service.example.com
ip_restriction:
  deny_ips:
    - 1.2.3.4
    - 5.6.7.0/24
routes:
  - name: app
    match:
      path_prefix: /
    action:
      type: proxy
      upstream:
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
