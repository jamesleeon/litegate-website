# Forward Auth 外部鉴权

默认发行版包含纯 Go Forward Auth 插件。它在 Authentication 阶段对每个受保护请求发起不带业务请求体的 GET 检查，早于业务动作和代理缓存。2xx 放行；401/403 和支持的登录跳转返回客户端；鉴权服务异常返回 503。

完整 URL 简写不猜测鉴权路径。对象形式可设置 address、uri、copy_headers；默认复制 Remote-User、Remote-Groups、Remote-Name、Remote-Email。鉴权服务名称必须在网关所在网络可解析。当前不支持多个鉴权 upstream 或身份头重命名。

登录门户单独代理到身份服务，门户和应用都需要 HTTPS、有效证书以及身份服务的 Cookie/访问策略。LiteGate 无需为此另配 OIDC 或 Redis。仅需本地用户名密码登录时，也可使用内置 `auth.type: sso`；它不提供用户组、MFA 或跨域共享 Cookie。

```yaml
site: auth.example.com
https: true
proxy: authelia:9091
---
site: app.example.com
https: true
forward_auth: http://authelia:9091/api/authz/forward-auth
proxy: app:8080
```

## 相关文档与代码

- [Authentication](authentication.md)
- [Plugin](../../../../pkg/plugins/forwardauth)
