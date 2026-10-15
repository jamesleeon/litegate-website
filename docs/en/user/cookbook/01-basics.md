# Basics: static sites and APIs

Put site files in the configured sites directory. A default serve hosts static pages while /api uses proxy. Paths are preserved; /api is not automatically stripped. Configure rewrite when the backend needs prefix removal.

Validate configuration and check static roots, permissions, backend reachability and Host before deployment. HTTPS also needs valid certificates and global entrypoint configuration.

<!-- case: static-and-api -->
```yaml
site: app.example.com
serve: ./public
/api:
  proxy: 127.0.0.1:8080
```

```check
GET http://app.example.com/ => 200 "public"
GET http://app.example.com/api/orders => 8080 /api/orders
```

## Related documentation and code

- [Serve](../04-actions/serve.md)
- [Proxy](../04-actions/proxy.md)
