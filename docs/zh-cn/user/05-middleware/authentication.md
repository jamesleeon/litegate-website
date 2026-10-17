# Authentication (网关身份认证与治理概述)

LiteGate 按责任提供三条认证与治理配置路径：

- **`auth`**（本地认证）
  - 面向静态 YAML 路由。
  - 适合 `basic`、`sso`、`jwt` 等本地单站点简单认证场景。
- **`remote_auth`**（OIDC 认证）
  - 面向标准 OIDC (OpenID Connect) / OAuth2 单点登录回跳与会话管理场景。
- **`ids`**（业务身份决策）
  - 面向动态服务发现、多租户 SaaS 架构和 IDS（身份驱动选路治理）平台的高速深度协同。
  - 由统一 Provider 自定义验证、缓存、直接响应、Header 投影和可选的物理隔离选路。
  - 在路由匹配后、Action 执行前运行，可保护所有 Action；动态实例选路（Selector/Meta）只对 proxy 有意义。

---

## 1. 核心分类说明

### 1.1 静态认证：`auth`
这是本地站点/路由认证，写在站点或路由的 `auth` 字段。支持 `basic` / `sso` / `jwt`，适合不需要依赖外部统一认证平台的简单场景。

#### 为网站增加内置登录

`auth.type: sso` 可以直接保护代理或静态网站，无需额外认证服务。下面配置保护整个站点，也覆盖 `/_auth/login` 与 `/_auth/logout`，确保登录与退出请求能进入认证处理：

```yaml
site: app.example.com
https: true
auth:
  type: sso
  secret: "REPLACE_WITH_A_RANDOM_SECRET_AT_LEAST_32_BYTES"
  users:
    demo: "REPLACE_WITH_BCRYPT_PASSWORD_HASH"
  session_ttl: 86400
  cookie_secure: true
proxy: 127.0.0.1:8080
```

部署前生成两个独立的值，并配置 HTTPS 证书：

```bash
# 输出 bcrypt 密码哈希，填入 users.demo
litegate -hash 'your-password'

# 输出 32 个随机字节的十六进制表示（64 个字符），填入 secret
litegate -secret
```

`-hash` 用于用户密码哈希；`secret` 用于签名会话 Cookie，应使用独立的随机密钥，不要用用户密码或其 bcrypt 哈希代替。用户首次访问会跳转登录页，登录成功后返回原页面；以后每次请求只在本地检查会话 Cookie 的签名和有效期。默认会话有效期为 24 小时，支持通过 `template` 自定义登录页。

基本登录流程不依赖 Redis；现有按 IP 统计失败次数与临时锁定功能需要 Redis。当前会话为无状态签名 Cookie，退出会清除当前浏览器 Cookie，但没有服务端逐会话撤销机制。Cookie 为当前主机使用，不会自动在不同子域之间共享；认证通过后也不会自动向后端注入用户名。

需要集中维护用户、用户组权限、双因素认证或向后端传递身份时，可使用 [Authelia / Forward Auth](./forward-auth.md)；需要标准身份提供方登录时，使用下文的 OIDC。

#### 用 JWT 保护接口和订阅

`auth.type: jwt` 由网关直接校验业务系统签发的 JWT，不需要再回调业务后端。两种验签方式二选一：

| 字段 | 适用 | 说明 |
|---|---|---|
| `secret` | 业务系统用 HS256/384/512 共享密钥签发 | 写成引用：`env://APP_JWT_SECRET`、`file:///etc/litegate/jwt.key` 或 `${APP_JWT_SECRET}`，不要把密钥明文写进站点文件 |
| `jwks_url` | 身份提供方用 RS/ES 私钥签发并公开 JWKS | 例如 `https://idp.example.com/.well-known/jwks.json` |

两种方式各自锁定算法族：配置 `secret` 时只接受 HS 系列，配置 `jwks_url` 时只接受 RS/ES 系列，避免算法混淆攻击；`alg: none` 一律拒绝。

```yaml
site: app.example.com
/api:
  auth:
    type: jwt
    secret: env://APP_JWT_SECRET
    token_from: [header, 'cookie:lg_token'] # 先找 Authorization: Bearer，再找 Cookie
    subject_claim: user_id                  # 用户标识
    tenant_claim: tenant_id                 # 租户标识（可选）
  proxy: 127.0.0.1:8080
```

- `token_from`：令牌来源，按顺序取第一个非空值；取到的令牌无效时直接拒绝，不会继续尝试后面的来源。`header` 表示 `Authorization: Bearer`（缺省），`cookie:<名称>` 表示读取 Cookie。浏览器的 `EventSource` 无法设置请求头，订阅推送时通常读取 HttpOnly Cookie。出于日志泄露的考虑，不支持从 URL 查询参数取令牌。
- `subject_claim` / `tenant_claim`：把令牌声明为网关的**已验证身份**。`tenant_claim` 必须与 `subject_claim` 同时配置。配置后，令牌里缺少对应 claim 会直接返回 401；验证通过后，事件通知用它区分订阅者（`offline: auth.subscriber`）和租户（`{auth.tenant}`）。不配置时只做验签。
- `issuer`、`audience`：配置后校验 `iss`、`aud`。
- 只要验证通过，长连接（例如事件推送）都会在令牌 `exp` 到期时断开，与是否配置身份映射无关；没有 `exp` 的令牌不设边界，连接只受各自的最长时长限制，签发方应始终写入 `exp`。
- 数字 claim 按原样保留，18 位雪花 ID 不会丢精度。
- 客户端自行携带的 `X-Lito-*`、`X-Tenant-ID` 等身份头会在入口处被清除，伪造不了。

多个路由共用一份配置时，可以使用命名中间件 `type: jwt_auth`，字段相同（`token_from`、`audience` 用逗号分隔）。

### 1.2 OIDC 认证：`remote_auth`
处理 OIDC/OAuth2 的登录重定向、回调与会话维持，会话存储依赖 Redis。详见 [OIDC 指南](./oidc.md)，authentik 接入样例见 [authentik](./authentik.md)。

### 1.3 身份驱动选路与治理：`ids`
不同路径选择不同 Provider；内核只理解 Forward、Respond、错误和可选 Selector/Meta，不理解具体业务动作。业务登录、token 与会话由 Provider 实现；投影到后端的 Header 使用显式白名单，认证不会把客户端传入的租户头当作授权。详见 [IDS 治理指南](./ids-governance.md)。

---

## 2. 延伸阅读

- [Basic Auth 基本认证中间件](./basic-auth.md)
- [IDS 治理指南](./ids-governance.md)
- [OIDC 指南](./oidc.md)
- [IDS Provider 插件开发与配置](../../ids-provider-plugin-guide.md)
- [Forward Auth / Authelia](./forward-auth.md)
- [Remote Auth](./remote-auth.md)
- [事件通知与 JWT](../09-advanced/notify-jwt-integration.md)
