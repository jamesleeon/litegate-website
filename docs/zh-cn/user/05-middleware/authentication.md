# 认证与 IDS 治理

按责任选择三条配置路径：auth 提供本地 basic/sso/jwt；remote_auth 处理 OIDC/OAuth2 登录与会话；ids 使用业务 Provider 验证、直接响应、投影头或动态隔离，不限于 proxy。

本地 SSO 提供登录页、签名 Cookie、登录返回和退出，无需额外认证服务。使用独立的至少 32 字节随机 secret 与 bcrypt users；基本登录不需 Redis，失败次数/IP 锁定需要 Redis。Cookie 默认 24 小时，可用 session_ttl、cookie_secure 与 template 配置。退出清除浏览器 Cookie，不提供逐会话服务端撤销，不自动共享子域 Cookie 或注入用户名；需要组策略/MFA 时使用外部身份服务。

JWT 的 secret（HS256/384/512）与 jwks_url（RS/ES）必须二选一，拒绝 alg:none。密钥使用 env://、file:// 或支持的引用；可校验 issuer/audience。token_from 按顺序取第一个非空值，选中但无效即拒绝，不支持 Query Token。浏览器 SSE 可读 HttpOnly Cookie。

subject_claim/tenant_claim 映射可信通知身份，缺少映射 claim 返回 401；tenant_claim 要求 subject_claim，数字 ID 保留精度。不映射时只验签。JWT exp 到期关闭长连接；无 exp 时需应用明确自己的生命周期。命名 jwt_auth 可共享策略。

认证不能把用户传入的租户头变成授权。IDS Header 使用显式白名单；业务登录/token/会话由 Provider 实现。OIDC 依赖独立配置与 Redis；详见对应指南。

```bash
litegate -hash 'replace-with-your-password'
litegate -secret
```

```yaml
site: app.example.com
https: true
auth:
  type: sso
  secret: REPLACE_WITH_A_RANDOM_SECRET_AT_LEAST_32_BYTES
  users:
    demo: REPLACE_WITH_BCRYPT_PASSWORD_HASH
  session_ttl: 86400
  cookie_secure: true
proxy: 127.0.0.1:8080
```

```yaml
site: app.example.com
/api:
  auth:
    type: jwt
    secret: env://APP_JWT_SECRET
    token_from: [header, 'cookie:lg_token']
    subject_claim: user_id
    tenant_claim: tenant_id
  proxy: 127.0.0.1:8080
```

## 相关文档与代码

- [Basic](basic-auth.md)
- [Forward Auth](forward-auth.md)
- [OIDC](oidc.md)
- [authentik OIDC 配置样例](authentik.md)
- [Remote Auth](remote-auth.md)
- [IDS](ids-governance.md)
- [Notify/JWT](../09-advanced/notify-jwt-integration.md)
