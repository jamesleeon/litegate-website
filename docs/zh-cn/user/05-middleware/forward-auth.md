# 使用 Authelia 为 LiteGate 站点添加统一登录

如果应用没有自己的登录系统，或者希望在进入应用前统一检查用户、用户组和双因素认证，可以使用 `forward_auth`。浏览器先访问 LiteGate，网关向 Authelia 检查身份与访问权限，通过后才把请求交给业务服务。

如果只是给单个网站增加用户名、密码登录，可以使用 LiteGate 内置的 `auth.type: sso`，无需部署 Authelia。它提供登录页、登录后返回原页面、会话 Cookie 和退出登录，每次请求在本地校验 Cookie 签名及有效期。用户与 bcrypt 密码哈希在站点配置中维护，也可指定自定义登录页模板。详见 [本地认证说明](./authentication.md#11-静态认证auth)。

内置 SSO 当前侧重访问入口保护：不提供用户组策略、双因素认证或自动向后端传递用户身份；Cookie 也没有设置跨域共享的 Domain。需要这些能力时，再采用下文的 Authelia 接入方案。

默认发行版包含纯 Go 的 Forward Auth 中间件插件，无需 CGO。它在 Authentication 阶段执行，早于业务动作和代理缓存。每个受保护 HTTP 请求都检查一次；用户登录后携带会话 Cookie，通常无需再次输入密码。LiteGate 不需要为这条链路配置 OIDC 或 Redis；Authelia 自身的会话与存储单独配置。

## 1. 配置登录门户与受保护网站

登录门户和应用分别配置为两个站点，也可以放在同一个文件中用 `---` 分隔：

```yaml
site: auth.example.com
https: true
proxy: authelia:9091
---
site: app1.example.com
https: true
forward_auth:
  address: authelia:9091
  uri: /api/authz/forward-auth
  copy_headers: [Remote-User, Remote-Groups, Remote-Name, Remote-Email]
proxy: app1:8080
```

默认已复制上述四个 Authelia 身份头，所以通常只需：

```yaml
site: app1.example.com
https: true
forward_auth: http://authelia:9091/api/authz/forward-auth
proxy: app1:8080
```

完整 URL 简写也适用于其他采用相同协议的鉴权服务。插件不会自动猜测 Authelia 路径。`authelia`、`app1` 这样的容器名称，仅在 LiteGate 所在网络能解析这些名称时使用；LiteGate 运行在宿主机时，改用实际地址，例如 `127.0.0.1:9091`。

LiteGate 向鉴权接口发出不带业务请求体的 GET，收到 2xx 后继续处理业务请求；401/403 和常见登录跳转会返回给客户端，鉴权服务异常则返回 503。当前不支持多个鉴权 upstream 或身份头重命名。

## 2. 准备域名、HTTPS 和 Authelia

示例使用登录门户 `https://auth.example.com`、应用 `https://app1.example.com`，Authelia 和应用分别监听本机 `9091`、`8080`。

两个域名都需要解析到 LiteGate，HTTPS 证书需要覆盖它们。`https: true` 启用站点 HTTPS 行为，证书还需通过 [自动证书](../06-certificates/auto-cert.md) 或已有证书配置提供。Authelia 使用 Secure Cookie；直接使用 HTTP 或裸 IP 无法完成这套浏览器登录流程。内网可以使用域名与测试证书。

已有 Authelia 时，检查下文的 Cookie 和访问规则即可。新建测试实例可使用文件用户库、SQLite 和默认内存会话。

创建目录，生成用户密码哈希：

```bash
mkdir -p authelia
docker run --rm authelia/authelia:4.39.28 \
  authelia crypto hash generate argon2 \
  --password 'replace-with-your-test-password' --no-confirm
```

把输出的 `Digest` 填入 `authelia/users_database.yml`：

```yaml
users:
  demo:
    displayname: Demo User
    password: 'PASTE_ARGON2_DIGEST_HERE'
    email: demo@example.com
    groups: [admins]
```

`authelia/configuration.yml` 单实例示例。三个 secret 使用不同的随机值，例如分别运行 `openssl rand -hex 32` 生成；不要保留占位符。

```yaml
server:
  address: tcp://0.0.0.0:9091
log:
  level: info
identity_validation:
  reset_password:
    jwt_secret: REPLACE_WITH_RANDOM_SECRET_1
authentication_backend:
  file:
    path: /config/users_database.yml
access_control:
  default_policy: deny
  rules:
    - domain: app1.example.com
      policy: one_factor
session:
  secret: REPLACE_WITH_RANDOM_SECRET_2
  same_site: lax
  cookies:
    - domain: example.com
      authelia_url: https://auth.example.com
      default_redirection_url: https://app1.example.com
storage:
  encryption_key: REPLACE_WITH_RANDOM_SECRET_3
  local:
    path: /config/db.sqlite3
notifier:
  filesystem:
    filename: /config/notification.txt
```

这个示例使用 `one_factor` 先验证用户名、密码和跳转流程。文件通知用于测试，生产通知应按需要配置 SMTP；多实例部署应配置共享会话存储。参见 [Authelia 会话配置](https://www.authelia.com/configuration/session/introduction/)。

校验后启动容器，只把鉴权端口映射到宿主机回环地址：

```bash
docker run --rm -v "$PWD/authelia:/config" authelia/authelia:4.39.28 \
  authelia validate-config --config /config/configuration.yml

docker run -d --name authelia --restart unless-stopped \
  -p 127.0.0.1:9091:9091 \
  -v "$PWD/authelia:/config" authelia/authelia:4.39.28
```

## 3. 配置 LiteGate 的两个站点

登录门户 `sites/auth.yaml`：

```yaml
site: auth.example.com
https: true
proxy: 127.0.0.1:9091
```

**登录门户不要挂载 `forward_auth`**，否则用户无法进入登录页面。

应用 `sites/app1.yaml`：

```yaml
site: app1.example.com
https: true
forward_auth: http://127.0.0.1:9091/api/authz/forward-auth
proxy: 127.0.0.1:8080
```

保存前校验：

```bash
litegate -t -config config.yaml
```

运行中的 LiteGate 会热加载站点文件。如果是在旧二进制中首次使用此功能，需要先升级到包含 Forward Auth 插件的版本。

打开应用域名，应先跳转 Authelia，输入 `demo` 和用户库对应的密码，成功后回到应用。后端能收到 `Remote-User`、`Remote-Groups`、`Remote-Name` 和 `Remote-Email`。

## 4. 只保护部分路径，或复用认证配置

站点级 `forward_auth` 继承到所有路由，包括静态文件和 PHP。只保护管理后台时，把它写在路由下：

```yaml
site: app1.example.com
https: true
/admin:
  forward_auth: http://127.0.0.1:9091/api/authz/forward-auth
  proxy: 127.0.0.1:8080
proxy: 127.0.0.1:8080
```

多条路由共用一份配置时，原来的命名中间件写法仍然支持：

```yaml
site: app1.example.com
https: true
middlewares:
  login:
    type: forward_auth
    config:
      address: 127.0.0.1:9091
      uri: /api/authz/forward-auth
      timeout: 3s
      copy_headers: [Remote-User, Remote-Groups, Remote-Name, Remote-Email]
/admin:
  use: login
  proxy: 127.0.0.1:8080
/private:
  use: login
  proxy: 127.0.0.1:8080
respond: public
```

也可以通过 `snippets` / `import` 复用内联 `forward_auth`。路由配置替换完整的站点级配置，不深合并；`false` 不代表关闭认证，会报错。需要公开路径时，把鉴权放到受保护路由，或在 Authelia 中显式配置访问规则。同一路由不要同时通过内联和 `use` 挂载同一种鉴权中间件。

## 5. 管理员权限和 MFA

网关决定是否调用鉴权，谁能访问什么资源由 Authelia 配置。例如仅允许 `admins` 访问管理员页面：

```yaml
access_control:
  default_policy: deny
  rules:
    - domain: app1.example.com
      resources: ['^/admin(?:/.*)?$']
      subject: ['group:admins']
      policy: one_factor
    - domain: app1.example.com
      resources: ['^/admin(?:/.*)?$']
      policy: deny
    - domain: app1.example.com
      policy: one_factor
```

规则顺序有意义：先允许管理员，再拒绝其他用户访问同一路径，最后允许已登录用户访问普通页面。把所需规则的 `policy` 改成 `two_factor` 可以要求 MFA；用户仍需在 Authelia 中完成相应注册和认证。当前演示已验证密码登录与用户组规则，MFA 注册流程需要按实际通知和二因素设置验证。

## 6. 参数和响应行为

| 字段 | 默认值 | 含义 |
|---|---|---|
| `address` | 必填 | 完整 HTTP(S) URL，或按 HTTP 访问的裸地址 |
| `uri` | 不覆盖地址 | 鉴权路径和查询参数；不能与地址已有路径或查询重复配置 |
| `timeout` | `5s` | 正数 duration，例如 `500ms`、`3s` |
| `request_headers` | `[Cookie, Authorization, Accept]` | 发给鉴权服务的请求头白名单，空数组表示不转发 |
| `copy_headers` | 四个 `Remote-*` 身份头 | 从成功鉴权响应复制到业务请求的头，空数组表示不复制 |
| `response_headers` | 同 `copy_headers` | 兼容旧字段，不能与 `copy_headers` 同时配置 |

- 仅 2xx 放行；401/403 拒绝；302/303/307/308 返回浏览器登录跳转。超时、连接错误、5xx 和意外状态返回 503，不放行，没有鉴权缓存。
- 网关生成 `X-Forwarded-Method/Proto/Host/Uri/For`，URI 包含原始查询参数；IP 和 HTTPS 状态使用宿主已解析的可信信息。前面有其他代理时，正确设置 LiteGate 的可信代理。
- 默认身份头及复制白名单中的目标头，会先从客户端请求清除；只有鉴权服务返回的白名单头可以注入。后端应只允许网关访问，不要通过后续配置覆盖身份头。
- 保留鉴权响应的 `Set-Cookie`；拒绝时保留 `WWW-Authenticate`。正文由网关生成，不转发鉴权服务 HTML。
- 鉴权 HTTPS 使用系统证书验证；内部调用不使用环境 HTTP 代理。客户端取消会取消鉴权请求。
- WebSocket 握手会鉴权，升级后的消息不逐条鉴权。

## 7. 验证和排错

依次检查：无会话访问应用得到 302；登录后应用返回 200 并收到正确身份；普通用户访问管理员路径得到 403；伪造身份头不能绕过登录；鉴权服务不可用时得到 503。

上述五项已在 Linux 测试机、Authelia 4.39.28 和 LiteGate 编译产物上验证；仓库还覆盖配置简写、路径重写、请求体保留、取消和错误跳转等测试。

| 现象 | 检查位置 |
|---|---|
| 登录后反复跳转 | Cookie domain 是否覆盖应用和门户；是否 HTTPS；浏览器是否接受证书并保存 Cookie |
| 未登录立即 403 | Authelia domain、访问规则和 session cookie domain |
| 返回 503 | 鉴权地址是否可达；接口路径、服务健康、超时和 TLS 验证 |
| 未知 `forward_auth` | 是否为最新默认构建；自定义入口是否导入插件包 |
| 身份头为空 | `copy_headers`、应用读取的头名称，以及后续配置是否覆盖 |
| 非标准 HTTPS 端口跳转不对 | `authelia_url`、`default_redirection_url` 是否包含实际端口，例如 `:18443` |

进一步阅读：[Authelia 代理鉴权协议](https://www.authelia.com/reference/guides/proxy-authorization/) · [LiteGate OIDC 接入](oidc.md)。OIDC 使用 LiteGate 自己的登录会话，Forward Auth 使用 Authelia 的逐请求鉴权，两种方式分别配置。
