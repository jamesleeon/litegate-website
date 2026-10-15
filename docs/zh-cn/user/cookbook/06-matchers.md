# 命名请求条件

matchers 给请求条件起名字，路由用带引号的 "@name" 引用，在加载时展开，运行时与内联条件等价。不同字段为 AND，path 列表内为 OR。

字段包括 path、prefix、method、header、query、rule。path 字符串精确匹配；列表支持通配。prefix 按路径段匹配。优先级按条件与路由规则决定，不按条件定义所在位置。未定义引用或无效表达式应先通过预检修复。

<!-- case: named-matchers -->
```yaml
site: example.com
matchers:
  blocked: {path: [/xmlrpc.php, /.env, '*.sql']}
  post: {method: POST}
routes:
  - match: '@blocked'
    respond: {status: 403, body: forbidden}
  - match: '@post'
    proxy: localhost:8081
proxy: localhost:8080
```

```check
GET http://example.com/xmlrpc.php => 403 "forbidden"
GET http://example.com/backup.sql => 403 "forbidden"
POST http://example.com/orders => 8081 /orders
GET http://example.com/orders => 8080 /orders
```

## 相关文档与代码

- [Priority](../02-concepts/routing-priority.md)
- [V2 concepts](../03-configuration/site-yaml-v2-concepts.md)
