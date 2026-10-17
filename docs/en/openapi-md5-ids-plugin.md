# OpenAPI MD5 IDS Provider: Configuration and Protocol

`openapi-md5` is an IDS Provider registered in the default LiteGate binary, blank-imported by the default entrypoint like NATS. It takes part in request verification only on routes bound to it. It verifies an MD5 signature over the raw body; on success it returns `ActionForward` without setting `Discovery`, and the route's action continues.

> MD5 exists only for compatibility with existing clients. New protocols should prefer HMAC-SHA256.

## Signature protocol

Request headers:

```text
_appid      application ID
_method     HTTP method; must equal the actual request method
_timestamp  Unix timestamp in seconds
_sign       32 hexadecimal digit MD5
```

Legacy clients sort the fields `_appid`, `_method`, `_timestamp` by name and concatenate only the values. The equivalent formula:

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

The body is the raw bytes received, with no JSON reformatting, charset conversion or newline handling. Signatures are compared in constant time; the host reads and restores the body so downstream can still read it in full.

## plugin.yaml configuration and debug logging

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

`secret_ref` takes the secret from `providers.openapi-md5.secrets.<ref>` and cannot be combined with `secret_env` / `secret_env_prefix`. The secret and debug_log are read from the latest configuration view on every request, so file hot reloads need no restart. Set debug_log to false to turn logging off. Logs use Info level and contain the plugin name, start/end events, the decision, a fixed reason and the duration; a system log level of warn/error filters them out.

Litemesh tags use `litegate.http.routers.api.ids.provider=openapi-md5`, `litegate.http.routers.api.ids.failpolicy=deny` and `litegate.http.routers.api.ids.options.secret_ref=orders`; for a complete routing example see the [IDS Provider guide](ids-provider-plugin-guide.md). Secrets and plugin configuration stay on the gateway process side.

## Secret configuration

Secrets don't go in route options. A single-secret route reads by default:

```text
LITEGATE_OPENAPI_MD5_SECRET
```

You can reference another environment variable:

```yaml
options:
  secret_env: ORDERS_OPENAPI_SECRET
```

When several apps share a route, use a prefix:

```yaml
options:
  secret_env_prefix: OPENAPI_SECRET_
```

The App ID becomes an upper-case environment variable suffix, with non-alphanumerics replaced by underscores. For example `app-42` reads:

```text
OPENAPI_SECRET_APP_42
```

To fetch secrets dynamically from Redis, a database or a tenant system, implement your own Provider with cached business lookups.

## Route configuration

```yaml
site: open.example.com
services:
  orders:
    discovery: {name: orders}
routes:
  - name: open-orders
    match:
      path_prefix: /openapi/orders
    service: orders
    ids:
      provider: openapi-md5
      fail_policy: deny
      options:
        secret_env_prefix: OPENAPI_SECRET_
        max_clock_skew: 5m
        max_body_size: 1MiB
```

Optional parameters:

| Parameter | Default | Description |
| --- | --- | --- |
| `app_id_header` | `_appid` | App ID header |
| `method_header` | `_method` | Method header |
| `timestamp_header` | `_timestamp` | Unix-seconds timestamp header |
| `signature_header` | `_sign` | Signature header |
| `secret_ref` | empty | Reference into plugin.yaml secrets; mutually exclusive with the environment variable options |
| `secret_env` | `LITEGATE_OPENAPI_MD5_SECRET` | Environment variable for a single secret |
| `secret_env_prefix` | empty | Resolve the environment variable by App ID; takes precedence over `secret_env` |
| `max_clock_skew` | `5m` | Allowed client clock skew |
| `max_body_size` | `1MiB` | Largest body included in the signature; cannot exceed the host's 8 MiB limit |

## Decisions

- Valid signature: `ActionForward`, no Discovery, to the default downstream.
- Missing fields, method mismatch, expired timestamp or wrong signature: direct 401.
- Body over the limit: direct 413.
- Missing secret environment variable or invalid parameters: an error, handled by `fail_policy`.

Failure responses are JSON with `Cache-Control: no-store`:

```json
{"code":"invalid_signature"}
```

## Go client

`pkg/apiclient` in the repository implements the same algorithm:

```go
client := apiclient.NewClient(
    "app-42",
    os.Getenv("OPENAPI_SECRET_APP_42"),
    "https://api.example.com",
)

resp, err := client.PostJSON("/openapi/orders", []byte(`{"sku":"A-1"}`))
```

The implementation is in `internal/plugins/openapi_md5/provider.go` and is registered by default through `cmd/litegate/plugins.go`. After rebuilding the gateway, query it with `litegate plugins inspect ids/openapi-md5`. For the development contract see the [IDS Provider guide](ids-provider-plugin-guide.md).

The MD5 protocol doesn't cover the host, path or query, and the timestamp window is not one-time replay protection; interfaces sharing a secret share the same signature boundary, and protocol extensions require changing both client and server.
