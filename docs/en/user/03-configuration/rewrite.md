# Rewrite: paths and query parameters

Rewrite changes the current request after route selection; it does not route again using the new URL. The browser URL stays unchanged. Use a redirect for a browser-visible move. CORS preflight can return early; later security and authentication phases see the transformed request.

`path.pattern` uses Go regular expressions against decoded URL.Path, excluding the query. `path.target` must start with `/` and cannot contain `?`, `#` or control characters. Both fields are required together. Captures come from the rewrite expression itself; prefer `${1}` to avoid ambiguous boundaries. Legacy `pattern` / `target` remain compatible but cannot be combined with `path`.

Query operations run in this order: `query.remove`, `rename`, `set`, `add`, to remove, rename, replace and append values. set/add accept request variables; path.target does not expand them. Anchor expressions to bound replacement and do not copy PCRE lookaround syntax.

```yaml
site: api.example.com
routes:
  - name: legacy
    match: {path_prefix: /legacy/}
    rewrite:
      path: {pattern: '^/legacy/(.*)$', target: '/api/${1}'}
      query:
        remove: [debug]
        rename: {uid: user_id}
        set: {source: litegate}
        add: {trace: '1'}
    proxy: ['127.0.0.1:8080']
```

## Related documentation and code

- [Pipeline](../05-middleware/pipeline.md)
