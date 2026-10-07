# OIDC / OAuth2 认证配置指南

LiteGate 通过路由上的 `remote_auth.provider` 提供 OIDC / OAuth2 认证能力（`ids` 是独立的 IDS Provider 插件入口，不用于 OIDC 登录）。它支持标准 OIDC Provider，也支持标准 OAuth2 Provider，并通过 Redis 保存登录状态与会话。

---

## 1. 核心设计

LiteGate 的认证链路采用 `Stateless Router + Stateful Session` 设计：

- Redis 是强依赖。
  登录发起阶段的 `state`、PKCE verifier、nonce，以及登录完成后的 session 都保存在 Redis。
- 网关本身不保存本地服务端会话。
  浏览器只持有一个 session cookie，真实会话数据在 Redis。
- 支持默认回调路径和自定义回调路径。
  默认回调路径是 `/_litegate/oauth/callback`；也可以通过 provider 级或 route 级 `callback_path` 自定义。

---

## 2. 全局配置

### 2.1 Redis

OIDC / OAuth2 登录闭环必须启用 Redis：

```yaml
redis:
  enabled: true
  address: "127.0.0.1:6379"
  password: ""
  db: 0
```

### 2.2 定义 Auth Providers

在 `config.yaml` 中定义一个或多个认证提供商：

```yaml
auth_providers:
  google-oidc:
    enabled: true
    type: "oidc"
    issuer: "https://accounts.google.com"
    client_id: "YOUR_CLIENT_ID"
    client_secret: "YOUR_CLIENT_SECRET"
    scopes: ["openid", "profile", "email"]
    # 可选：provider 级自定义回调路径
    # callback_path: "/_auth/google/callback"
    # 可选：时钟容忍
    # clock_skew: "5m"
    # 可选：限制签名算法
    # allowed_signing_algs: ["RS256"]
    # 可选：登录成功/失败通知
    # notify_url: "http://your-app/auth-webhook"
    # 可选：追加或覆盖授权请求参数；值为空表示去掉默认值
    # auth_params:
    #   prompt: login

  github-oauth:
    enabled: true
    type: "oauth2"
    auth_url: "https://github.com/login/oauth/authorize"
    token_url: "https://github.com/login/oauth/access_token"
    client_id: "YOUR_CLIENT_ID"
    client_secret: "YOUR_CLIENT_SECRET"
    scopes: ["user", "repo"]
    # callback_path: "/_auth/github/callback"
```

说明：

- `type: oidc` 适用于支持 OIDC Discovery 和 `id_token` 校验的 Provider。
- `type: oauth2` 适用于标准 OAuth2 Provider，例如 GitHub。
- 默认回调路径是 `/_litegate/oauth/callback`。
- `client_secret` 支持 `env:XXX` 形式的环境变量展开。
- 授权请求默认不带 `prompt`、`access_type`。Google（issuer 或 auth_url 为 `accounts.google.com`）自动加上 `access_type=offline` 和 `prompt=consent`，否则拿不到 refresh token。其他 IdP 需要特定参数时用 `auth_params`；`state`、`nonce`、`scope`、`redirect_uri` 等由登录流程生成的参数不能覆盖。
- Keycloak 默认就会发 refresh token；Authentik、Dex、Azure AD 等通常需要在 `scopes` 里加 `offline_access`。

### 2.3 OIDC 安全配置

```yaml
oidc_security:
  cookie_secret: "32_byte_secret_for_aes_encryption"
  cookie_same_site: "lax"   # lax / strict / none
  max_concurrent_sessions: 5

  token_allowed_ips: ["127.0.0.1", "192.168.1.0/24"]
  me_allowed_ips: ["127.0.0.1"]

  # /_litegate/oauth/token 默认关闭
  # token_endpoint_enabled: true
  # 可选：直接用 session ID 调 token 接口时，读取后删除该 session
  # token_one_shot: true
  # 允许 redirect_back 跳转的外部主机
  # allowed_redirect_hosts: ["app.example.com"]
  # 同一 IP 15 分钟内登录回调失败次数上限，默认 20，负数关闭
  # login_failure_limit: 20
```

说明：

