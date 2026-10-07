# 单回调地址分流（OAuth 一个回调地址，多个后端）

很多第三方开放平台（淘宝、微信、钉钉、企业微信、各类电商/支付平台）在应用配置里**只允许填写一个 OAuth 回调地址**。但实际业务往往需要把回调分给不同的处理逻辑，例如：

- **主账号授权** 和 **子账号授权** 走不同的后端服务；
- 不同租户 / 不同业务线共用一个平台应用，但回调后要落到各自的处理器。

平台只给一个回调地址，怎么在网关层把它再拆开？这篇文档给出 LiteGate 的标准做法。

---

## 1. 核心思路：用 `state` 分流，靠“匹配”而不是“改写”切上游

OAuth 授权发起时你自己会带上一个 `state` 参数，平台会原样回传。**`state` 就是天然的分流依据**——发起授权时给不同业务打上不同前缀即可：

| 授权类型 | 发起时的 state | 回调 URL（平台只认这一个） |
| --- | --- | --- |
| 主账号 | `main.<nonce>` | `https://cb.example.com/callback?...&state=main.abc` |
| 子账号 | `sub.<nonce>`  | `https://cb.example.com/callback?...&state=sub.xyz`  |

LiteGate 用 [`QueryPrefix`](../03-configuration/site-config.md#9-规则表达式-rule-dsl-参考) 规则按 `state` 前缀命中不同路由，**每条路由直接决定自己的上游和路径**。

> **和 Nginx 的关键区别**
>
> Nginx 里常见的写法是：
> ```nginx
> location = /callback {
>     if ($arg_state ~ ^sub\.) { rewrite ^/callback$ /sub_callback last; }
>     proxy_pass http://main_backend;
> }
> ```
> 这里 `rewrite ... last` 的**真实目的不是改路径，而是借“改写后重新匹配 location”来切换上游**——因为 Nginx 的 `if` 没法在同一个 location 里换 `proxy_pass`。改路径只是副作用，后端还得被迫多挂一个 `/sub_callback`。
>
> LiteGate 反过来：**切上游是匹配规则本身的结果**，改路径是可选的、独立的动作。所以下面的方案里，大多数情况根本不需要 `rewrite`。

---

## 2. 方案 A：一个服务，用路径区分（推荐，最简单）

如果你愿意把主/子账号的处理器放在**同一个后端服务**里，只是监听不同 path（例如 `/oauth/main/callback` 和 `/oauth/sub/callback`），那么网关只做“按 state 前缀改写路径”即可，上游始终是同一个：

```yaml
domain: cb.example.com
routes:
  # 子账号：state 以 sub. 开头 → 改写到后端的子账号路径
  - name: oauth-callback-sub
    priority: 200
    match:
      rule: 'Path("/callback") && QueryPrefix("state", "sub.")'
    action:
      type: proxy
      upstream: ["127.0.0.1:8080"]
      rewrite:
        path:
          pattern: "^/callback$"
          target: "/oauth/sub/callback"

  # 主账号（以及其它所有回调）→ 改写到后端的主账号路径
  - name: oauth-callback-main
    priority: 100
    match:
      rule: 'Path("/callback")'
    action:
      type: proxy
      upstream: ["127.0.0.1:8080"]
      rewrite:
        path:
          pattern: "^/callback$"
          target: "/oauth/main/callback"
```

请求 `GET /callback?code=...&state=sub.xyz` 会被改写成 `/oauth/sub/callback?code=...&state=sub.xyz` 转给后端；其余回落到主账号路径。query（含 `code`、`state`）原样保留。

**适用场景**：后端是一个服务、代码在一个仓库里，只是想按类型分函数处理。改动最小，运维最简单。

---

## 3. 方案 B：两个服务，切换上游

如果主/子账号是**两个独立部署的服务**（不同进程、不同机器），就让匹配规则直接选不同 upstream。是否还需要 `rewrite`，**取决于目标后端注册了哪个路径**：

### B-1：后端已经挂了 `/callback` —— 不需要 rewrite

```yaml
routes:
  - name: oauth-callback-sub
    priority: 200
    match:
      rule: 'Path("/callback") && QueryPrefix("state", "sub.")'
    action:
      type: proxy
      upstream: ["10.0.0.2:9091"]   # 子账号服务，本身就处理 /callback

  - name: oauth-callback-main
    priority: 100
    match:
      rule: 'Path("/callback")'
    action:
      type: proxy
      upstream: ["10.0.0.1:9091"]   # 主账号服务，本身就处理 /callback
```

匹配规则已经把请求送到正确的服务，两个服务都在 `/callback` 上接收，**无需改写路径**。

### B-2：后端只挂了 `/sub_callback` —— 必须 rewrite

如果子账号服务只在 `/sub_callback` 上监听、不认识 `/callback`，那么直转会 404，必须把路径改写成后端认识的样子：

```yaml
  - name: oauth-callback-sub
    priority: 200
    match:
      rule: 'Path("/callback") && QueryPrefix("state", "sub.")'
    action:
      type: proxy
      upstream: ["10.0.0.2:9091"]
      rewrite:
        path:
          pattern: "^/callback$"
          target: "/sub_callback"    # 改成后端注册的路径
```

**判断标准一句话**：要不要 `rewrite`，只看“进来的路径”和“后端监听的路径”是否一致，**跟切不切上游无关**。

---

## 4. 三个必看的注意事项

### ① 多条路由匹配同一 path 时，全部要用 `rule:`，不要用 `path:`

上面主账号那条为什么写成 `rule: 'Path("/callback")'` 而不是更直观的 `path: "/callback"`？

因为 LiteGate 对 `path:`（精确路径）做了 **O(1) 精确匹配加速**，它会在按 `priority` 排序的常规匹配**之前**命中。一旦主账号用了 `path: "/callback"`，它会**无条件抢先命中**，`priority: 200` 的子账号规则永远轮不到——`state=sub.` 的回调会被错误地送到主账号后端。

**规则**：当多条路由落在同一个 path、靠附加条件（query / header）区分先后时，**这些路由都用 `rule:` 表达**，让它们统一走 `priority` 排序。像 `/authorize`、`/manual_exchange` 这种只有一条路由、不重叠的路径，继续用 `path:` 更快，不受影响。

### ② `state` 必须是单值，且不能只靠前缀做安全

- 参与匹配的 query 参数必须**只有一个值**。`state=sub.x&state=main.x` 这种重复参数**不会命中**上述任何路由，避免网关和后端对 `state` 取到不同值（query 走私）。
- **前缀只负责分流，不能代替后端的 `state` 校验**。`state` 仍必须是随机、一次性、短期有效、并与发起授权的会话绑定的值。推荐 `sub.<nonce>.<签名>`，或在服务端保存 `state → 授权类型` 的映射后再做前缀。

### ③ `rewrite` 不会重新触发路由匹配

LiteGate 的 `rewrite` 只改写**当前路由内**的路径，**不会**像 Nginx `rewrite ... last` 那样回到路由表重新匹配。这正是它简单可控的原因：一条路由从匹配到上游是一条直线，不会二次跳转。

---

## 5. 完整示例

一个平台应用、一个回调地址，同时支持主/子账号，外加授权入口和门户静态资源：

```yaml
domain: cb.example.com
defaults:
  timeout: 600
routes:
  # 授权入口（发起 OAuth，带上 state=main./sub. 前缀由业务代码决定）
  - name: authorize
    priority: 100
    match:
      path: "/authorize"
    action:
      type: proxy
      upstream: ["10.0.0.1:9091"]

  # 子账号回调
  - name: oauth-callback-sub
    priority: 200
    match:
      rule: 'Path("/callback") && QueryPrefix("state", "sub.")'
    action:
      type: proxy
      upstream: ["10.0.0.2:9091"]

  # 主账号及其它回调
  - name: oauth-callback-main
    priority: 100
    match:
      rule: 'Path("/callback")'
    action:
      type: proxy
      upstream: ["10.0.0.1:9091"]

  # 授权门户静态资源
  - name: oauth-portal
    priority: 50
    match:
      path_prefix: "/portal/"
    action:
      type: proxy
      upstream: ["10.0.0.2:9091"]
      strip_prefix: "/portal"
```

---

## 6. 验证与排错

发一个带子账号前缀的回调，看它是否落到子账号上游：

```bash
curl -i "https://cb.example.com/callback?code=test&state=sub.abc123"
```

- **落错上游（子账号回调打到主账号）**：99% 是注意事项 ① —— 主账号路由用了 `path:` 而不是 `rule:`，把子账号规则短路了。改成 `rule: 'Path("/callback")'`。
- **404**：后端没有注册被转发/改写后的路径。要么在后端挂上对应 path，要么按方案 B-2 用 `rewrite` 改成后端认识的路径。
- **命中了主账号但你以为该走子账号**：检查 `state` 是不是被带成了多值（`&state=` 出现两次），多值不参与匹配；以及前缀是否真的是 `sub.`（区分大小写）。
- 想确认某个请求最终会命中哪条路由，可用 LiteGate 的路由查询工具（MCP `lookup_route`）或开启 access log 的 `routing_detail`。

---

## 相关文档

- [Proxy 转发与 `rewrite` 参数详解](../04-actions/proxy.md#8-url-rewrite-rewrite)
- [规则表达式 Rule DSL（`Path` / `QueryPrefix` 等）](../03-configuration/site-config.md#9-规则表达式-rule-dsl-参考)
- [路由优先级解析](../02-concepts/routing-priority.md)
- [干净 URL 全部回退到入口脚本（WordPress/Laravel/SPA）用 `try_files`](../04-actions/serve.md)
