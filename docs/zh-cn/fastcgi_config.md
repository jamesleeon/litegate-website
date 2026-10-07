# LiteGate FastCGI 配置指南

本文档介绍如何在 LiteGate 的 YAML 站点配置中,把请求反向代理到 **FastCGI** 后端(最常见的就是 **PHP-FPM**),让 LiteGate 直接为 PHP / WordPress / Laravel 等环境服务。

普通 PHP 网站优先使用 [站点配置的 `php` 简写](user/03-configuration/site-config.md#php-网站wordpress--laravel)，只需配置网站目录和 PHP-FPM 地址，即可自动处理静态文件、目录首页和入口回退。本文的底层 FastCGI 配置适合需要手动控制路由的场景。

> 适用场景:用 LiteGate 替代「Nginx + php-fpm」中的 Nginx 角色,直接通过 TCP 端口或 Unix Socket 与 php-fpm 通信。

---

## 1. 最小配置(TCP)

假设 php-fpm 监听在 `127.0.0.1:9000`,站点代码在后端机器的 `/var/www/html`:

```yaml
domain: example.com
routes:
  - name: php-route
    match:
      path: /index.php
    action:
      type: proxy
      upstream_type: static
      proto: fastcgi                 # 必填:声明走 FastCGI 协议
      fastcgi_root: /var/www/html    # 必填:后端的 Document Root(SCRIPT_FILENAME 的根)
      upstream:
        - "fastcgi://127.0.0.1:9000" # FastCGI 后端地址
```

三个必填项就这么简单:**`proto: fastcgi`** + **`fastcgi_root`** + **`upstream`**。

---

## 2. 使用 Unix Socket

php-fpm 用 Unix Socket 时(性能更好,免去 TCP 开销),把 `upstream` 换成 `unix://` 加 socket 绝对路径即可:

```yaml
action:
  type: proxy
  upstream_type: static
  proto: fastcgi
  fastcgi_root: /var/www/html
  upstream:
    - "unix:///var/run/php/php8.2-fpm.sock"   # 注意是三个斜杠:unix:// + /绝对路径
```

> Unix Socket 仅适用于 LiteGate 与 PHP-FPM 所在系统都支持 Unix Domain Socket 的场景。Windows 部署建议使用 `fastcgi://127.0.0.1:9000`；Windows Named Pipe 不是 Unix Socket，当前不作为 FastCGI upstream 支持。

---

## 3. upstream 支持的写法

| 写法 | 说明 |
|---|---|
| `fastcgi://127.0.0.1:9000` | TCP,**必须带端口** |
| `fastcgi://[::1]:9000` | IPv6 + 端口 |
| `unix:///var/run/php-fpm.sock` | Unix Socket,**三斜杠** + socket 绝对路径 |
| `127.0.0.1:9000` | 裸 TCP 地址(等价于 `fastcgi://`),也必须带端口 |

FastCGI 路由的 `upstream` **只接受** `fastcgi://` / `unix://` / 裸 `host:port` 三种;写成 `http://`、`ftp://` 等会在加载时报错。

---

## 4. 完整字段参考

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `proto` | string | — | **必填**,固定为 `fastcgi` 才会启用 FastCGI;只要设置了任意 `fastcgi_*` 字段而 `proto` 不是 `fastcgi`,加载会报错 |
| `fastcgi_root` | string | — | **必填**,后端的 Document Root,与脚本路径拼成 `SCRIPT_FILENAME` |
| `upstream` | list | — | **必填**,后端地址列表(见上表),支持多个做负载均衡 |
| `index` | string | `index.php` | 当请求路径以 `/` 结尾时,自动补的入口文件名 |
| `fastcgi_split_path` | string | `.php` | PATH_INFO 切分点,必须含 `.`;用于把 `/a.php/b` 切成脚本 `/a.php` + PATH_INFO `/b` |
| `fastcgi_extensions` | list | `[".php"]` | **允许执行的扩展名白名单**;元素必须以 `.` 开头(如 `.php`),或用 `*` 放行全部 |
| `fastcgi_params` | map | `{}` | 追加安全的 CGI 环境变量，例如 `APP_ENV`、`REDIRECT_STATUS`；不能覆盖 `SCRIPT_FILENAME`、`REQUEST_URI`、`HTTP_*` 等内置变量 |
| `fastcgi_keep_conn` | bool | `false` | 是否启用与后端的**连接池复用**(类似 Nginx `fastcgi_keep_conn`) |
| `fastcgi_max_idle_conns` | int | `2` | 连接池保留的最大空闲连接数,不能为负 |
| `fastcgi_idle_timeout` | int | `0` | 空闲连接回收时间(秒),`0` 表示不超时回收,不能为负 |
| `timeout` | int | `0` | 整个请求/响应的硬超时(秒),`0` 表示不设硬超时 |
| `host` | string | — | 覆盖传给后端的 `HTTP_HOST` / `SERVER_NAME` |
| `strip_prefix` / `prepend_prefix` | string | — | 路径改写,会同步影响 `SCRIPT_NAME` 与 `SCRIPT_FILENAME` |

---

## 5. 开启连接池(keep-alive)

默认每个请求都新建一条到后端的连接、用完即关。高并发 PHP 场景下,开启连接复用可显著降低连接建立开销:

```yaml
action:
  type: proxy
  upstream_type: static
  proto: fastcgi
  fastcgi_root: /var/www/html
  upstream:
    - "unix:///var/run/php/php8.2-fpm.sock"
  fastcgi_keep_conn: true          # 开启连接池复用
  fastcgi_max_idle_conns: 16       # 最多保留 16 条空闲连接
  fastcgi_idle_timeout: 60         # 空闲 60 秒后回收
  timeout: 30                      # 单请求最长 30 秒
```

> 连接只有在**响应被完整、干净地读完**后才会还池;客户端提前断开或上传中断的连接会被直接关闭,不会污染下一个请求。取用前还会做一次轻量探活,自动丢弃被后端关掉的失效连接。

---

## 6. PATH_INFO 与子路径

`fastcgi_split_path`(默认 `.php`)用于把路径切分成「脚本 + PATH_INFO」。例如请求 `/app.php/user/42`:

- `SCRIPT_NAME` = `/app.php`
- `PATH_INFO` = `/user/42`
- `SCRIPT_FILENAME` = `<fastcgi_root>/app.php`

切分采用「最后一个匹配且其后紧跟 `/` 或结尾」的贪婪规则,与 Nginx `fastcgi_split_path_info ^(.+\.php)(/.+)$` 行为一致。

---

## 7. 自动注入的 CGI 环境变量

LiteGate 会自动构造并传给后端这些变量,**无需手动配置**:

`REQUEST_METHOD`、`REQUEST_URI`、`QUERY_STRING`、`CONTENT_TYPE`、`CONTENT_LENGTH`、`GATEWAY_INTERFACE`、`SERVER_PROTOCOL`、`SCRIPT_FILENAME`、`SCRIPT_NAME`、`PATH_INFO`、`PATH_TRANSLATED`、`DOCUMENT_ROOT`、`DOCUMENT_URI`、`REMOTE_ADDR`、`REMOTE_PORT`、`SERVER_ADDR`、`SERVER_PORT`、`SERVER_NAME`、`HTTP_HOST`,以及全部 `HTTP_*` 请求头。客户端使用 HTTPS 时还会带上 `HTTPS=on`。

如需追加应用变量，使用 `fastcgi_params`：

如果 TLS 在前置负载均衡终止，需要在全局 `real_ip.trusted_proxies` 中配置实际代理地址。来自可信直接连接的单一 `X-Forwarded-Proto: https` 会设置 `HTTPS=on`，且在 Host 未指定端口时使用 `SERVER_PORT=443`。不采信非可信来源、重复或逗号分隔的协议值。

```yaml
fastcgi_params:
  APP_ENV: production
  REDIRECT_STATUS: "200"
```

变量名必须是大写字母、数字或下划线且不能以数字开头。为避免绕过脚本路径和请求安全检查，内置 CGI 变量与 `HTTP_*` 变量不能覆盖。

---

## 8. 安全说明

- **扩展名白名单**:默认仅允许 `.php` 被当作脚本执行。请求 `/uploads/avatar.jpg` 这类非白名单扩展名会被网关直接拒绝(返回错误),避免上传文件被误执行。务必**不要**轻易把 `fastcgi_extensions` 设成 `*`。
- **路径穿越防护**:请求路径中包含 `..` 段、或拼接后逃出 `fastcgi_root` 的,都会被拦截。
- **httpoxy 防护**:`Proxy` 请求头不会被透传成 `HTTP_PROXY`。

---

## 9. 使用限制

LiteGate 不内嵌 PHP Runtime，也不负责启动或管理 PHP-FPM。PHP 脚本由独立 PHP-FPM 服务执行。

WordPress、Laravel 等前端控制器应用可以通过 `serve` Action 的 `try_files` 回退到 `/index.php`。内部重定向会保留客户端原始 `REQUEST_URI` 和查询参数。`try_files` 不能直接配置在 `proxy` Action 下；错误配置会在加载时被拒绝。

`serve` 会检查 LiteGate 本机文件系统，所以 LiteGate 与远程 PHP-FPM 必须共享同一份站点文件，或者将静态资源部署到 LiteGate 可访问的目录。

---

## 10. 完整示例

```yaml
domain: php.example.com
routes:
  # PHP 脚本和 PATH_INFO 请求交给 PHP-FPM。
  - name: php-scripts
    priority: 100
    match:
      rule: 'PathRegex("(?i)^/.*\.php(?:/.*)?$")'
    action:
      type: proxy
      upstream_type: static
      proto: fastcgi
      fastcgi_root: /var/www/html
      index: index.php
      fastcgi_split_path: ".php"
      fastcgi_extensions: [".php"]
      fastcgi_params:
        APP_ENV: production
        REDIRECT_STATUS: "200"
      upstream:
        - "unix:///var/run/php/php8.2-fpm.sock"
      fastcgi_keep_conn: true
      fastcgi_max_idle_conns: 16
      fastcgi_idle_timeout: 60
      timeout: 30

  # 静态文件直接返回；不存在的干净 URL 内部转到 /index.php。
  - name: php-static-and-front-controller
    match:
      path_prefix: /
    action:
      type: serve
      root: /var/www/html
      try_files:
        - "{path}"
        - "/index.php"
```

---

相关文档:[站点配置](user/03-configuration/site-config.md) · [proxy action](user/04-actions/proxy.md)
