# Rewrite：路径与查询参数改写

LiteGate 的 `rewrite` 用来把请求 URL 适配成当前后端认识的格式。**路由匹配先决定使用哪条 route 和哪个上游，rewrite 随后修改这条 route 内的路径与查询参数。改写后不会重新匹配路由。**

例如 `/legacy/users/42` 可以改成 `/api/users/42`，但请求仍由原来命中的 route 处理。浏览器地址不变，也不会收到 rewrite 产生的 `3xx` 响应。

## 1. 执行顺序与 Nginx 的区别

对一个进入路由处理流程的请求，主要顺序是：

```text
原始请求 → 匹配 Site / Route → CORS 与预检处理
         → rewrite → 其他 RequestTransform 中间件
         → 安全检查与流量控制 → 当前 route 的 Action
```

因此，路由的 `Path`、`Query`、`Header` 等条件在 rewrite 之前判断；后续 WAF、IP 策略、鉴权、限流看到的是经过 RequestTransform 阶段处理的请求。CORS 预检可能提前返回，此时不会进入 rewrite。

| 场景 | Nginx | LiteGate |
| :--- | :--- | :--- |
| 改写后重新选路 | `rewrite ... last` 会按新 URI 重新查找 location | rewrite 不会重新匹配 route；需要在原始请求的匹配条件中直接选路 |
| 当前处理分支内改写 | `break` 停止当前 rewrite 指令集，继续当前 location 的处理 | 用当前 route 的 `rewrite`，没有 `last` / `break` 标志 |
| 让浏览器访问新地址 | rewrite 可使用 `redirect` / `permanent`，或 URL replacement | 使用 `redirect` Action，或 `redirect_regex` / `redirect_scheme` 中间件 |
| 正则语法 | PCRE | Go `regexp`；不能直接照搬前后向断言、正则反向引用等 PCRE 写法 |
| 新增或删除查询参数 | replacement 可以包含查询串，并有旧参数追加规则 | `path.target` 只写路径；参数单独放到 `query` 中操作 |

