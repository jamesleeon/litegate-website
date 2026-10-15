# HTTP Basic Auth

命名 `basic_auth` 中间件在 Authentication 阶段保护路由。先用 `litegate -hash` 生成 bcrypt 哈希；users 为逗号分隔的 `用户名:bcrypt_hash`。明文、MD5 和 SHA 密码会被加载校验拒绝。示例哈希必须替换成生成的完整哈希。

凭证缺失或错误返回 401 和 WWW-Authenticate。realm 默认为 `LiteGate Restricted`，不能含双引号或控制字符；`remove_header: true` 在通过认证后移除 Authorization；`enabled: false` 禁用定义。Basic 凭证需要 HTTPS 保护。多个路由可引用同一定义；内联 `auth.type: basic` 是另一个配置入口，勿同时叠加相同认证。

```bash
litegate -hash 'replace-with-your-password'
```

```yaml
site: internal.example.com
middlewares:
  admin-gate:
    type: basic_auth
    config:
      users: 'admin:$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy'
      realm: Internal Tools
      remove_header: true
routes:
  - match: {path_prefix: /}
    use: [admin-gate]
    proxy: ['127.0.0.1:8080']
```

## 相关文档与代码

- [Authentication](authentication.md)
- [Implementation](../../../../internal/middleware/basic_auth.go)
