# OpenAPI MD5 兼容 Provider

openapi-md5 在默认入口编入，只有绑定路由后才验签。它兼容旧 MD5 Body 签名协议；新协议优先使用 HMAC-SHA256。请求头为 _appid、_method、_timestamp（Unix 秒）、_sign（32 位十六进制）。_method 必须与实际方法一致。

签名等于 hex(md5(secret + appid + method + timestamp + raw_request_body + secret))。Body 使用原始字节，不格式化 JSON、不改变编码或换行；比较为常量时间，读取后恢复 Body，成功 Forward 到路由原有下游。

密钥放插件配置 providers.openapi-md5.secrets 或支持的环境引用，不在路由 options 放明文。secret_ref 与 secret_env/secret_env_prefix 互斥。默认环境名 LITEGATE_OPENAPI_MD5_SECRET；debug_log 从最新配置读取，日志受全局级别控制且不输出密钥。

上线验证时间戳窗口、错误 appid/method/sign、Body 大小、密钥轮换和下游 Body 完整性；不能把时间戳校验等同于完整的业务防重放。

```yaml
plugin_config:
  path: plugin.yaml
  watch: true
```

```yaml
providers:
  openapi-md5:
    debug_log: false
    secrets:
      orders: '${ORDERS_OPENAPI_SECRET}'
```

```yaml
site: open.example.com
https: true
/api:
  proxy: 127.0.0.1:8080
  ids:
    provider: openapi-md5
    fail_policy: deny
    options: {secret_ref: orders}
```

## 相关文档与代码

- [Implementation](../../internal/plugins/openapi_md5)
- [IDS guide](ids-provider-plugin-guide.md)
