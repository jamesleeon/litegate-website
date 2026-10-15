# LiteGate v2 quick start

New configurations use ordinary .yaml files and top-level site. No separate Lite or standard mode selection is needed; existing .lite.yaml files remain compatible.

## Get online quickly

Run `litegate -hello` to try hello world on local port 8080. Save production configuration as sites/app.yaml:

```yaml
site: https://app.example.com
/api:
  proxy: 127.0.0.1:8080
  strip_prefix: true
spa: ./dist
```

Bare domains do not enable HTTPS redirection by default; use https:// or https: true explicitly. Complex conditions use routes with match and advanced options use action; these are all v2 capabilities.

- [WebDAV v2 guide](user/04-actions/webdav.md)
- [Site configuration](user/03-configuration/site-config.md)
- [Quick start](user/01-getting-started/quick-start.md)