- `cookie_secret` 建议至少 32 字节；设置后 session cookie 会加密。
- `max_concurrent_sessions` 会限制同一用户的并发登录数，超出后会淘汰最旧 session。
- `token_allowed_ips` 控制 `/_litegate/oauth/token`。
- `me_allowed_ips` 控制 `/_litegate/oauth/me`。
- `login_failure_limit`：同一 IP 登录回调失败（IdP 返回错误、换 token 失败等）达到上限后，15 分钟内不再发起登录，返回 403。state 过期、不是本浏览器发起的回调等情况不计数。NAT 后用户较多时可调大或设为负数关闭。

---

## 3. 站点 / 路由配置

在具体路由上启用认证：

```yaml
domain: "app.example.com"
routes:
  - name: "protected-api"
    match:
      path_prefix: "/api"
    action:
      type: "proxy"
      service_name: "my-backend"
      remote_auth:
        enabled: true
        provider: "google-oidc"
        enforce: true
        callback_path: "/_auth/cb"
        inject_claims:
          "X-User-Id": "sub"
          "X-User-Email": "email"
          "X-User-Name": "name"
```

说明：

- `remote_auth.provider` 引用全局 `auth_providers` 里的名称。OIDC 登录属于认证中间件配置，不应写在用于 IDS 流量治理的 `ids` 节点下。
- `enforce: true` 表示未登录时自动跳转到 Provider 登录页。
- `callback_path` 可以在 route 级覆盖 provider 默认回调路径。
- `inject_claims` 会把认证后的 claims 注入到转发给后端的请求头中。
- `enforce: true` 时，浏览器请求（`Accept` 含 `text/html`）跳转登录，API 请求返回 `401`。
- provider 不可用（未配置、IdP discovery 失败）时，`enforce: true` 的路由返回 `503`，不会放行；只有显式 `fail_policy: allow` 才放行（匿名）。provider 在之后初始化或重载成功后立即生效。
- OIDC provider 总会请求 `openid` scope，`scopes` 中可省略。
- 会话以 cookie 为准；`Authorization: Bearer` 只识别网关 session ID（UUID），后端自己的 Bearer Token（如 JWT）原样透传，不影响登录态。
- 登录回调要求发起登录的同一浏览器中的 state cookie，防止登录 CSRF。
- access token 在剩余不足其有效期 1/4（最多 5 分钟）时自动刷新；IdP 未返回 `expires_in` 时，会话有效期以 session 记录（7 天）为准。

---

## 4. 回调路径规则

LiteGate 当前支持两类回调入口：

1. 默认系统回调路径：`/_litegate/oauth/callback`
2. 自定义回调路径：来自 provider 级或 route 级 `callback_path`

当前实现下，自定义回调路径已经支持全局识别，不再要求你手工为 callback 单独写一条业务 route。

但要注意两个边界：

- 自定义回调路径应位于当前站点域名下。
- 不要与 LiteGate 的高优先级保留路径冲突，例如：
  - `/.well-known/acme-challenge/*`
  - `/health`
  - `/_litegate/*`

推荐做法：

- 默认优先使用 `/_litegate/oauth/callback`
- 如果业务上需要更自然的 URL，再使用 `/_auth/...` 之类的自定义回调路径

---

## 5. 保留接口

### 5.1 查看当前会话

访问：

```text
/_litegate/oauth/me
```

返回当前 session 的 JSON 信息，包含：

- `id`
- `user_id`
- `provider`
- `claims`
- `expiry`
- `state`（登录时透传的业务 state，可能为空）

该接口受 `oidc_security.me_allowed_ips` 控制。

### 5.2 获取 reference token 对应的 session

访问：

```text
/_litegate/oauth/token?id=<session-id>
```

或使用：

```text
Authorization: Bearer <session-id>
```

该接口受 `oidc_security.token_allowed_ips` 控制。

需要先开启 `oidc_security.token_endpoint_enabled: true`。

`id` 可以是 session ID，也可以是 `redirect_back` 拿到的一次性 ticket（见下文）。ticket 首次兑换后立即失效，对应 session 保留，浏览器登录态不受影响；`token_one_shot: true` 只对直接传 session ID 的调用生效，读取后删除该 session。

