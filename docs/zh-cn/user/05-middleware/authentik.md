# authentik OIDC 配置样例

LiteGate 可以通过内置 OIDC 接入自建 authentik，不需要专用插件或外部账号注册。用户在 authentik 登录，LiteGate 校验 ID Token，并通过请求头把身份信息传给后端。LiteGate 的登录状态和会话需要 Redis。

本例使用内网 HTTP，便于复现测试；生产部署请换成 HTTPS 域名和有效证书。OIDC 登录、身份头透传、自动刷新和完整登出已用 authentik **2026.8.3** 与当前 LiteGate 源码实测通过。

## 1. 准备地址与服务

把以下文档示例地址 `192.0.2.10` 替换为你的服务器地址。authentik 的地址必须同时能被浏览器和 LiteGate 访问。

| 服务 | 本例地址 |
| --- | --- |
| authentik | `http://192.0.2.10:19000` |
| LiteGate 应用入口 | `http://192.0.2.10:18086` |
| Redis | `127.0.0.1:16379` |
| HTTP 后端 | `127.0.0.1:18087` |

先按 [authentik Docker Compose 安装指南](https://docs.goauthentik.io/install-config/install/docker-compose/) 部署 authentik，完成本地管理员初始化，并创建一个测试用户。无需在外部网站注册。安装 Compose 的 HTTP 端口可设为 `COMPOSE_PORT_HTTP=19000`。Redis 和后端需要单独运行；上面的 `127.0.0.1` 地址以 LiteGate 所在网络环境为准，容器部署时应改为可访问的服务地址。

## 2. 在 authentik 创建应用和 Provider

创建 **OAuth2/OpenID Connect Provider**，并关联一个 Application：

| 设置 | 值 |
| --- | --- |
| Application slug | `litegate` |
| Application launch URL | `http://192.0.2.10:18086/` |
| Client type | `Confidential` |
| Client ID | `litegate-lab` |
| Client Secret | 使用 authentik 生成的值，保存供 LiteGate 使用 |
| Authorization flow | `default-provider-authorization-implicit-consent` |
| Grant types（若界面提供此项） | Authorization code、Refresh token |
| Issuer mode | 每个 Provider 使用独立 issuer，保持默认值 |
| Signing Key | 选择 RSA 证书密钥对，使签名算法为 `RS256` |
| Encryption Key | 不设置 |
| Scope mappings | `openid`、`profile`、`email`、`offline_access` 的映射 |
| Include claims in ID Token | 启用 |

登记两条 **Strict** redirect URI；2026.8 的界面中分别选择对应类型：

| 类型 | 地址 |
| --- | --- |
| Authorization | `http://192.0.2.10:18086/_litegate/oauth/callback` |
| Logout | `http://192.0.2.10:18086/` |

LiteGate 使用 Discovery 中的 JWKS 验签。authentik 未选 Signing Key 时使用 `HS256`，不适配本例；请选择 RSA Signing Key，并保持 Token 加密关闭。`offline_access` 用于获取刷新令牌，用户资料需要包含在 ID Token 中供 `inject_claims` 使用。

本例的 issuer 应为 `http://192.0.2.10:19000/application/o/litegate/`，其 Discovery 地址为：

```text
http://192.0.2.10:19000/application/o/litegate/.well-known/openid-configuration
```

检查该 JSON 的 `issuer` 与 LiteGate 配置完全相同，包括末尾 `/`。LiteGate 的 `issuer` 字段填写 issuer 本身，不填写完整 Discovery URL。

## 3. LiteGate 全局配置

保存为 `config.yaml`：

```yaml
mode: observability
entrypoints:
  web:
    address: ":18086"
auto_cert:
  enabled: false
sites_dir: ./sites

redis:
  enabled: true
  address: "127.0.0.1:16379"

auth_providers:
  authentik:
    enabled: true
    type: oidc
    issuer: "http://192.0.2.10:19000/application/o/litegate/"
    client_id: litegate-lab
    client_secret: "env:LITEGATE_AUTHENTIK_CLIENT_SECRET"
    scopes: [openid, profile, email, offline_access]
    allowed_signing_algs: [RS256]

oidc_security:
  cookie_secret: "REPLACE_WITH_RANDOM_SECRET_AT_LEAST_32_BYTES"
  cookie_same_site: lax
  me_allowed_ips: ["127.0.0.1", "::1"]
```

将 `cookie_secret` 替换为至少 32 字节的随机秘密，例如用 `openssl rand -hex 32` 生成并填入。该字段直接填写生成的值；`client_secret` 则支持上述 `env:变量名` 写法。在启动 LiteGate 的进程环境中设置 Client Secret：

```bash
export LITEGATE_AUTHENTIK_CLIENT_SECRET='替换为 authentik 的 Client Secret'
litegate -config config.yaml
```

使用 systemd 时，将变量放入服务的 `EnvironmentFile`；使用容器时传入容器环境变量。此例将会话诊断接口限制在本机；需要从测试电脑查看时，可向 `me_allowed_ips` 添加该电脑的 IP。

## 4. LiteGate 站点配置

保存为 `sites/app.yaml`，后端替换成你自己的 HTTP 服务：

```yaml
site: ":18086"

/public: 127.0.0.1:18087

/:
  proxy: 127.0.0.1:18087
  remote_auth:
    provider: authentik
    enforce: true
    inject_claims:
      X-Auth-User: preferred_username
      X-Auth-Email: email
      X-Auth-Subject: sub
```

`/public` 免登录，其余路径要求认证。`inject_claims` 的方向为 `请求头: claim`。后端读取这些头即可识别用户，且应只接受来自 LiteGate 的请求。默认回调路径由 LiteGate 接管，无需另写回调路由。

## 5. 登出配置

访问 `http://192.0.2.10:18086/_litegate/oauth/logout` 时，LiteGate 删除自己的会话并跳转到 authentik 的 End Session endpoint。

authentik 默认的 `default-provider-invalidation-flow` 保留全局 SSO 会话。若登出后返回受保护的 `/`，浏览器可能立即通过 SSO 再次登录。

若希望本例登出后重新输入用户名和密码，把 Provider 的 **Invalidation flow** 设为 **`default-invalidation-flow`**。此流程同时退出 authentik 的全局会话，会影响该浏览器后续访问其他 authentik 应用时的 SSO。前面的 Logout redirect URI 也必须登记。

这是浏览器主动登出；当前 LiteGate 未实现接收 authentik back-channel logout 通知。

## 6. 验证

| 操作 | 预期 |
| --- | --- |
| 浏览器打开 `http://192.0.2.10:18086/` | 跳到 authentik，测试用户登录后回到应用 |
| 查看后端收到的请求头 | `X-Auth-User`、`X-Auth-Email`、`X-Auth-Subject` 对应登录用户 |
| `curl -i http://192.0.2.10:18086/orders` | 无会话的 API 请求返回 `401` |
| `curl -i http://192.0.2.10:18086/public` | 后端正常返回，免登录 |
| 客户端伪造 `X-Auth-User` | 受保护路由覆盖为真实用户，公开路由清除该头 |
| 登录后查看 `/_litegate/oauth/me` | 在允许的 IP 上返回 `provider: authentik` 和用户 claims |
| 临时把 Provider access token 有效期设为 2 分钟，登录约 100 秒后访问受保护路由 | 保持登录，`/me` 的 `expiry` 延长；验证后恢复所需有效期 |
| 使用完整登出流程后访问应用 | 重新显示 authentik 登录页 |

浏览器请求（`Accept` 含 `text/html`）跳转登录；API 请求返回 `401`。authentik 不可用或 Discovery 失败时，受保护路由返回 `503`，Provider 初始化会在后台重试。

## 相关文档

- [OIDC / OAuth2 认证配置指南](oidc.md)
- [认证概述](authentication.md)
- [authentik OAuth2/OIDC Provider](https://docs.goauthentik.io/add-secure-apps/providers/oauth2/)
