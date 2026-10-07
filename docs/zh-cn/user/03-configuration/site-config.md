<!-- GENERATED FILE — DO NOT EDIT.
     Source: internal/configdocs/docs/zh/site-config.md (package internal/configdocs)
     Regenerate: go generate ./internal/configdocs/...
     Edit the source instead; a drift test fails if this copy is edited directly. -->

# 站点配置参考 (`sites/*.yaml`)

每个站点对应一个 YAML 文件，默认放在 `./sites` 目录。LiteGate 会扫描该目录并在变更后热加载。

> [!TIP]
> MCP 的 `get_config_guide` 直接返回本文件内容。这里的字段应与当前代码中的 `internal/loader/types.go` 保持一致。

---

## 0. 统一站点 YAML（v2，新配置默认写法）

> [!TIP]
> 想直接找能复制的写法？先看 [常用场景案例](../cookbook/README.md)（反向代理、SPA、按路径分流、跨域、限流、跳转、常见报错等），每个案例都经过自动化测试。

新建站点统一使用 `.yaml` 文件与顶层 `site:`，不再要求用户选择 Lite 或标准模式。`version: 2` 可省略；顶层 `site` 识别 v2，`domain` 识别旧标准，旧 `.lite.yaml` 域名映射继续兼容。同一文件的多个 YAML 文档必须使用相同格式。现有文件保持原写法，不需要迁移。

AI 创建新配置时默认使用下面的 v2 写法；编辑已有配置时保留原格式。`litegate -t -config config.yaml` 通过统一 Loader 检查三种格式，无需新增迁移或检查命令。v2 的 `https` 缺省为 false，显式 true 或 false 优先，不自动启用 HTTPS；创建工具保留各自既有 HTTPS 行为。

```yaml
site: api.example.com
proxy: localhost:8080, 192.168.50.110:8088
```

前后端分流，路径键表示按路径段匹配的前缀；站点动作作为兜底：

```yaml
site: app.example.com
response_headers:
  X-Frame-Options: DENY
/api:
  proxy: localhost:8080
  strip_prefix: true
  cache: {ttl: 30s}
spa: ./dist
```

- 静态文件用 `serve: ./public`，SPA 用 `spa: ./dist`。`respond: ok` 与 `redirect: https://example.com` 是单动作简写。
- `proxy` 标量与列表始终是地址，逗号分隔多个地址。命名本地 Service 用 `service: orders` 或 `proxy: {service: orders}`，并在 services 定义；高级发现/连接参数可用 `action` 保留原内部字段，不能把发现名称直接写成 proxy 地址。
- 精确路径、method/header/query/rule 等复合条件用 `routes` 列表与 `match`；路径键不能同时写 match。原 Action 的高级配置写在 `action` 下，由同一个内部模型处理。
- `use` 引用已定义中间件。站点 request_headers 只作用于代理，response_headers 作用于全部动作，路由同名值覆盖站点值。
- 有子路由时，鉴权/限流等根路由处理写在显式 `/` 路由；全站中间件用站点 use。布尔 true 或字符串 "true" 的 strip_prefix 都要求前缀匹配。
- MCP `enable_jwt/apikey/oidc_for_site` 支持单文档 v2 与旧标准配置。v2 在 AST 上修改代理路由，保留注释与简写，重复调用不重复绑定；JWT/API Key 更新同名定义，类型冲突报错，OIDC 更新路由 remote_auth。静态/SPA 路由不会因本次操作被新增鉴权。旧 Lite 与多文档文件请使用完整 YAML 编辑、校验与保存。

后文根字段、match 与 action 表格作为内部模型和旧标准格式参考；v2 使用 `site`、`https`、`transports`、`use` 分别代替旧站点的 `domain`、`force_https`、`serverstransports`、路由 `middlewares`。不要把旧根字段示例整体复制成 v2。

### 监听端口简写

`site: :9090`、`site: "*:9090"`、`site: 0.0.0.0:9090` 等价于 `site: "*"` 加 `port: 9090`，接受该端口上的任意 HTTP Host。以 `*` 开头的 YAML 值必须加引号。端口范围为 1–65535，不能再同时写 `port` 或 `entrypoints`。`site: example.com:9090` 表示该端口上按域名匹配；IPv6 带端口时用 `[::1]:9090`。host 部分是请求匹配条件，不是绑定本机网络接口的地址。`https` 仍缺省 false。

```yaml
site: :9090
proxy: 127.0.0.1:8080
```

### 大小写不敏感的路径前缀

`/goapi:` 区分大小写；`~/goapi:` 不区分大小写。两者都按路径段匹配：后者匹配 `/goapi`、`/GoApi`、`/GOAPI/orders`，不匹配 `/goapix` 或 `/other/goapi`。这不是正则语法；正则仍使用 routes/match.rule。`strip_prefix: true` 去掉请求中实际匹配到的前缀，保留剩余路径的大小写。

`~/` 只保证 ASCII 路径的大小写不敏感匹配。中间件引用在继承和导入之间去重，同一处 `use` 声明内的重复仍报错。同一路径不能同时声明为 `/path` 和 `~/path`。

```yaml
site: :9090
~/goapi:
  proxy: 127.0.0.1:8080
  cors:
    allowed_origins: ["*"]
    allowed_methods: [GET, POST, OPTIONS]
    allowed_headers: ["*"]
    max_age: 1728000
```

### file_server 别名

路径键也支持直接写代理地址，等价于该路径下的 `proxy` 字段：

```yaml
site: :9090
~/goapi: 127.0.0.1:8080
spa: ./www
```

API 请求保留原路径转发给后端，其他路径由 SPA 处理。普通 `/api` 路径键也支持此简写；需要去掉前缀或添加路由配置时，改用映射形式（例如 `proxy` 加 `strip_prefix: true`）。

`file_server` 与 `serve` 等价，支持目录字符串或对象参数，也可用于路径键与 routes 列表。目录需要显式填写；同一路由不能同时写 file_server、serve、spa 或其他终结动作。Vue/React 的单页应用仍可使用 spa 简写。通用 `action: {type: file_server, root: ./public}` 同样编译为 serve。

```yaml
site: example.com
file_server: /www/example.com
```

```yaml
site: localhost
file_server: {root: ./www, index: index.html}
/api:
  proxy: localhost:9001
```

### PHP 网站（WordPress / Laravel）

`php` 自动组合 PHP-FPM、静态文件、目录首页与前端控制器回退，不需要手写正则和两条路由：

```yaml
site: example.com
https: true
compress: true
php:
  root: /var/www/wordpress
  upstream: unix:///run/php/php8.3-fpm.sock
  deny_scripts: [/wp-content/uploads]
  keep_conn: true
  max_idle_conns: 16
  idle_timeout: 60
```

把 Socket 文件名替换为实际 PHP-FPM 地址，也可以使用 `fastcgi://127.0.0.1:9000` 或地址列表。PHP-FPM 需要单独运行，LiteGate 与 PHP-FPM 必须能访问同一份网站文件。Windows 使用 TCP 地址。

默认先查找请求对应的文件，再依次查找目录下的 `index.php`、`index.html`，最后回退到根目录 `/index.php`。PHP 脚本和 PATH_INFO 请求由 PHP-FPM 执行；PHP 和 HTML 目录首页都会自动补齐末尾 `/`，保留查询参数。回退保留原始 `REQUEST_URI`、查询参数和请求体。不存在的显式 PHP 脚本返回 404，不回退，也不作为静态文件返回。

可选配置：`index`（默认 `index.php`，必须是 PHP 文件）、`try_files`（默认 `["{path}", "{path}/index.php", "{path}/index.html", "/index.php"]`）、`timeout`（秒）、`keep_conn`、`max_idle_conns`、`idle_timeout`（秒）、`params`（附加 CGI 变量）。`try_files` 按顺序检查 root 内的普通文件，PHP 候选交给 PHP-FPM；全部不存在时返回 404。例如 `try_files: ["{path}", "{path}/index.php", "{path}/index.html"]` 可以保留目录首页并关闭根入口回退。

生产 WordPress 站点建议保留示例中的 `deny_scripts`。高并发部署可启用 `keep_conn`；连接复用默认关闭，示例保留最多 16 条空闲连接，60 秒后回收，可按 PHP-FPM worker 数和实际负载调整。

PHP 备份文件以常见后缀识别：`.php~`、`.php.bak`、`.php.old`、`.php.orig`、`.php.backup`、`.php.save`、`.php.swp`、`.php.swo`、`.php.tmp`（不区分大小写），返回 404；隐藏文件仍由静态服务规则拦截。文件名中包含 `.php` 的普通静态资源，例如 `prism.php.min.js`、`syntax.php.css`，可正常访问。这些规则不识别所有可能的备份命名，部署时应将其他备份文件放在网站目录外。

`php` 也能用在路径键或 `routes` 中，与其他动作一样每条路由只能配置一个终结动作。需要从 URL 去掉挂载前缀时，显式设置 `strip_prefix: true`；应用仍需支持该部署前缀。有子路由时，全站根动作的压缩等治理字段放在显式 `/` 路由下。