Nginx 行为参见 [官方 rewrite 模块文档](https://nginx.org/en/docs/http/ngx_http_rewrite_module.html#rewrite)。上述对比用于迁移配置；LiteGate 的 rewrite 并不是对 Nginx 指令集的兼容实现。

## 2. 一份完整的路径改写配置

```yaml
site: api.example.com

routes:
  - name: legacy-users
    match:
      rule: 'PathRegex("^/legacy/users/([^/]+)$")'
    action:
      type: proxy
      upstream: ["127.0.0.1:8080"]
      rewrite:
        path:
          pattern: '^/legacy/users/([^/]+)$'
          target: '/api/users/${1}'
```

请求 `/legacy/users/42?view=full` 会发送到当前上游的 `/api/users/42?view=full`。这里只改路径，原始查询串保持不变。

`match.rule` 决定是否选择这条 route；`rewrite.path.pattern` 决定这条 route 中是否执行改写。这是两次不同用途的匹配。**rewrite 中的捕获组来自自己的 `path.pattern`，不是路由匹配正则的捕获组。**

| 字段 | 说明 |
| :--- | :--- |
| `path.pattern` | Go 正则，作用于解码后的 `URL.Path`，不包含查询串；非法正则会在加载时拒绝 |
| `path.target` | 替换后的路径，必须以 `/` 开头，不能包含 `?`、`#` 或控制字符 |

`pattern` 和 `target` 必须成对配置。建议用 `^`、`$` 限定整条路径：底层使用 `ReplaceAllString`，未加锚点的正则可能替换多个匹配片段。

替换文本支持 `$1`、`${1}` 和命名捕获组引用。捕获组后紧接普通字符时，用 `${1}` 明确边界，例如 `/v${1}suffix`。路径 target 不展开 `{query.x}`、`{header.X}` 等请求变量；这些变量可用于下面的 query `set` / `add`。

旧版写法 `rewrite.pattern` / `rewrite.target` 仍兼容，但不能与 `rewrite.path` 同时配置。新配置建议使用 `path`。

## 3. 查询参数改写

路径与查询参数可以一起改写：

```yaml
site: api.example.com

routes:
  - name: legacy-users
    match:
      rule: 'PathRegex("^/legacy/users/([^/]+)$")'
    action:
      type: proxy
      upstream: ["127.0.0.1:8080"]
      rewrite:
        path:
          pattern: '^/legacy/users/([^/]+)$'
          target: '/api/users/${1}'
        query:
          remove: [debug]
          rename:
            uid: user_id
          set:
            source: litegate
            path_user: '$1'
            trace: '{header.X-Trace-ID}'
          add:
            tag: migrated
```

若请求为 `/legacy/users/42?uid=7&debug=1&tag=old`，且请求头 `X-Trace-ID: t123`，上游收到：

```text
/api/users/42?path_user=42&source=litegate&tag=old&tag=migrated&trace=t123&user_id=7
```

操作顺序固定为 **`remove → rename → set → add`**，与 YAML 中字段书写的先后顺序无关。

| 操作 | 行为 |
| :--- | :--- |
| `remove` | 删除参数及其全部值；不存在时跳过 |
| `rename` | 移动源参数的全部值，覆盖目标参数已有值；源不存在时不改变目标 |
| `set` | 将参数覆盖为一个值；不存在时创建 |
| `add` | 追加一个值，保留已有同名值 |

rename 使用同一份源值快照，不会按 map 遍历顺序串行搬运。例如 `a: b`、`b: c` 将旧 `a` 移到 `b`，旧 `b` 移到 `c`，不会把旧 `a` 连续搬到 `c`。多个源重命名到同一个目标会在加载时拒绝。

`set` / `add` 的值支持路径捕获组及 `{host}`、`{path}`、`{query.x}`、`{header.X}`、`{cookie.x}` 等请求变量。此时 `{path}` 是本次路径改写后的路径；`{query.x}` 读取请求 URL 中的查询参数，不读取正在构建的 query 操作结果，因此不要依赖 `set` 字段之间的先后顺序。query 捕获引用使用 `$1`、`$2` 等写法；当前 query 模板会把花括号解析为请求变量，因此不要照搬路径 target 的 `${1}` 写法。请求提供的字符串只展开一次，例如请求值本身是 `$1` 时，会作为普通文本保留。

可以省略 `path`，只配置 `query`。**如果配置了 `path` 却没有匹配成功，整条 rewrite 都跳过，query 操作也不执行。** 想对整条 route 的所有请求改参数时，使用纯 query 改写，或确保路径正则覆盖该 route 的请求。

## 4. 从 Nginx `last` 迁移：直接用匹配规则选上游

假设 `/callback` 默认交给旧服务，但 `state` 以 `sub.` 开头的请求需要交给新服务，而新服务只接受 `/sub_callback`。不要先改成 `/sub_callback` 再期待另一条 route 接管；直接在原始请求上匹配条件，并在同一条 route 中指定上游与目标路径：

```yaml
site: oauth.example.com

routes:
  - name: sub-callback
    priority: 200
    match:
      rule: 'Path("/callback") && QueryPrefix("state", "sub.")'
    action:
      type: proxy
      upstream: ["127.0.0.1:9002"]
      rewrite:
        path:
          pattern: '^/callback$'
          target: '/sub_callback'

  - name: default-callback
    priority: 100
    match:
      rule: 'Path("/callback")'
    action:
      type: proxy
      upstream: ["127.0.0.1:9001"]
```

`/callback?state=sub.abc` 发往 9002 的 `/sub_callback?state=sub.abc`；其他 `/callback` 请求走 9001。若新服务也接受 `/callback`，删除第一条 route 的 rewrite 即可，分流仍然有效。

这里的 `state` 前缀只负责选路，OAuth 后端仍要校验 state 的随机性、有效期和会话绑定。完整方案见 [单回调地址分流](../09-advanced/oauth-single-callback.md)。

## 5. 命名 middleware 写法

复用规则时，也可以定义命名 `rewrite` middleware：

```yaml
site: api.example.com

middlewares:
  legacy-adapter:
    type: rewrite
    config:
      path_pattern: '^/legacy/(.*)$'
      path_target: '/api/${1}'
      query_remove: 'debug,internal'
      query_rename.uid: user_id
      query_set.source: litegate
      query_add.tag: migrated

routes:
  - name: legacy
    match:
      path_prefix: /legacy/
    use: [legacy-adapter]
    action:
      type: proxy
      upstream: ["127.0.0.1:8080"]
```

命名形式会解析为同一套 `action.rewrite` 能力，执行语义一致。一个 route 只能有一个有效 rewrite；不能同时配置内联 rewrite 与命名 rewrite，也不能通过 chain 引用多份 rewrite。命名配置使用上面的扁平字段，不使用内联形式的 `path` / `query` 嵌套结构。

## 6. 编码、签名与排查

- 路径正则匹配解码后的路径。改写后清除 `RawPath`，转发时会重新转义；依赖原始百分号编码形式的协议应特别检查。
- 只改 path 时不重编码 query。执行 query 修改后会按标准 URL 编码生成查询串，参数顺序、空格和百分号编码形式可能变化。
- 对原始 URI 做签名校验的组件应使用 `{original_uri}` / `{original_path}`，或避免修改参与签名的内容。rewrite 保留原始 URI 的请求上下文；需要交给可信后端时，可用 Action 的 `headers` 显式投射为请求头，见 [Proxy 文档](../04-actions/proxy.md#8-url-rewrite-rewrite)。
- 配置 query 操作时，畸形查询串返回 `400`；执行 rewrite 后 URI 超过 16 KiB 返回 `414`。路径正则未命中时直接跳过本 rewrite 的处理与检查。
- 后端返回 404 时，先检查命中的 route、上游地址和最终路径。可以开启 debug 日志查看 `URL rewrite executed`，也可以通过 MCP 的 `lookup_route` 检查有效执行链。

选择能力时：简单剥前缀可用 `strip_prefix`，纯正则路径替换可用 `replace_path_regex`；改路径和参数用 rewrite；让浏览器跳转用 redirect；SPA 或入口脚本回退用 `try_files`。具体配置见 [路径改写与重定向中间件](../05-middleware/path-and-redirect.md) 和 [Serve](../04-actions/serve.md)。
