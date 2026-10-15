# Rewrite：路径与查询参数改写

Rewrite 在路由匹配后修改当前请求，不会按新 URL 再次选路。浏览器地址不变；需要浏览器跳转时使用 redirect。CORS 预检可以提前返回，后续安全和认证阶段看到改写后的请求。

`path.pattern` 使用 Go 正则，匹配解码后的 URL.Path，不包含查询串；`path.target` 必须以 `/` 开头，不能含 `?`、`#` 或控制字符。两项必须同时配置。捕获组来自 rewrite 自己的正则；推荐 `${1}` 避免边界歧义。旧 `pattern` / `target` 写法兼容，但不能与 `path` 混用。

查询参数用 `query.remove`、`rename`、`set`、`add` 分别删除、改名、覆盖和追加，按该顺序执行。set/add 支持请求变量；path.target 不展开这些变量。使用锚点限制路径替换范围，不能直接照搬 PCRE 前后向断言。

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

## 相关文档与代码

- [Pipeline](../05-middleware/pipeline.md)