**禁止上传目录执行脚本**：可在 `php` 下设置 `deny_scripts: [/wp-content/uploads]`。默认不禁止任何目录；设置后，目录内的 PHP 脚本、PATH_INFO 和目录 PHP 首页返回 403，图片等静态资源仍可访问。路径以 `/` 开头，相对于网站 `root`，按目录边界匹配且不区分大小写，`/wp-content/uploads-extra` 不会被误匹配。设置 `strip_prefix` 时，在去掉挂载前缀后检查；站内符号链接解析后的脚本位置也会检查。自定义 `try_files` 选中的脚本同样受此限制。

**负载均衡终止 TLS**：在全局 `config.yaml` 的 `real_ip.trusted_proxies` 配置实际代理的 IP 或 CIDR，例如 `real_ip: {trusted_proxies: ["192.0.2.10/32"]}`（这是全局配置，不写在站点 YAML 中）。

当直接连接来自可信代理且 `X-Forwarded-Proto` 为单一 `https` 值时，PHP 收到 `HTTPS=on`，没有显式 Host 端口时 `SERVER_PORT=443`；`https: true` 也不会把此请求再次重定向。非可信来源、重复或逗号分隔的协议值不被采信。代理应覆盖该请求头为实际客户端协议。该机制也适用于底层 FastCGI proxy 动作。

**子路径映射**：`php` 默认保留完整 URL 路径，`file_server` 默认自动去掉匹配的路由前缀。例如 `/blog` 路由、`root: /var/www` 和请求 `/blog/x`：

| 配置 | 对应物理路径 |
|---|---|
| `php: {root: /var/www, upstream: ...}` | `/var/www/blog/x`（类似 Nginx root） |
| `strip_prefix: true` + `php: {root: /var/www, upstream: ...}` | `/var/www/x` |
| `file_server: /var/www` | `/var/www/x`（类似 Nginx alias） |

PHP 的静态文件与脚本都使用同一映射规则；默认根入口回退 `/index.php` 始终相对于 `root`。PHP 应用挂载子路径时，如需 `/blog/index.php` 作为入口，请显式配置 `try_files`。

### 配置片段 snippets / import

同一个 YAML 文档内，可将公共路由治理写进顶层 `snippets`，用 `import` 在站点或路由位置展开。`import` 接受一个名称或名称列表。片段无参数，不导入文件或 KV；可通过 `sites/_shared.yaml` 跨站点共享；这只是配置复用，不改变中间件、限流或负载均衡的运行时状态作用域。

片段只接受路由治理字段（例如 cors、auth、compress、strip_prefix、use、request_headers、response_headers）；不能定义 site、port、match、routes、终结动作或 services/transports/middlewares 资源。后端仍用 proxy/service，动作在使用位置声明。片段可导入其他片段，循环、未知引用、重复引用和超出展开限制均报错。

合并规则：

- 普通治理字段重复即报错，即使值相同；不深层合并 auth/cors 等对象，也不允许本地静默覆盖。
- request_headers / response_headers 按大小写不敏感的头名合并；本地头值优先，多个同级导入片段声明同名头则报错。
- 同一导入位置的 use 按引用顺序合并并去重。站点与路由的既有继承和重复引用校验规则继续适用。
- 有子路由时，导入 cors/auth 等根路由治理也必须写在显式 `/` 路由下；站点级 use 和响应头可以继承。

原始文件保留 snippets/import 与注释，运行时使用独立的展开结果。错误保留片段定义行号，编译错误补充片段及引用位置。未使用的片段也检查字段、类型、引用和循环；业务语义仍在有效路由上校验。Loader 的 `ExpandSiteV2Document` 提供有效 AST 检视接口。

```yaml
site: localhost
snippets:
  public-api:
    cors:
      allowed_origins: ["*"]
      allowed_methods: [GET, POST, OPTIONS]
      allowed_headers: ["*"]
    response_headers:
      X-Frame-Options: DENY
    compress: true
/goapi:
  import: public-api
  proxy: localhost:9001
/userapi:
  import: public-api
  response_headers:
    X-Service: users
  proxy: localhost:9002
```

### v2 后端与传输

`proxy` 对象和命名 `services` 支持 `to`、`servers`、`discovery`、`resolver`、`timeout`、`retry`、`lb` / `loadbalancer`、`health` / `healthcheck`、`circuitbreaker`。`servers` 是 `to` 的同义词，两者不能同时配置；静态地址与 discovery 互斥。命名引用用 `service`。

`retry: 2` 等价于 `retry: {attempts: 2}`；`health: /health` 等价于 `healthcheck: {path: /health}`；`lb: least_conn` 等价于 `loadbalancer: {strategy: least_conn}`；`discovery: orders` 等价于 `discovery: {name: orders}`。health/healthcheck、lb/loadbalancer 不能同时配置。除这些别名外，对象参数沿用服务标签的层级。

传输在顶层 `transports` 定义，通过后端 `loadbalancer.serverstransport` 引用；后端不支持 `transport` 键。

```yaml
site: shop.example.com
transports:
  mesh:
    tls: {enabled: true, insecureskipverify: false}
services:
  orders:
    to: [https://127.0.0.1:8080]
    timeout: 500ms
    retry: 2
    health: /health
    loadbalancer: {strategy: least_conn, serverstransport: mesh}
/orders:
  service: orders
/api:
  proxy: {to: localhost:8080, timeout: 2s, retry: 2, lb: least_conn, health: /health}
```

### 旧标准字段与 v2 对照

| 旧字段 | v2 写法 |
|---|---|
| domain / force_https | site / https |
| serverstransports / 路由 middlewares | transports / use（字符串或列表） |
| headers / res_headers | request_headers / response_headers |
| enable_tracing | tracing |
| proxy_cache / proxy_cache_ttl / proxy_cache_key | cache: {enabled, ttl, key} |
| 路由 upstream / timeout | proxy: {to, timeout} |
| fastcgi_*、insecure_skip_verify、host、sticky_* 等高级字段 | action: {type: proxy, ...} |
| action: {service: x} | service: x 或 proxy: {service: x}；通用 action 必须显式写 type |

第 1–9 节为旧标准格式与内部模型参考，不能直接将其路由字段复制到 v2。

## 0.1 旧 Lite 写法（继续兼容）

手工将 Lite 改写为 v2 时，如需保留 HTTP→HTTPS 跳转，必须显式写 `https: true`：Lite 缺省 true，v2 缺省 false。已有 Lite 文件无需迁移。

下面保留旧 Lite 示例，供维护现有文件时参考。新配置使用上面的统一 v2 写法。
只需要将文件命名为 `.lite.yaml`（例如 `example.com.lite.yaml`），即可极大地简化配置结构，避免深层嵌套。新建配置不再默认输出此格式。

极简模式的核心思想：**顶层键名即为域名，次级键名为路径（以 `/` 开头）或全局属性。**

### 极简反向代理示例
```yaml
api.example.com:
  /v1:
    proxy: 127.0.0.1:8080
  /v2:
    proxy: 127.0.0.1:8081
```

### 极简 SPA (单页应用) 与静态资源示例
```yaml
docs.example.com:
  /:
    root: /var/www/html
    spa: true
  /images:
    root: /var/www/images
```

### 极简模式支持的 Action
在路由路径下（`/xxx:` 之下），极简模式支持以下快捷指令：
- `proxy`: 反向代理上游地址 (如 `127.0.0.1:8080`)
- `root`: 静态文件根目录路径
- `spa`: 布尔值，当存在 `root` 时，启用单页应用回退路由
- `redirect`: 重定向目标 URL
- `respond`: 直接响应静态文本字符串
- `headers`: 注入请求头 (map)
- `res_headers`: 覆盖响应头 (map)

以下指令**只能写在站点级**（直接挂在域名下）。写进路由会被解析器直接拒绝（`LiteRoute` 以 KnownFields 严格解码）：
- `webdav`: 启用 WebDAV 的根目录路径
- `https`: 布尔值，关闭强制 HTTPS 跳转（默认 true）
- `entrypoints`: 挂载的入口监听器列表

同一路由内动作互斥，只有一个会生效，优先级为 `proxy` > `root` > `respond` > `redirect`。

### 全局级动作
极简模式允许省略 `/`，直接将指令挂在域名下。
```yaml
simple.example.com:
  https: false               # 关闭强制 HTTPS 跳转 (默认 true)
  proxy: 127.0.0.1:3000      # 相当于在 / 下配置 proxy
  headers:
    X-Forwarded-App: legacy  # 仅 proxy 向上游发送；不是安全响应头
```

维护旧 Lite 文件时，其表达范围仍有限；新配置可统一用 v2 的路由治理字段与 action 高级出口。

---

## 1. 根字段 (标准模式)

