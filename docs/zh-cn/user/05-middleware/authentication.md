# Authentication (网关身份认证与治理概述)

LiteGate 提供了两套不同的身份认证与流量治理组件，它们分别解决不同的业务问题：

- **`action.auth`** (本地静态认证中间件)
  - 面向静态 YAML 路由。
  - 适合 `basic`、`sso`、`jwt` 等本地单站点简单认证场景。
- **`action.remote_auth`** (OIDC 认证中间件)
  - 面向标准 OIDC (OpenID Connect) / OAuth2 单点登录回跳与会话管理场景。
- **`action.ids`** (数据代理前置 IDS 治理)
  - 面向动态服务发现、多租户 SaaS 架构和 IDS（身份驱动选路治理）平台的高速深度协同。
  - 由统一 Provider 自定义验证、缓存、直接响应、Header 投影和可选的物理隔离选路。
  - 执行在 Proxy 数据代理阶段的前置接缝（pre-proxy seam），而非传统 HTTP 路由中间件。

---

## 1. 核心分类说明

### 1.1 静态认证：`auth`
这是传统的本地站点/YAML 路由静态认证，走 `Action.Auth`。支持 `basic` / `sso` / `jwt`，适合不需要依赖外部统一认证平台的简单场景。

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

### 1.2 OIDC 认证：`remote_auth`
托管 OAuth2 标准协议的回跳与会话维持，走 `Action.RemoteAuth`。由 `OIDCHandler` 中间件执行登录重定向与会话生命周期维护。详见 [OIDC 指南](./oidc.md)。

### 1.3 身份驱动选路与治理：`ids`
这是 LiteGate 核心数据流的前置接缝，走 `Action.IDS`。不同路径选择不同 Provider；内核只理解 Forward、Respond、错误和可选 Selector/Meta，不理解具体业务动作。详见 [IDS 治理指南](./ids-governance.md)。

---

## 2. 延伸阅读

- [Basic Auth 基本认证中间件](./basic-auth.md)
- [IDS 治理指南](./ids-governance.md)
- [OIDC 指南](./oidc.md)
- [IDS Provider 插件开发与配置](../../ids-provider-plugin-guide.md)
