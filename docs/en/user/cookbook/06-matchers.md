# Named request matchers

matchers names request conditions. Routes reference quoted "@name" values expanded at load time, equivalent to inline conditions. Different fields combine with AND; entries in a path list combine with OR.

Fields include path, prefix, method, header, query and rule. A path string matches exactly; lists support wildcards. prefix matches path segments. Priority follows conditions/routing rules rather than definition location. Fix undefined references and invalid expressions through preflight.

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

## Related documentation and code

- [Priority](../02-concepts/routing-priority.md)
- [V2 concepts](../03-configuration/site-yaml-v2-concepts.md)