```yaml
domain: "example.com"          # 必填。站点域名
entrypoints: ["web", "websecure"] # 可选。挂载的全局入口监听器列表（缺省自动挂载至所有可用入口）
port: 0                        # 可选。为该站点单独监听一个端口；0 表示使用全局监听
force_https: true              # 可选。自动将 HTTP 重定向到 HTTPS
connect_override: home         # 可选。仅授权指定 Connect Peer 接管同名精确域名
description: "用户中心"        # 可选。站点描述
disable_trace_id: false        # 可选。禁用 X-Trace-Id 注入

# 可选。自定义付费证书与私钥路径配置（启用后优先使用此证书，不使用全局自动申请证书）
tls:
  enabled: true
  cert_file: "./certs/example.com.crt"
  key_file: "./certs/example.com.key"

defaults:
  timeout: 30                  # 可选。默认超时，单位：秒

ip_restriction:
  allow_ips: ["192.168.0.0/16"]
  deny_ips: []

# 中间件定义（可选）
middlewares:
  limit-10:
    type: "ratelimit"
    config:
      qps: "10"
  strip-api:
    type: "strip_prefix"
    config:
      prefixes: "/api"

routes:
  - name: "default"
    match:
      path_prefix: "/"
    action:
      type: "proxy"
      upstream: ["127.0.0.1:8080"]
```

`connect_override` 用于把现有 Cloud Site 零中断迁移到 LiteGate Connect。它只接受
`connect.server.peers` 中已配置的 Peer 名称，并且只能用于精确 DNS 域名；通配域名会在加载时
拒绝。配置授权后，本地路由会继续工作，直到指定 Peer 注册同名域名；接管后即使 Peer 离线也
保持 fail-closed，不自动回落本地 upstream。

字段说明：

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `domain` | string | 必填。站点域名 |
| `entrypoints` | string[] | 可选。绑定的全局入口监听器名称列表（如 `["web", "websecure"]`）；留空表示挂载至所有入口 |
| `port` | int | 可选。站点独立监听端口 |
| `force_https` | bool | 可选。HTTP 自动跳转 HTTPS |
| `description` | string | 可选。站点描述 |
| `disable_trace_id` | bool | 可选。禁用响应头 `X-Trace-Id` |
| `tls` | object | 可选。自定义付费 TLS 证书配置结构体 |
| `tls.enabled` | bool | 启用自定义证书时必填。是否启用该站点的自定义 TLS 证书配置 |
| `tls.cert_file` | string | 启用自定义证书时必填。付费证书的物理文件路径 (e.g. `./certs/example.crt`) |
| `tls.key_file` | string | 启用自定义证书时必填. 付费私钥的物理文件路径 (e.g. `./certs/example.key`) |

> 说明：启用 `tls` 后，该域名按 SNI 精确匹配并**只**使用此证书，不再回退到全局自动申请；证书缺失/加载失败会导致握手直接失败。证书仅在站点配置重载时加载，续期换证后需重新保存配置。仍需全局已开启 HTTPS 监听才生效。
| `defaults.timeout` | int | 可选。默认超时，单位秒 |
| `ip_restriction` | object | 可选。站点级 IP 白名单 / 黑名单 |
| `middlewares` | map | 可选。中间件定义（类似 Traefik 的 Middlewares） |
| `services` | map | 可选。命名 Service 定义，路由通过 `action.service` 引用（见第 4 节） |
| `serverstransports` | map | 可选。上游传输配置 (TLS / mTLS)，由 Service 引用 |
| `routes` | array | 必填。路由列表 |

---

### Forward 专用站点

Forward 站点不需要 `routes`。每个域名在服务端固定绑定一个内部目标，客户端不能覆盖目标。
Token 至少 32 字节，生产环境推荐 `token_file`。目标可以是专用 L4/SOCKS5 Stream、
本机 L7 Site，或由 Connect 注册的远端服务：

```yaml
domain: forward.example.com
forward:
  target:
    type: stream # stream、site 或 connect
    name: rds-mysql
  token_file: /etc/litegate/secrets/forward.token
```

原有 `stream: rds-mysql` 写法继续兼容，并等价于上面的 `target.type: stream`。
`site` 和 Connect 发布的 L7 Site 会把隧道内每个请求的 Host/SNI 固定到 `target.name`；
一个 Forward Token 不能借内部入口访问其他站点。

`entrypoints` 可以省略；未显式配置全局 Entrypoint 时，LiteGate 仍会根据 `http.https_port` 自动提供 `websecure`。Forward 本身强制 WSS/TLS。只有存在多个入口且需要限制暴露范围时，才配置 `entrypoints: [websecure]`。

公网连接固定使用 `/_litegate/forward/v1` 上的 WSS。域名应由现有 HTTPS 证书覆盖；
例如 `*.example.com` 可以直接覆盖 `forward.example.com`。

## 2. 路由

`routes` 按顺序匹配，但当多条路由出现重叠（例如使用了复杂的 `rule` DSL）时，可以通过配置 `priority` 精确控制匹配顺序。

```yaml
routes:
  - name: "api-v1"
    priority: 100                 # 可选。匹配优先级，数值越大越先匹配
    match:
      path_prefix: "/api/v1"
      method: ["GET", "POST"]
      header:
        X-Env: "staging"
    middlewares: ["limit-10"]      # 引用中间件
    ip_restriction:
      deny_ips: ["1.2.3.4"]
    action:
      type: "proxy"
      upstream: ["127.0.0.1:8080"]
```

### 路由基本字段说明

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `name` | string | 必填。路由唯一标识名称 |
| `priority` | int | 可选。匹配优先级（默认为 `0`。在混合匹配或使用 Rule DSL 时，数值大者优先匹配） |
| `match` | object | 必填。路径与条件匹配块 |
| `middlewares` | string[] | 可选。要挂载的中间件标识列表 |
| `ip_restriction` | object | 可选。本条路由专属的 IP 白/黑名单（覆盖站点级配置） |
| `action` | object | 必填。命中后执行的核心动作类型与配置参数 |

### `match` 匹配块说明

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `path_prefix` | string | 前缀路径匹配，如 `/api` |
| `path` | string | 精确路径匹配，如 `/health` |
| `rule` | string | 表达式规则（Caddy/Traefik 式 DSL），如 `Host("a.com") && PathPrefix("/api")` |
| `method` | string[] | 限制的 HTTP 方法列表，例如 `["GET", "POST"]` |
| `header` | map | 要求必须携带且匹配的 Header 键值对条件 |

### `ip_restriction` 路由过滤说明

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `allow_ips` | string[] | 允许通过本路由访问的 IP 或网段（白名单） |
| `deny_ips` | string[] | 拒绝通过本路由访问的 IP 或网段（黑名单） |

---

## 3. Action 通用字段

所有 `action` 类型都支持以下通用字段：

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `type` | string | 必填。内置支持：`proxy`、`serve`、`respond`、`redirect`、`block`、`list`、`webdav`、`markdown`、`template`、`status` |
| `headers` | map[string]string | 请求头注入（代理场景）或响应头（部分场景） |
| `res_headers` | map[string]string | 覆盖上游响应头 |
| `rate_limit` | float64 | QPS 限流 |
| `rate_limit_policy` | string | `static` 或 `adaptive` |
| `auth` | object | Basic / JWT 认证 |
| `cors` | object | CORS 配置 |
| `waf` | object | WAF 配置 |
| `circuit_breaker` | object | 熔断配置 |
| `ids` | object | IDS Provider 插件决策配置（与 remote_auth 独立） |
| `remote_auth` | object | 远程鉴权 / OIDC 配置 (向下兼容) |
| `route_selector` | map[string]string | 多租户或多维路由选择 |
| `route_tags_header` | string | 显式启用客户端路由标签请求头；未配置时默认头只接受可信 Selector 客户端 |

> [!NOTE]
> 校验器要求：
> - `proxy` 必须提供 `upstream` 或 `service_name`
> - `serve` / `webdav` / `markdown` 必须提供 `root`

---

## 4. Proxy

```yaml
action:
  type: proxy
  namespace: "default"
  upstream_type: static            # 可选。常见值：static / consul / litemesh / external
  upstream: ["127.0.0.1:8080"]
  service_name: "order-api"
  service_tag: "v2"
  host: "backend.internal"
  proto: "http"                    # http / https / ws / wss / fastcgi / grpc
  insecure_skip_verify: false
  strip_prefix: "/api"
  prepend_prefix: "/gateway"
  timeout: 30
  retry: 0
  disable_chunked: false
  lb_policy: round_robin
  prefer_h2: false
  mtls: false
  flush_interval: 0
  
  # 服务治理与可观测参数 (可选)
  gray_weight: 10                  # 灰度权重值 (如 10 表示 10% 流量流入当前路由)
  log_level: "info"                # 单条路由级的特定日志级别覆盖
  enable_tracing: true             # 开启当前代理链路的分布式 Tracing 追踪

  health_check:
    enabled: true
    path: "/health"
    interval: 10s
    timeout: 3s
  route_selector:
    sid: "{head.X-Tenant-ID}"
  route_tags_header: "X-LiteGate-Tags"
```