### 5.2.1 redirect_back：把登录结果交给其他系统

登录时带上 `?redirect_back=<url>`（或路由配置 `default_redirect_back`），登录完成后浏览器跳到该地址并附带 `token=<ticket>`（以及原样透传的 `state`）。外部地址需要在 `allowed_redirect_hosts` 中，且必须是 https。

`token` 是 2 分钟有效、只能用一次的 ticket，不是 session ID：URL 会进入浏览器历史、访问日志和 Referer，所以不直接暴露 7 天有效的会话凭据。接收方应在服务端调用 `/_litegate/oauth/token?id=<ticket>` 兑换用户信息。

> 早期版本这里传的是 session ID。如果接收方曾把 `token` 当作 `Authorization: Bearer` 使用，需要改为先兑换：兑换结果的 `id` 字段就是 session ID。

### 5.3 手动刷新 token

访问：

```text
POST /_litegate/oauth/refresh?id=<session-id>
```

前提：

- session 仍存在
- provider 支持 refresh
- session 中存在 `refresh_token`

### 5.4 登出

访问：

```text
/_litegate/oauth/logout
```

当前行为是：

- 删除 Redis 中的 session 记录并清除本地 cookie
- 如果 provider 声明了 `end_session_endpoint`，跳转到 IdP 登出页，带上 `id_token_hint`、`client_id` 和 `post_logout_redirect_uri`（站点根地址 `/`）
- 如果 provider 不支持，则跳转回 `/`

注意：`post_logout_redirect_uri` 需要在 IdP 的客户端配置里登记（Keycloak 是 Valid post logout redirect URIs），否则 IdP 会拒绝跳回。

---

## 6. 实际登录流程

一次典型的 OIDC/OAuth2 登录闭环如下：

1. 用户访问受保护路由。
2. LiteGate 发现没有有效 session。
3. LiteGate 生成 `state`、PKCE verifier、nonce，并写入 Redis。
4. 浏览器被重定向到认证提供商。
5. Provider 登录完成后回调 LiteGate。
6. LiteGate 校验 `state`，并用相同的 redirect URI 交换 token。
7. 如果是 OIDC Provider，LiteGate 会校验 `id_token` 和 nonce。
8. LiteGate 将 session 写入 Redis，并设置本地 cookie。
9. 后续请求带上 cookie 后，LiteGate 从 Redis 恢复 session，并把 claims 注入 Header。

---

## 7. 常见问题

### 为什么回调时报 `State mismatch` 或 `Session expired or invalid state`？

常见原因：

- Redis 不可用
- Redis 中的 state 已过期
- 浏览器回调 URL 与登录发起时记录的 callback path 不一致
- 认证提供商后台配置的 redirect URI 与 LiteGate 实际使用的不一致

### 自定义 callback_path 需要手工写路由吗？

通常不需要。

LiteGate 现在会基于回调请求中的 `state` 去 Redis 识别原始 callback path，并自动接管该请求。

但仍建议避开保留路径，并保证 callback path 落在当前站点域名下。

### 后端如何获取用户信息？

通过 `inject_claims` 配置把 claims 注入请求头，后端直接读取 Header 即可。

例如：

```yaml
inject_claims:
  "X-User-Id": "sub"
  "X-User-Email": "email"
```

注意两种写法方向相反：路由里的 `inject_claims` 映射是 `请求头: claim`；命名中间件 `type: remote_auth` 的 `config.inject_claims` 是逗号分隔的 `claim:请求头` 字符串（如 `sub:X-User-Id,email:X-User-Email`）。

### OAuth2 Provider 和 OIDC Provider 有什么区别？

- OIDC Provider 会返回 `id_token`，LiteGate 会做本地校验。
- OAuth2 Provider 没有标准 `id_token` 校验流程，LiteGate 主要依赖 code exchange 的结果。

---

## 8. 建议

- 生产环境务必启用 Redis。
- 生产环境务必配置 `cookie_secret`。
- 优先使用 HTTPS。
- 优先使用默认回调路径，除非业务明确需要自定义 callback path。
- 对 `/_litegate/oauth/token` 和 `/_litegate/oauth/me` 配置严格 IP 白名单。
