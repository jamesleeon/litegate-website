# OpenAPI MD5 compatibility Provider

openapi-md5 is compiled into the default entry and validates only bound routes. It supports a legacy MD5 Body-signature protocol; prefer HMAC-SHA256 for new protocols. Headers are _appid, _method, _timestamp (Unix seconds) and _sign (32 hexadecimal digits). _method must equal the actual method.

The signature is hex(md5(secret + appid + method + timestamp + raw_request_body + secret)). Body uses raw bytes without JSON formatting, encoding changes or newline normalization. Comparison is constant-time, Body is restored, and success Forwards to the existing route destination.

Store secrets in plugin configuration providers.openapi-md5.secrets or supported environment references, never plaintext route options. secret_ref is mutually exclusive with secret_env/secret_env_prefix. The default environment variable is LITEGATE_OPENAPI_MD5_SECRET. debug_log reads current configuration and respects global logging levels without printing keys.

Test timestamp bounds, invalid appid/method/sign, body limits, key rotation and downstream body integrity. Timestamp validation alone is not comprehensive business replay protection.

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

## Related documentation and code

- [Implementation](../../internal/plugins/openapi_md5)
- [IDS guide](ids-provider-plugin-guide.md)