### 高性能 HTTP/1.1 上游客户端（`upstream_client`）

默认开启，一般无需配置：后端是普通明文 HTTP/1.1（没有 TLS、gRPC、HTTP/2）时，代理使用同步连接池，降低每个请求的 CPU 开销；其他后端自动使用标准客户端。只有需要关闭或强制校验时才写这个字段，站点上的值对该站点所有代理路由生效，路由上的值覆盖站点，改动随站点热重载生效：

```yaml
site: api.example.com
/api:
  proxy: 10.0.0.11:8080, 10.0.0.12:8080
/legacy:
  proxy: 10.0.0.13:8080
  upstream_client: standard     # 关闭：该路由始终用 Go 标准 Transport
/orders:
  proxy: 10.0.0.14:8080
  upstream_client: fast         # 强制：该路由必须能走快速通道，否则加载报错
```

- 默认值与站点级 `fast` 是"能用就用"：`https://`、`grpc`、`prefer_h2`、mTLS/TLS 等路由自动保持标准客户端，不报错。路由上显式写 `fast` 则严格校验，这些配置加载即报错；服务发现的后端运行时才确定协议，不满足时回落并对每个后端记录一次警告日志。
- 全局关闭：`config.yaml` 中 `http.upstream_client: standard`。
- WebSocket 等协议升级照常走隧道，不受影响。
- 少数请求仍会交给标准客户端，以保证与原有行为一致：带 `Expect: 100-continue`、带请求 trailer、请求体长度未知或超过 64KB。
- 确认实际生效：指标 `litegate_upstream_client_requests_total{route, client, fallback}` 按路由统计 `client=fast/standard` 与回落原因；受信任来源带 `X-LiteGate-Debug: true` 请求时，响应头 `X-LiteGate-Upstream-Client` 给出 `fast` 或 `standard; fallback=原因`。

### FastCGI 代理配置示例

对于 PHP-FPM 等 FastCGI 后端服务，可以使用以下配置进行代理转发：

```yaml
action:
  type: proxy
  upstream_type: static
  proto: "fastcgi"                 # 必须指定为 fastcgi
  fastcgi_root: "/var/www/html"    # 仅当 proto 为 fastcgi 时必填，指定 FastCGI 在后端的 Document Root
  fastcgi_split_path: ".php"       # 可选。切分脚本与 PATH_INFO 的后缀，默认为 ".php"
  fastcgi_extensions: [".php"]     # 可选。允许执行的扩展名白名单，默认为 [".php"]。支持 "*" 放行所有，需注意安全隐患
  fastcgi_params:                   # 可选。传给 PHP-FPM 的额外安全 CGI 环境变量
    APP_ENV: production
    REDIRECT_STATUS: "200"
  fastcgi_keep_conn: true          # 可选。是否启用连接复用池，默认为 false
  fastcgi_max_idle_conns: 10       # 可选。连接池中允许保留的最大空闲连接数，默认为 2
  fastcgi_idle_timeout: 60         # 可选。空闲连接超时回收时间（秒），默认 0 表示永不超时
  upstream:
    - "fastcgi://127.0.0.1:9000"   # 支持通过 TCP 端口指定后端
    # 或者使用 Unix Socket 格式：
    # - "unix:///var/run/php-fpm.sock"
```

字段说明：

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `namespace` | string | 可选。上游命名空间 |
| `upstream_type` | string | 上游解析类型 |
| `upstream` | string[] | 静态上游列表 |
| `service_name` | string | 服务发现名称 |
| `service_tag` | string | 服务标签 |
| `host` | string | 覆盖请求 Host |
| `proto` | string | 上游协议 |
| `fastcgi_root` | string | FastCGI 专属。指定后端的 Document Root。当 `proto` 为 `fastcgi` 时必填。 |
| `fastcgi_split_path` | string | FastCGI 专属。指定脚本路径与 Path Info 的切分后缀（如 `.php`）。默认值为 `.php`。 |
| `fastcgi_extensions` | string[] | FastCGI 专属。允许通过 FastCGI 执行的脚本扩展名白名单（如 `[".php"]`）。默认值为 `[".php"]`。可以设置为 `["*"]` 允许任何扩展名，但如果后端 PHP-FPM 配置不当，可能会导致任意文件执行等安全风险。 |
| `fastcgi_params` | map[string]string | FastCGI 专属。追加 `APP_ENV`、`REDIRECT_STATUS` 等 CGI 环境变量；不能覆盖路径、请求及 `HTTP_*` 内置变量。 |
| `fastcgi_keep_conn` | bool | FastCGI 专属。是否启用与后端的连接池复用，默认值为 `false`。 |
| `fastcgi_max_idle_conns` | int | FastCGI 专属。连接池中最大的空闲连接数（默认为 `2`，不能为负数）。 |
| `fastcgi_idle_timeout` | int | FastCGI 专属。空闲连接的超时回收期限（秒，默认 `0` 表示不超时回收，不能为负数）。 |
| `insecure_skip_verify` | bool | 跳过 TLS 校验。注意：在 `mtls: true` 模式下，即使此字段设为 `true`，系统仍将强制执行服务端证书链与 SPIFFE 身份强校验（仅输出 Warn 安全警示日志，无法彻底绕过），以防止零信任安全漏洞。 |
| `strip_prefix` | string | 转发前移除路径前缀 |
| `prepend_prefix` | string | 转发前附加路径前缀 |
| `timeout` | int | 超时，单位秒 |
| `retry` | int | 重试次数，不能为负数；非幂等请求仅在确认请求尚未发送时重试 |
| `retry_on_status` | int[] | 可选。触发故障转移与重试的上游 HTTP 状态码列表（如 `[502, 503, 504]`） |
| `retry_methods` | string[] | 可选。允许触发重试的 HTTP 方法列表（如 `["GET", "HEAD"]`，默认仅允许幂等方法） |
| `passive_failure_status` | int[] | 可选。计入被动熔断健康度与异常节点剔除的状态码列表（如 `[500, 502, 503, 504]`） |
| `xff_mode` | string | 可选。X-Forwarded-For 传递模式：`transparent` (完全透传) 或 `boundary` (边界清洗) |
| `disable_chunked` | bool | 禁用 chunked 传输；缓冲请求体计算长度，超过 2 MiB 返回 413 |
| `lb_policy` | string | 负载均衡策略。支持 `round_robin` (轮询)、`ip_hash` (源IP哈希)、`weighted_round_robin` (权重轮询)、`p2c` (结合活跃请求数与延迟的双随机选择)、`least_conn` (最少连接数)、`cookie` (会话保持) |
| `prefer_h2` | bool | 优先 HTTP/2 |
| `upstream_client` | string | 默认跟随全局 `http.upstream_client`（默认 `fast`：明文 HTTP/1.1 后端走同步连接池，其他自动用标准客户端）；`standard` 关闭；路由上写 `fast` 为严格模式。见下文 |
| `mtls` | bool | 启用 mTLS |
| `flush_interval` | int | 刷新间隔；`-1` 表示即时刷新 |
| `gray_weight` | int | 可选。当前灰度发布的流量占比权重 (0 - 100) |
| `log_level` | string | 可选。该路由的访问日志级别覆盖 (`none` / `error` / `warn` / `info` / `debug`)，对所有 action 类型生效 |
| `enable_tracing` | bool | 可选。该路由的边缘 Span 必定采样上报（不受 `sample_ratio` 影响），需全局 `tracing.enabled` |
| `health_check` | object | 健康检查配置 |

### 缓存、重写、会话保持、并发限制与 gRPC（新增能力）

以下字段均配置在 proxy 路由的 `action` 上：

```yaml
action:
  type: proxy
  upstream: ["127.0.0.1:8080"]

  # 反向代理内容缓存
  proxy_cache: true
  proxy_cache_ttl: 30              # 缓存秒数，默认 10；同时尊重上游 Cache-Control 取更短值
  proxy_cache_key: "{host}:{uri}:{header.Accept-Language}"  # 可选；{uri} 含查询串，{path} 不含

  # URL 正则重写（在鉴权 / WAF / 限流之前执行）
  rewrite:
    pattern: "^/old/(.*)$"
    target: "/new/$1"

  # Cookie 会话保持
  lb_policy: cookie                # 其它可选：round_robin / ip_hash / weighted_round_robin / p2c / least_conn
  sticky_cookie_name: "LG_STICKY_BACKEND"   # 可选，默认即此
  sticky_cookie_ttl: 1800                    # 可选，秒，默认 1800

  # 并发连接限制
  limit_conn: 100
  limit_conn_key: "ip"            # "ip" 按客户端 IP；留空按路由全局

  # gRPC 一等公民：proto: grpc（明文 h2c；配合 mtls:true 自动升级为 grpcs / TLS）
  proto: grpc
```

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `proxy_cache` | bool | 开启内容缓存。带 `Authorization`/`Cookie` 请求、`Set-Cookie`/`private` 响应、未知 `Vary` 维度、非 GET/HEAD、WS/gRPC/SSE 会自动绕过 |
| `proxy_cache_ttl` | int | 缓存秒数，默认 10 |
| `proxy_cache_key` | string | 自定义缓存 Key 模板，支持 `{host}`/`{uri}`（含查询串）/`{path}`/`{method}`/`{header.X}` |
| `rewrite.pattern` / `rewrite.target` | string | Go 正则重写 `URL.Path`，`$1` 引用捕获组；不会重新触发路由匹配 |
| `lb_policy: cookie` | string | Cookie 会话保持，Cookie 经 AES-GCM 加密、HttpOnly、HTTPS 下 Secure |
| `sticky_cookie_name` | string | 粘连 Cookie 名，默认 `LG_STICKY_BACKEND` |
| `sticky_cookie_ttl` | int | 粘连 Cookie 有效期（秒），默认 1800 |
| `limit_conn` | int | 最大并发在途请求数，超限返回 503 + Retry-After |
| `limit_conn_key` | string | `ip` 按客户端 IP；留空按路由全局 |
| `proto: grpc` | string | gRPC 一等公民代理，自动 HTTP/2 + trailer 透传；`mtls:true` 时升级为 grpcs |

