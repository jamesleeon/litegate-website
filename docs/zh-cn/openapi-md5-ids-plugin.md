# OpenAPI MD5 IDS Provider 配置与协议

`openapi-md5` 是默认 LiteGate 二进制内置注册的 IDS Provider，与 NATS 一样通过默认入口空导入。只有路由绑定后才参与请求验证。它读取原始 Body 完成 MD5 验签；成功返回 `ActionForward`，不设置 `Discovery`，继续执行路由动作。

> MD5 仅用于兼容已有客户端。新协议应优先使用 HMAC-SHA256。

## 签名协议

请求头：

```text
_appid      应用 ID
_method     HTTP 方法，必须与实际请求方法一致
_timestamp  Unix 秒时间戳
_sign       32 位十六进制 MD5
```

旧客户端先按 `_appid`、`_method`、`_timestamp` 的字段名排序，然后只拼接字段值。等价公式为：

```text
sign = hex(md5(
    secret
    + appid
    + method
    + timestamp
    + raw_request_body
    + secret
))
```

Body 使用收到的原始字节，不做 JSON 格式化、字符集转换或换行处理。签名比较使用常量时间算法；宿主读取并恢复 Body，下游仍能完整读取。

## plugin.yaml 配置与调试日志

```yaml
# config.yaml
plugin_config:
  path: plugin.yaml
  watch: true
```

```yaml
# plugin.yaml
providers:
  openapi-md5:
    debug_log: true
    secrets:
      orders: '${ORDERS_OPENAPI_SECRET}'
```

```yaml
# sites/open.example.com.yaml
site: open.example.com
https: true
/api:
  proxy: 127.0.0.1:8080
  ids:
    provider: openapi-md5
    fail_policy: deny
    options:
      secret_ref: orders
```

`secret_ref` 从 `providers.openapi-md5.secrets.<ref>` 获取密钥，与 `secret_env` / `secret_env_prefix` 不能同时配置。密钥与 debug_log 每次请求从最新配置视图读取，文件热更新后无需重启。关闭日志将 debug_log 改为 false。日志使用 Info 级别，包含插件名称、开始/结束事件、决策、固定原因和耗时；系统日志级别为 warn/error 时会过滤这些日志。

Litemesh 标签使用 `litegate.http.routers.api.ids.provider=openapi-md5`、`litegate.http.routers.api.ids.failpolicy=deny` 和 `litegate.http.routers.api.ids.options.secret_ref=orders`，完整路由示例见 [IDS Provider 指南](ids-provider-plugin-guide.md)。密钥与插件配置放在网关进程侧。

## Secret 配置

Secret 不放在路由 options。单 Secret 路由默认读取：

```text
LITEGATE_OPENAPI_MD5_SECRET
```

也可以引用另一个环境变量：

```yaml
options:
  secret_env: ORDERS_OPENAPI_SECRET
```

多个 App 共用路由时使用前缀：

```yaml
options:
  secret_env_prefix: OPENAPI_SECRET_
```

App ID 会转为大写环境变量后缀，非字母数字替换成下划线。例如 `app-42` 读取：

```text
OPENAPI_SECRET_APP_42
```

如果需要从 Redis、数据库或租户系统动态获取 Secret，需要在自行实现的 Provider 中增加带缓存的业务查询逻辑。

## 路由配置

```yaml
routes:
  - name: open-orders
    match:
      path_prefix: /openapi/orders
    action:
      type: proxy
      service_name: orders
      ids:
        provider: openapi-md5
        fail_policy: deny
        options:
          secret_env_prefix: OPENAPI_SECRET_
          max_clock_skew: 5m
          max_body_size: 1MiB
```

可选参数：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `app_id_header` | `_appid` | App ID Header |
| `method_header` | `_method` | 方法 Header |
| `timestamp_header` | `_timestamp` | Unix 秒时间戳 Header |
| `signature_header` | `_sign` | 签名 Header |
| `secret_ref` | 空 | plugin.yaml 中 secrets 的引用，与环境变量路由选项互斥 |
| `secret_env` | `LITEGATE_OPENAPI_MD5_SECRET` | 单 Secret 环境变量引用 |
| `secret_env_prefix` | 空 | 按 App ID 解析环境变量；设置后优先于 `secret_env` |
| `max_clock_skew` | `5m` | 允许的客户端时钟偏差 |
| `max_body_size` | `1MiB` | 允许参与签名的最大 Body，不得超过宿主 8 MiB 上限 |

## 决策结果

- 验签成功：`ActionForward`，不返回 Discovery，进入默认下游。
- 字段缺失、方法不匹配、时间戳过期或签名错误：直接响应 401。
- Body 超限：直接响应 413。
- Secret 环境变量缺失或配置参数非法：返回 error，由 `fail_policy` 处理。

失败响应为 JSON，并带 `Cache-Control: no-store`：

```json
{"code":"invalid_signature"}
```

## Go 客户端

仓库中的 `pkg/apiclient` 已实现相同算法：

```go
client := apiclient.NewClient(
    "app-42",
    os.Getenv("OPENAPI_SECRET_APP_42"),
    "https://api.example.com",
)

resp, err := client.PostJSON("/openapi/orders", []byte(`{"sku":"A-1"}`))
```

实现位于 `internal/plugins/openapi_md5/provider.go`，通过 `cmd/litegate/plugins.go` 默认注册。重新编译网关后，可用 `litegate plugins inspect ids/openapi-md5` 查询。开发契约见 [IDS Provider 指南](ids-provider-plugin-guide.md)。

MD5 协议不包含 Host、路径或 Query，时间戳窗口也不是一次性防重放机制；复用密钥的接口具有相同签名边界，客户端协议扩展需双方同时修改。
