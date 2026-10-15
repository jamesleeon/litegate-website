# 基础：静态站点与 API

站点文件放在配置的 sites 目录。默认 serve 提供静态页面，/api 使用 proxy。路径路由沿用原路径，不会自动去掉 /api；后端需要去前缀时显式配置 rewrite。

上线前运行配置校验，检查静态 root、权限、后端可达性与 Host。HTTPS 还需有效证书与全局入口配置。

<!-- case: static-and-api -->
```yaml
site: app.example.com
serve: ./public
/api:
  proxy: 127.0.0.1:8080
```

```check
GET http://app.example.com/ => 200 "public"
GET http://app.example.com/api/orders => 8080 /api/orders
```

## 相关文档与代码

- [Serve](../04-actions/serve.md)
- [Proxy](../04-actions/proxy.md)