> 全局相关（config.yaml）：多节点 Cookie 会话保持需配 `sticky_key`（32 字节 hex 共享密钥）；`cache.proxy_cache_max_entries` 控制缓存条目上限。

---

### 新旧服务并行迁移（MCP/AI 必须遵守）

`rewrite` 不等价于 Nginx `rewrite ... last`：它只修改已命中 route 中发送给上游的路径，不会再次匹配其他 route，也不能用来切换 upstream。

当用户要求“老服务不停，按 query/header 把部分流量迁到新服务”时，AI 必须生成两条 proxy route：高优先级条件 route 直接指向新服务，低优先级兜底 route 保留老服务。不得声称 rewrite 会跳转到新 route。

```yaml
routes:
  - name: oauth-new
    priority: 100
    match:
      path: "/oauthcallback"
      rule: 'Query("state", "optional_state_id")'
    action:
      type: proxy
      upstream: ["new-oauth-service:8080"]
      rewrite:
        pattern: "^/oauthcallback$"
        target: "/new_oauthcallback"

  - name: oauth-old
    priority: 10
    match:
      path: "/oauthcallback"
    action:
      type: proxy
      upstream: ["old-oauth-service:8080"]
```

MCP 操作顺序：先用 `get_site_config` 读取并保留现有配置，再用 `validate_site_config` 校验完整 YAML，最后才能调用 `save_site_config`。不得使用只能生成单 route 的 `create_proxy_site` 修改此类站点。保存后应至少调用两次 `lookup_route`，分别验证条件命中与兜底流量。

### 纯 API 后端的写后动作 (`on_success`)

当页面由 LiteGate `template` 渲染、业务后端只提供 JSON API 时，可以把缓存失效和 HTMX 协议留在网关配置中：

```yaml
- name: create-todo
  match:
    path: "/api/todos"
    method: ["POST"]
  action:
    type: proxy
    upstream_type: static
    upstream: ["127.0.0.1:9000"]
    on_success:
      invalidate_cache: ["todos"]
      htmx_trigger: ["todos-changed"]
      discard_body: true
```

成功严格指 `200` 到 `299`。`3xx`、`4xx`、`5xx` 不执行这些动作，错误响应体仍会返回客户端。`htmx_trigger` 会覆盖上游同名响应头；`invalidate_cache` 对应 `fetch_json.cache_tags`。YAML 路由匹配字段名是 `method`，JSON 表示中为 `methods`。

模板可以来自 `template_root` 指向的目录文件，也可以开启 `template_kv_mode` 从 litemesh/Consul KV 加载；`on_success` 与模板存储方式无关。

### 引用命名 Service（旧标准格式：`services` / `serverstransports`）

把“怎么到达后端”定义为站点级的命名 Service，多条路由通过 `action.service` 引用。
键名与服务发现标签 `litegate.http.services.<name>.*`、`litegate.http.serverstransports.<name>.*` 一致，校验规则也相同。

```yaml
serverstransports:
  mesh:
    tls:
      enabled: true
      clientcertificate: litemesh    # 使用 Litemesh 身份做双向 TLS
      insecureskipverify: false

services:
  orders:
    discovery:
      name: orders                   # 服务发现中的服务名；与 servers 二选一
      selector:
        match: { version: v2 }       # 硬边界：只选 metadata 匹配的实例
        meta: { zone: a }            # 软偏好：优先命中，无命中时回退
    timeout: 5s                      # 单个请求端到端超时，支持 500ms 等写法
    loadbalancer:
      strategy: least_conn
      server: { port: 8080, scheme: https }
      serverstransport: mesh
    healthcheck: { path: /health, interval: 10s }
    retry: { attempts: 2 }
    circuitbreaker: { enabled: true, timeout: 60, maxrequests: 1, tripthreshold: 3 }

  legacy:
    servers: ["http://10.0.0.1:8080", "http://10.0.0.2:8080"]   # 静态后端

routes:
  - match: { path_prefix: /orders }
    action: { type: proxy, service: orders }
  - match: { path_prefix: /v2/orders }
    action: { service: orders }        # 省略 type 时即为 proxy
```

规则：

*   引用了 `service` 的路由不能再内联上游字段（`service_name`、`upstream`、`lb_policy`、`timeout`、`retry`、`circuit_breaker`、`health_check`、`route_selector`、`route_meta`、`service_port`、`proto`、`insecure_skip_verify`、`mtls`），否则加载失败。一条路由的后端只有一个配置来源。
*   `discovery.name` 与 `servers` 必须且只能配置一个；`selector` 只能与 `discovery` 一起使用。
*   引用同一个 Service 的路由共享健康状态与熔断状态；通过服务发现的 Service 还共享负载均衡器，静态 `servers` 由每条路由各自维护轮询计数。
*   内联写法（直接在 `action` 中写 `service_name`、`timeout` 等）继续有效，与引用 Service 的效果相同。
*   `retry`、`circuit_breaker` 中间件类型已弃用，请改用 Service 的 `retry` / `circuitbreaker`。

## 5. 静态文件与目录类 Action

### `serve`

```yaml
action:
  type: serve
  root: "/var/www/html"
  index: "index.html"
  file: ""
  not_found_file: "404.html"
  spa: true
  compress: true
  cache_control: "public, max-age=3600"
  try_files: ["{path}", "/index.php"]   # 可选。按候选物理文件回退；最后一项以 / 开头则作为 fallback 内部重定向（最多 5 次防环路）。适合 PHP 前端控制器
  
  # --- Serve KV 动态自动部署模式 (可选) ---
  kv_mode: true                    # 启用静态 ZIP 自动同步热部署功能
  kv_provider: "litemesh"          # 驱动提供商: litemesh, consul, http
  kv_key: "litegate/config/main"   # 监听的键名。如果是 http 则是完整接口 URL
  keep_versions: 3                 # 本地最多保留的历史版本包数量 (默认 3)
```

### `webdav`

```yaml
action:
  type: webdav
  root: "/data/shared"
  web_ui: true
  read_only: false
  direct_download: true            # 可选。允许文件直链下载（跳过网页播放器或直接作为附件下载）
  allow_browse: true               # 可选。是否允许游客免登录在 WebUI 中浏览目录（配合 auth 使用）
```

### `markdown`

```yaml
action:
  type: markdown
  root: "./docs"
  index: "README.md"
  render_markdown: true
  title: "项目文档"
  show_hidden: false
```

说明：

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `root` | string | 必填。根目录 |
| `index` | string | 默认首页 |
| `file` | string | 指定固定文件 |
| `not_found_file` | string | 自定义 404 文件 |
| `spa` | bool | SPA 回退到 `index.html` |
| `compress` | bool | 启用压缩 |
| `cache_control` | string | 缓存控制头 |
| `try_files` | string[] | serve 专属。按候选文件回退；最后一项以 `/` 开头作为 fallback 内部重定向（最多 5 次防环路） |
| `kv_mode` | bool | 是否启用前端静态 ZIP 的 KV/HTTP 自动托管拉取模式 |
| `kv_provider` | string | 版本驱动提供商，可填 `litemesh`, `consul`, `http` |
| `kv_key` | string | 监听的 KV 键名或 API 完整 URL |
| `keep_versions` | int | 各节点本地最多保留的历史版本包目录数 (默认 3) |
| `web_ui` | bool | WebDAV 文件管理界面 |
| `read_only` | bool | WebDAV 只读 |
| `direct_download` | bool | WebDAV 专属。允许文件直接下载模式（跳过预览器或支持未登录直链下载） |
| `allow_browse` | bool | WebDAV 专属。是否允许匿名用户通过 WebUI 浏览目录 |
| `title` | string | 列表 / markdown 页面标题 |
| `show_hidden` | bool | 显示隐藏文件 |
| `render_markdown` | bool | 启用 markdown 渲染 |

