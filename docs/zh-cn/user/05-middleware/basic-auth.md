# Basic Auth (HTTP 基本认证中间件)

`basic_auth` 是一个命名 middleware，用标准的 HTTP Basic 认证（`WWW-Authenticate: Basic`）保护路由。它适合内部工具、Staging 环境、简单后台等“不想接入 OIDC/SSO，但又要挡住匿名访问”的场景。

> **一句话须知**：`users` 里存的**必须是 bcrypt 哈希**（`htpasswd -B` 生成），**不能写明文密码**。写了明文会在加载时直接报错。

---

## 1. 快速开始

第一步，用 LiteGate 自带命令生成 **bcrypt** 密码哈希（无需额外安装工具）：

```bash
./litegate -hash 'S3cret!'
# 日志输出中的 hash 字段即为结果，例如：
#   hash=$2a$10$Q9Q0k8m....（60 个字符的 bcrypt 哈希）
```

第二步，把 `用户名:哈希` 填进命名 middleware，并在路由中引用：

```yaml
domain: internal.example.com

middlewares:
  admin-gate:
    type: basic_auth
    config:
      users: "admin:$2y$05$Q9Q0k8m....."   # 用户名:bcrypt哈希
      realm: "Internal Tools"

routes:
  - name: dashboard
    match:
      path_prefix: /
    middlewares: [admin-gate]
    action:
      type: proxy
      upstream: ["127.0.0.1:8080"]
```

未携带凭证或凭证错误时，网关返回 **`401 Unauthorized`** 并带 `WWW-Authenticate: Basic realm="Internal Tools"`，浏览器会自动弹出登录框。

---

## 2. 配置字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `users` | string | 是 | — | 逗号分隔的 `username:bcrypt_hash` 列表。哈希必须是合法 bcrypt（`$2a$`/`$2b$`/`$2y$` 开头，共 60 字符）。 |
| `realm` | string | 否 | `LiteGate Restricted` | 认证域名称，显示在浏览器登录框里。不能包含双引号或控制字符。 |
| `remove_header` | bool | 否 | `false` | 认证通过后是否删除 `Authorization` 头，避免把 Basic 凭证透传给上游后端。 |
| `enabled` | bool | 否 | `true` | 设为 `false` 时该定义不进入运行时管线，也不参与组合冲突检查。 |

多个用户用逗号分隔：

```yaml
config:
  users: "admin:$2y$05$AAAA....,ops:$2y$05$BBBB....."
```

---

## 3. 生成 bcrypt 哈希的几种方式

| 工具 | 命令 | 说明 |
| :--- | :--- | :--- |
| **LiteGate 自带（推荐）** | `./litegate -hash 'password'` | 直接输出 bcrypt 哈希，无需安装任何额外工具 |
| Apache htpasswd | `htpasswd -nbB user 'password'` | 输出 `user:hash`，取冒号后半段 |
| Python | `python -c "import bcrypt;print(bcrypt.hashpw(b'password', bcrypt.gensalt()).decode())"` | 需 `pip install bcrypt` |

> 只支持 **bcrypt**。MD5(`$apr1$`)、SHA(`{SHA}`) 和明文都不被接受，加载时会报 `password must be a valid bcrypt hash`。

---

## 4. 与内联 `action.auth: {type: basic}` 的区别

LiteGate 里有两条“basic 认证”的路径，别混淆：

| 维度 | 命名 `basic_auth` middleware（本页） | 内联 `action.auth: { type: basic }` |
| :--- | :--- | :--- |
| 定位 | 通用、可复用、可被多路由引用的横切中间件 | 绑定在单个路由 action 上的静态认证 |
| 复用 | 定义一次，多路由 `middlewares: [name]` 引用 | 每个路由各写各的 |
| 执行阶段 | Authentication phase，统一编译进 PipelinePlan | Action 内联，走 `Action.Auth` 那条链路 |
| 推荐场景 | 多路由共享同一套账号、想在 Dashboard 看到管线 | 单路由一次性保护 |

**建议**：需要在多条路由复用、或希望执行顺序在 PipelinePlan 里可见时，用命名 `basic_auth`；只保护单个路由的一次性场景，内联 `action.auth` 更省事。

---

## 5. 执行位置与安全说明

- **阶段**：`basic_auth` 位于 **Authentication** phase，在 CORS 预检、请求改写和 WAF 之后、代理动作之前执行。CORS 预检（`OPTIONS`）不会被它拦截。
- **单实例**：`basic_auth` 的 `AllowMultiple = false`，一个路由只能有一个有效的 basic 认证定义，重复挂载会在加载时报错。
- **伪造头清理**：进入认证前会剥离客户端伪造的内部身份头（与 `jwt_auth` / `api_key` 一致）。
- **抗用户名枚举**：用户不存在时，网关仍会对一个固定哑哈希执行一次 bcrypt 校验，使“用户不存在”与“密码错误”耗时一致，避免通过响应时间枚举有效用户名。
- **务必配合 HTTPS**：Basic 凭证是 Base64 编码而非加密，明文链路上等同裸奔。生产环境请只在 TLS 入口启用。

---

## 6. 常见问题 (FAQ)

**Q：配置后所有请求都 401，账号密码明明是对的？**
最常见原因是 `users` 里写了**明文密码**而不是 bcrypt 哈希。当前版本已在加载期拦截明文，如果你用的是旧配置或从别处拷贝的哈希，请确认它以 `$2a$`/`$2b$`/`$2y$` 开头且共 60 字符。

**Q：能不能让后端也拿到用户名？**
认证通过后请求会继续转发，但本中间件不会注入用户名头。如需把身份传给上游，用 `jwt_auth` 的 `inject_claims`，或在后端自行解析。若担心 Basic 凭证泄漏给后端，设 `remove_header: true`。

**Q：`realm` 里能写中文吗？**
可以，但不能包含双引号 `"` 和控制字符，否则加载失败。

---

## 延伸阅读
- [认证总览](./authentication.md)
- [Middleware Pipeline 与 Chain](./pipeline.md)
- [OIDC 单点登录](./oidc.md)