### `template`

服务端模板渲染（主模板或局部片段采用 `html/template` 进行上下文敏感的 XSS 自动转义防御）。

```yaml
action:
  type: template
  template: "./site/pages/index.html"   # 主模板文件（若启用 KV 模式，为 KV 存储中的主模板 Key 名称）；或用 body 内联
  template_root: "./site"               # 可选。片段扫描根目录，主模板可 {{ template "partials/header.html" . }} 复用片段（仅在 template_kv_mode 为 false 时有效）
  body: ""                              # 内联模板字符串（与 template 二选一）
  status: 200
  content_type: "text/html; charset=utf-8"
  headers: {}

  # --- Template KV 动态自动部署模式 (可选) ---
  template_kv_mode: true                # 是否启用 KV 存储加载模板文件
  template_kv_provider: "litemesh"      # KV 驱动提供商，可填 litemesh, consul
  template_kv_prefix: "litegate/templates/" # 监听并读取模板文件的 KV 键前缀
  template_kv_namespace: "default"      # 可选。Litemesh 专属命名空间

  # 后端 JSON API 实时并发拉取（合并到模版 .Data 里）
  fetch_json:
    - key: "weather"                      # 合并后的键名，模板中通过 {{ .Data.weather }} 访问
      url: "http://api.weather.local/v1"  # 实时获取的 JSON 接口地址（支持 {{.Path}} 等请求上下文参数渲染）
      ttl: 60                             # 缓存生存期，单位：秒
      timeout: 5                          # 请求超时，单位：秒
      allow_private: false                # 是否允许发起私网/内网 IP 访问（SSRF 物理防绕过）
      max_body_size: 2097152              # 允许的最大 Body 大小，默认 2MB
      fail_policy: "ignore"               # 接口调用失败策略："ignore" (忽略并返回空) 或 "error" (直接报错 500)
      forward_headers: ["Authorization"]  # 透传到后端接口的客户端请求头列表
```

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `template` | string | 主模板文件路径（与 `body` 二选一，优先 `template`；若启用 KV 模式，为 KV 存储中的主模板 Key 名称） |
| `template_root` | string | 可选。片段扫描根目录，用于多文件组合复用 |
| `body` | string | 内联模板字符串 |
| `status` | int | 响应状态码，默认 200 |
| `content_type` | string | 默认 `text/html; charset=utf-8` |
| `headers` | map | 额外响应头 |
| `template_kv_mode` | bool | 是否启用静态模板的 KV 自动拉取与热更新模式 |
| `template_kv_provider` | string | 版本驱动提供商，可填 `litemesh`, `consul` |
| `template_kv_prefix` | string | 监听并读取模板文件的 KV 键前缀 |
| `template_kv_namespace` | string | 可选。命名空间（litemesh 专属） |
| `fetch_json` | array | 实时并发拉取的后端 JSON 接口列表 |
| `fetch_json[].key` | string | 数据合并在 `.Data` 下的键名，例如 `weather` |
| `fetch_json[].url` | string | 目标 JSON API 的 URL 模板（内含 `{{ ... }}` 的参数使用 `text/template` 渲染以防转义） |
| `fetch_json[].ttl` | int | 数据在网关本地的成功/失败缓存时长，单位秒 |
| `fetch_json[].timeout` | int | 后端接口请求超时时间，单位秒（默认 5s） |
| `fetch_json[].allow_private` | bool | 是否允许访问私网 IP。默认 `false`，强力抵御 SSRF 和 DNS 重新绑定（DNS Rebinding） |
| `fetch_json[].max_body_size` | int64 | 后端响应内容大小限额，单位字节（默认 2MB） |
| `fetch_json[].fail_policy` | string | `ignore`（忽略错误并在模版中通过 `.Errors.key` 获取错误）或 `error`（立即响应 500 异常） |
| `fetch_json[].forward_headers` | string[] | 指定转发透传的客户端 Header 键，其值将参与缓存 Key 生成（生成时已做大小写敏感标准化） |

> 模板内可用变量/方法：`{{ .Host }}`、`{{ .Path }}`、`{{ .Method }}`、`{{ .ClientIP }}`、`{{ .Time }}`、`{{ .Header "K" }}`、`{{ .Query "k" }}`、`{{ .Cookie "n" }}`、`{{ .Nonce }}`。
> 模板内内置渲染函数：
> - `{{ htmx }}`：渲染嵌入的 HTMX 脚本标签 `<script src="/_litegate/assets/htmx-4.0.0.min.js"></script>`（免手动下载）。
> - `{{ markdown "## Content" }}`：将 Markdown 文本实时转换为安全 HTML。
> - `{{ safeHTML "<div>" }}`：声明信任的 HTML 片段。
> - `{{ lower "ABC" }}` / `{{ upper "abc" }}` / `{{ contains "a" "b" }}` / `{{ replace "a" "b" "c" }}` / `{{ substr "abc" 0 2 }}`：常用的字符串操作。
> - `{{ env "APP_ENV" }}`：读取安全环境变量白名单内的值。
> - `{{ formatTime .Time "2006-01-02" }}` / `{{ formatDateTime .Time "2006-01-02" }}`：进行 RFC3339 或常用时间格式转换。

> [!WARNING]
> **分布式模板的安全与功能边界 (KV 模式)**
> 1. **Markdown 文件加载失效**：在 `template_kv_mode` 启用时，由于不存在真实的本地模板目录（`realTemplateRoot` 为空），内置的 `{{markdown "x.md"}}` 引用外部物理文件功能将失效，仅能渲染内联的 Markdown 文本（如 `{{markdown "## 文本"}}`）。
> 2. **禁用通用 `namespace` 字段**：`template` 与 `status` 动作在校验时严禁包含 `namespace` 根字段，如果需要进行租户/KV 命名空间隔离，必须显式声明为 `template_kv_namespace`。
> 2. **安全风险 - 等同于部署代码权限**：拥有目标 KV 前缀（`template_kv_prefix`）的写入权限，等同于能够通过 `safeHTML` 等机制向网关注入并执行任意 HTML/模板代码。因此，请务必锁紧该 KV 目录所对应的命名空间（namespace）和读写 Token 权限。

### HTMX 与后端 API (Fetch JSON) 结合示例

```yaml
domain: "dashboard.example.com"
routes:
  - name: "realtime-dashboard"
    match:
      path_prefix: "/"
    action:
      type: "template"
      template: "./pages/dashboard.html"
      fetch_json:
        - key: "metrics"
          url: "http://metrics-service.internal:8000/api/v1/stats?domain={{.Host}}"
          allow_private: true  # 允许访问内部监控服务
          ttl: 5               # 快速刷新缓存
          fail_policy: "ignore"
```

在主模板文件 `./pages/dashboard.html` 中编写：
```html
<!DOCTYPE html>
<html>
<head>
    <title>Dashboard</title>
    <!-- 自动引入内建的 HTMX 脚本 -->
    {{ htmx }}
</head>
<body>
    <h1>System Status for {{ .Host }}</h1>
    
    <!-- 渲染并发获取的 JSON 数据 -->
    <div id="stats">
        <p>Active Users: {{ .Data.metrics.active_users }}</p>
        <p>Total Requests: {{ .Data.metrics.total_reqs }}</p>
    </div>

    <!-- 借由 HTMX 快速进行动态局部刷新 -->
    <button hx-get="/stats-partial" hx-target="#stats">Refresh Stats</button>
</body>
</html>
```

### `status`

系统状态仪表盘页面渲染。会自动收集网关内所有的 site 和代理路由的流量、QPS、延迟等 live 指标及历史健康状况。

```yaml
action:
  type: status
  title: "服务状态监控"                  # 可选。状态页面的大标题，默认 "LiteGate System Status"
  host: "self"                          # 可选。配置为 "self" 仅展示当前被访问域名（站点）的数据；留空（默认）展示全局所有站点
  template: "./site/pages/status.html"   # 可选。自定义状态页面的模板路径（与 template 场景用法相同）
  template_root: "./site"               # 可选。片段扫描根目录
  template_debug: false                 # 可选。开启调试模式（不缓存模板）
  template_production: true             # 可选。开启生产模式（缓存模板）
  show_instances: false                 # 可选。是否在代理路由监控中展示具体的后端物理服务实例列表 (默认 false)

  # --- Template KV 动态自动部署模式 (可选) ---
  template_kv_mode: true                # 是否启用 KV 存储加载状态面板模板文件
  template_kv_provider: "litemesh"      # KV 驱动提供商，可填 litemesh, consul
  template_kv_prefix: "litegate/templates/" # 监听并读取状态面板模板文件的 KV 键前缀
  template_kv_namespace: "default"      # 可选。Litemesh 专属命名空间
```

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `title` | string | 可选。自定义状态页面顶部展示的系统大标题 |
| `host` | string | 可选。配置要展示的站点。设为 `self` 仅展示当前被访问域名的健康指标（多租户安全隔离）；也可配置具体域名；留空（默认）展示网关所有站点的全局监控 |
| `template` | string | 可选。自定义状态页面模板文件路径，若留空则展示网关内置的高级状态监控仪表盘 |
| `template_root` | string | 可选。片段扫描根目录，用于模板组合复用 |
| `template_debug` | bool | 可选。是否开启模板调试模式 |
| `template_production` | bool | 可选。是否开启模板缓存 |
| `show_instances` | bool | 可选。是否在代理路由监控下渲染展示底层的物理服务实例节点详情 (默认 false) |
| `template_kv_mode` | bool | 可选。是否启用状态面板模板文件的 KV 自动拉取与热更新模式 |
| `template_kv_provider` | string | 可选。版本驱动提供商，可填 `litemesh`, `consul` |
| `template_kv_prefix` | string | 可选。监听并读取状态面板模板文件的 KV 键前缀 |
| `template_kv_namespace` | string | 可选。命名空间（litemesh 专属） |

> 状态页面默认不仅提供极美观的 Web Dashboard (HTML)，如果请求带有 `?format=json` 或 `Accept: application/json` 请求头，还会自动返回全部指标的结构化 JSON 数据，方便第三方系统抓取。

---

## 6. `respond` 与 `redirect`

### `respond`

```yaml
action:
  type: respond
  status: 200
  body: "Hello, LiteGate!"
  content_type: "text/plain; charset=utf-8"
```

### `redirect`

```yaml
action:
  type: redirect
  location: "https://new-site.com{path}"
  status: 301
```

---

## 7. 中间件配置

### `cors`

```yaml
cors:
  allowed_origins: ["https://app.example.com"]
  allowed_methods: ["GET", "POST", "PUT", "DELETE"]
  allowed_headers: ["Authorization", "Content-Type"]
  exposed_headers: ["X-Request-ID"]
  allow_credentials: true
  max_age: 3600
```

`allow_credentials: true` 必须配合明确列出的 `allowed_origins`，与 `*`（或 `enabled: true` 且未填写来源）同时使用会在加载时报错。

### `auth`

```yaml
auth:
  type: basic
  realm: "LiteGate"
  users:
    admin: "<sha256>"
  permissions:
    admin: "rw"
  secret: ""
  sso_enabled: false
  allow_anonymous: false
  jwks_url: ""
  issuer: ""
  audience: []
```

### `waf`

```yaml
waf:
  enabled: true
  block_mode: true
  sensitivity: "medium"
```

### `circuit_breaker`

```yaml
circuit_breaker:
  enabled: true
  timeout: 60
  max_requests: 1
  trip_threshold: 3
```

---

## 8. IDS Provider (`ids`) 与 OIDC (`remote_auth`)

`ids` 是插件决策入口，`remote_auth` 是 OIDC / OAuth2 登录配置，两者不是别名。“大一统控制引擎”的旧说明不再适用于当前配置。内核不内置 MD5、Redis 会话、`login_steering` 或 `token_steering` 业务规则。

V2 路由写法（`company-ids` 为需自行注册的插件名称）：

```yaml
site: api.example.com
/api:
  proxy: localhost:8080
  ids:
    provider: company-ids
    fail_policy: deny
    selector_merge_policy: intersect
    options:
      policy_ref: order-read
    header_projection:
      allowed_headers: [X-Tenant-Ref]
```

| `ids` 字段 | 作用 |
|---|---|
| `provider` | 必填，已注册的 IDS Provider 插件名称，不是 `auth_providers` 名称 |
| `fail_policy` | 默认 `deny`；`allow` 不覆盖插件明确拒绝，宿主超时和 panic 仍拒绝 |
| `selector_merge_policy` | 默认 `intersect`；合并静态和插件发现筛选条件 |
| `runtime` | 宿主控制的 timeout、slow_threshold、max_concurrency、circuit_breaker |
| `options` | 插件定义的字符串参数，不是内核内置业务规则 |
| `header_projection` | `allowed_headers` 控制可注入下游的可信 Header |

IDS 在动作前执行，适用于 proxy、respond、serve 等动作。只有 proxy 消费发现实例筛选决策；插件不能替换路由选定的 Service。默认入口已内置注册 `openapi-md5`；升级到包含该插件的二进制即可使用。开发和运行时细节见 [IDS Provider 指南](../../ids-provider-plugin-guide.md)。

`remote_auth` 使用全局 `auth_providers` 中的 OIDC / OAuth2 Provider，支持 `enabled`、`provider`、`callback_path`、`enforce`、`inject_claims`、`default_redirect_back` 和 `fail_policy`。保留的 `sign_method` 字段不能作为 MD5 插件已内置的依据。

旧示例中的 `ids.enabled`、`url`、`sign_method`、`static_secret`、`lookup` 和会话参数不属于当前 IDS 配置，不能直接沿用；需要在插件中实现对应业务并定义 `options`。

---

## 9. 规则表达式 (Rule DSL) 参考

`match.rule` 支持强大的布尔逻辑和多种谓词函数：

- `Host("domain")`: 匹配域名（自动忽略端口）。
- `Path("/path")`: 精确路径匹配。
- `PathPrefix("/prefix")`: 前缀匹配。
- `PathRegex("^/api/.*$")`: 正则路径匹配。
- `Method("GET")`: HTTP 方法匹配。
- `Header("Key")` 或 `Header("Key", "Value")`: 请求头存在性或值匹配。
- `HeaderRegexp("Key", "Pattern")`: 请求头正则匹配。
- `Query("Key")` 或 `Query("Key", "Value")`: 查询参数存在性或值匹配。
- `QueryRegex("Key", "Pattern")`: 查询参数正则匹配。
- `Cookie("Name")` 或 `Cookie("Name", "Value")`: Cookie 存在性或值匹配。
- `CookieRegex("Name", "Pattern")`: Cookie 正则匹配。
- `CookiePrefix("Name", "Prefix")` / `CookieSuffix("Name", "Suffix")`: Cookie 前缀/后缀匹配（亦支持 `CookieIPrefix`/`CookieISuffix` 忽略大小写匹配）。
- `ClientIP("10.0.0.0/8")`: 客户端真实 IP 或 CIDR 网段匹配。

逻辑运算符：`&&` (与), `||` (或), `!` (非), `()` (优先级)。

示例：
```yaml
match:
  rule: 'Host("api.example.com") && (Cookie("env", "canary") || Header("X-Beta"))'
```

---

## 响应头删除、客户端 IP 限流与站点 TLS 策略

```yaml
site: api.example.com
response_headers:
  "-Server": ""
  "-X-Powered-By": ""
  X-Gateway: LiteGate
tls:
  min_version: "1.2"
  max_version: "1.3"
  client_auth: require
  client_ca_file: ./certs/client-ca.pem
/api:
  rate_limit: {rate: 10, key: ip}
  proxy: localhost:8080
```

响应头名称前加 `-` 表示在响应提交时删除上游返回的字段，值必须为空字符串。普通名称配空字符串仍表示设置空值。站点配置会继承到路由，路由可覆盖同名字段；同一层不能同时设置和删除同一字段。旧式 `res_headers` 也支持删除。

`rate_limit: 10` 保持按站点和路由共享额度；`rate_limit: {rate: 10, key: ip}` 按客户端 IP 分配独立额度，`key: route` 表示共享。旧式 action 可写 `rate_limit: 10` 和 `rate_limit_key: ip`；命名 `ratelimit` 中间件可写 `config: {qps: "10", key: ip}`。单位为每秒请求数，沿用令牌桶突发额度。IP 使用网关已经解析的客户端地址，转发头只在全局 `trusted_proxies` 信任范围内生效；配置 Redis 时 IP 额度也使用分布式限流。

TLS 策略独立于手动证书的 `enabled` 开关，可与自动证书共用。`min_version` 默认 `1.2`，`max_version` 未设置时不限制最高版本；两者只接受 `1.2`、`1.3`。HTTP/3 始终至少使用 TLS 1.3，限制最高版本为 1.2 的站点不能使用 HTTP/3。

`client_auth` 支持 `none`（默认）、`optional`（有证书时验证）、`require`（必须有可信证书）。后两者必须配置本地 PEM 格式的 `client_ca_file`。普通 HTTP 请求无法通过启用了客户端认证的站点。策略在 SNI 握手时应用，并在每个请求中按目标站点重新检查，避免跨 Host 或复用旧连接绕过认证。修改 CA 文件后需重载站点配置。

可选 `cipher_suites` 是 TLS 1.2 密码套件名称列表，例如 `[TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256, TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256]`；仅接受 Go 的安全套件列表。TLS 1.3 密码套件不允许自定义。



### 客户端证书吊销列表（CRL）与连接缓存

```yaml
tls:
  client_auth: require
  client_ca_file: ./certs/client-ca.pem
  client_crl_file: ./certs/client.crl.pem
```

`client_crl_file` 接受本地 PEM CRL 文件（`X509 CRL`，可包含多个列表）或单个 DER CRL。它必须与 `client_auth: optional / require` 一起使用。配置了 CRL 后，每条受信证书链中的叶证书和中间证书都必须有对应签发者的完整 CRL；缺失、已过期、尚未生效、签名错误或证书已被吊销时拒绝访问。签名按真实签发者校验；同一签发者的多个完整 CRL 优先使用编号最高的列表。暂不支持增量 CRL、间接 CRL 或按分发点裁剪的 CRL。若 CA 文件把中间证书作为信任锚，还需在该文件中包含其签发者链直到自签名根，以完整检查中间证书的吊销状态。

TLS 握手（包括会话恢复）会检查 CRL。HTTP/1、HTTP/2、HTTP/3 请求复用连接上的验证结果；握手已经验证且受当前站点 CA 信任的证书链不会重复做密码学链校验。缓存按连接及当前站点策略隔离，最多保留一个成功结果，有效期不超过证书链和 CRL 的最早到期时间。更换站点、CA 或 CRL 配置会重新验证，已有 keep-alive 连接也不能绕过更新后的吊销策略。

更新 CA / CRL 文件后需要重载站点配置；不会自动下载吊销列表。重载失败会保留原来的有效配置；原 CRL 到期后继续拒绝访问，不能依靠过期列表放行。

## 10. 最小示例（v2）

```yaml
site: api.example.com
proxy: 127.0.0.1:8080
```

```yaml
site: docs.example.com
spa: ./public
```

### 命名请求条件（matchers）

站点级 `matchers` 定义可复用条件，路由用 `match: "@name"` 引用。`@name` 是引用，不是表达式；YAML 中必须加引号。名称以字母或下划线开头，后续允许字母、数字、下划线和连字符。引用仅在本站点有效；未定义引用、重复名称、空条件和未知字段会报错，未使用的定义也会校验。matcher 定义可以写成列表来组合其他 matcher（见下文组合条件），循环引用会报错。

```yaml
site: example.com
matchers:
  blocked: { path: [/xmlrpc.php, "*.sql"] }
  post: { method: POST }
routes:
  - match: "@blocked"
    respond: { status: 403 }
  - match: "@post"
    proxy: localhost:6001
proxy: localhost:8080
```

命名和内联 `match` 使用相同语义：不同条件之间为 AND，路径列表内为 OR。`path` 单个普通字符串精确匹配；列表支持精确路径与 `*` 通配符，`*` 匹配零个或多个字符（包括 `/`），匹配整个请求路径且区分大小写，不包含查询参数。只有 `*` 是通配符，`?`、`[]` 为普通字符；以 `*` 开头的 YAML 字符串需要加引号。`method` 支持单个字符串或列表。复杂表达式继续使用 `rule`，与其他条件之间为 AND。

命名 matcher 只复用条件，不改变路由优先级：按下述条件优先级排序，根级 `proxy` 是兜底。`blocked` 示例是一条拒绝路由，不是业务路由前统一执行的安全策略。共享鉴权、压缩等治理配置继续使用 snippets。

命名条件的排序规则：首先比较显式 `priority`（数值越大越优先）；同优先级下依次为精确路径、没有 `path`/`prefix` 的条件路由（rule、method、header、query）、前缀路由。前缀仍按长度排序，根 `/` 保持兜底；同等条件保持已有来源优先规则及声明顺序。单元素精确路径列表与单个路径字符串具有相同优先级。因而 `@blocked` 的 `*.sql` 和仅 method 的 `@post` 会先于 `/api` 前缀路由匹配；精确路径仍更优先，需要覆盖它时显式设置更高 priority。

路径匹配区分大小写，例如 `/xmlrpc.php` 不匹配 `/XMLRPC.PHP`。安全拦截需要覆盖大小写时，可使用 `rule` 中的 `PathRegexp` 与 `(?i)`。`match` 可以写成列表，表示各项同时满足：每项是 `"@name"`、内联条件或 `/前缀` 简写，例如 `match: ["@api", {method: POST}]`。合并时 `rule` 以 AND 连接，`header`/`query` 合并且同一键不能重复（header 不区分大小写）；`prefix`、`path`、`method` 等其他字段只能由一项提供，值相同可以重复，值不同报错。列表不能嵌套。

站点内两条路由具有相同的归一化条件会报重复；要让多条路由复用同一个 matcher，用列表为每条路由追加不同条件。路由排序变更同样影响旧标准 YAML、Lite、纯服务标签和合并站点；旧重叠路由如需维持原行为，应显式设置 priority。

### 多域名、通配站点与重定向占位符

```yaml
site: a.example.com, b.example.com
proxy: localhost:8080
```

逗号分隔的 v2 site 地址展开为独立站点，共用配置，每个地址可自带端口。空地址和重复站点会报错，域名会转小写并去掉末尾的点。MCP 的单站点鉴权快捷编辑不支持这种多站点配置，请使用完整 YAML 编辑与校验。

```yaml
site: "*.example.com"
respond: hello
```

通配符只匹配一个 DNS 标签：匹配 foo.example.com，不匹配 example.com 或 a.foo.example.com。精确站点优先于通配站点，通配站点优先于 SaaS 映射和全局兜底；带端口的通配站点只匹配对应端口。HTTP 域名匹配与 TLS 证书配置是独立能力，HTTPS 仍需要有效证书。加载启用 HTTPS 的通配站点时，若没有对应的已启用 DNS-01 配置或站点自定义证书，会记录配置警告；已有可用通配证书仍可正常使用。通配站点不会授权为任意子域单独签发证书：优先使用已有 DNS-01 通配证书；证书缺失且 on-demand 关闭时拒绝签发，开启时仍须通过 on-demand 策略和限流。

精确站点可使用 `redirect: https://www.{host}{uri}`；多域名配置展开后也按精确站点处理。`{labels.N}` 从右向左、从 0 开始取域名标签，不含端口：对 www.example.com，labels.0=com、labels.1=example、labels.2=www；越界及 IP 地址返回空字符串。例如 `site: www.a.com, www.b.com` 配合 `redirect: https://{labels.1}.{labels.0}{uri}` 可以去掉 www。通配、兜底站点不会放宽由占位符生成的跨域重定向，query/header 等输入也不能改变目标 origin。

### SPA 首页缓存默认值

`spa: ./dist` 为回退首页、根首页与直接访问的首页文件默认设置 `Cache-Control: no-cache`，允许缓存保存但要求使用前重新验证。普通 JS/CSS 等静态资源不受影响；带扩展名的缺失资源继续返回 404。显式 `cache_control` 或已配置的 Cache-Control 响应头优先；显式 cache_control 仍作用于全部文件。

### 跨站点共享的匹配条件和配置片段（_shared.yaml）

在站点目录放一个 `sites/_shared.yaml`（KV 模式对应站点前缀下的 `_shared.yaml` 键），只能写顶层 `matchers` 和 `snippets`。它不会被编译成站点，只作为公共定义随站点一起分发；各站点通过 `match: "@名称"` 和 `import: "@名称"` 引用，原有 `import: 名称` 仍可使用。`config.yaml` 不再承载这两项，写在主配置中会报错并提示迁移位置。

站点直接引用时，本地同名定义优先；共享片段内部的 `import` 始终在共享定义中解析，不会被站点定义改变。只有被引用的共享定义才并入站点，片段里的 `use` 在实际引用它的站点中检查中间件名称。`_shared.yaml` 本身在加载时校验语法、引用和循环，`_shared.yaml` 与 `_shared.yml` 不能同时存在。

修改 `_shared.yaml` 会对全部站点重新校验，任何站点失败都整体拒绝并保留旧定义和旧站点；KV 模式下共享定义内容不变时不重建站点，先于共享定义到达而失败的 KV 站点会在共享定义生效后自动重试。删除仍被引用的共享定义会被拒绝。错误信息标明 `_shared.yaml` 或站点文件的来源行号。

```yaml
# sites/_shared.yaml
matchers:
  api:
    prefix: /api
snippets:
  common:
    compress: true
```

```yaml
# sites/app.yaml
site: https://a.b.com
routes:
  - match: "@api"
    import: "@common"
    proxy: localhost:8080
```

`site: https://a.b.com` 等价于 `site: a.b.com` 加 `https: true`，使用现有 TLS 和 HTTP 到 HTTPS 重定向机制。允许末尾 `/`，不允许 URL 路径、查询参数或用户信息。与 `https: false` 同时配置会报错。显式端口沿用现有 `site: host:port` 的监听规则；HTTPS 跳转仍使用现有默认目标端口规则。

站点级 `ech: ech.example.com` 与 `site:` 同级，选择主配置 ech.groups 中的公共域名及其 DNS 提供商。域名自动收集，不需要重复配置 domains；多组必须显式选择，单组允许 ech: true，ech: false 关闭。要求主配置 ech.enabled、HTTPS 443 和 TLS 1.3；拒绝未知组、通配符/IP/透传站点。站点选组可热加载，换组时先撤回旧记录再由新组发布；旧全局 domains 列表继续启用，不受 false 取消。
