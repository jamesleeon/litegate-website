# Rewrite: Path and Query Rewriting

LiteGate's `rewrite` adapts request URLs to the format the current backend understands. **Route matching first decides which route and upstream to use; rewrite then changes the path and query within that route. Rewriting never re-matches routes.**

For example `/legacy/users/42` can become `/api/users/42`, but the request is still handled by the route it originally matched. The browser address doesn't change, and no `3xx` is produced by rewrite.

## 1. Execution order and differences from Nginx

For a request entering route processing, the main order is:

```text
Original request → match Site / Route → CORS and preflight handling
                 → rewrite → other RequestTransform middleware
                 → security checks and traffic control → the route's Action
```

So a route's `Path`, `Query`, `Header` and other conditions are evaluated before rewrite; later WAF, IP policy, authentication and rate limiting see the request as processed by the RequestTransform phase. CORS preflights may return early, in which case rewrite never runs.

| Scenario | Nginx | LiteGate |
| :--- | :--- | :--- |
| Re-select routing after a rewrite | `rewrite ... last` looks up the location again with the new URI | rewrite never re-matches routes; select the route from conditions on the original request |
| Rewrite within the current branch | `break` stops the current rewrite directives and continues in the current location | Use the current route's `rewrite`; there are no `last` / `break` flags |
| Send the browser to a new address | rewrite with `redirect` / `permanent`, or a URL replacement | Use the `redirect` Action, or the `redirect_regex` / `redirect_scheme` middleware |
| Regex syntax | PCRE | Go `regexp`; PCRE lookarounds, regex back-references and the like can't be copied as-is |
| Add or remove query parameters | The replacement may contain a query string, with rules for appending old arguments | `path.target` holds only the path; query parameters are handled under `query` |

For Nginx behavior see the [official rewrite module documentation](https://nginx.org/en/docs/http/ngx_http_rewrite_module.html#rewrite). The comparison is for migrating configuration; LiteGate's rewrite is not a compatible implementation of the Nginx directive set.

## 2. A complete path rewrite

```yaml
site: api.example.com

routes:
  - name: legacy-users
    match:
      rule: 'PathRegex("^/legacy/users/([^/]+)$")'
    proxy: ["127.0.0.1:8080"]
    rewrite:
      path:
        pattern: '^/legacy/users/([^/]+)$'
        target: '/api/users/${1}'
```

A request to `/legacy/users/42?view=full` is sent to the current upstream as `/api/users/42?view=full`. Only the path changes; the original query string stays.

`match.rule` decides whether this route is selected; `rewrite.path.pattern` decides whether the rewrite runs within it. These are two matches with different purposes. **Capture groups in rewrite come from its own `path.pattern`, not from the route matching regex.**

| Field | Description |
| :--- | :--- |
| `path.pattern` | Go regex on the decoded `URL.Path`, without the query string; invalid regexes are rejected at load time |
| `path.target` | The replacement path; must start with `/` and must not contain `?`, `#` or control characters |

`pattern` and `target` must be configured together. Anchor the whole path with `^` and `$`: the implementation uses `ReplaceAllString`, and an unanchored regex may replace several matching fragments.

The replacement supports `$1`, `${1}` and named capture group references. When a capture group is directly followed by ordinary characters, use `${1}` to mark the boundary, as in `/v${1}suffix`. The path target doesn't expand request variables such as `{query.x}` or `{header.X}`; those work in the query `set` / `add` below.

The legacy form `rewrite.pattern` / `rewrite.target` is still supported but cannot be combined with `rewrite.path`. Use `path` for new configuration.

## 3. Query rewriting

Path and query can be rewritten together:

```yaml
site: api.example.com

routes:
  - name: legacy-users
    match:
      rule: 'PathRegex("^/legacy/users/([^/]+)$")'
    proxy: ["127.0.0.1:8080"]
    rewrite:
      path:
        pattern: '^/legacy/users/([^/]+)$'
        target: '/api/users/${1}'
      query:
        remove: [debug]
        rename:
          uid: user_id
        set:
          source: litegate
          path_user: '$1'
          trace: '{header.X-Trace-ID}'
        add:
          tag: migrated
```

For the request `/legacy/users/42?uid=7&debug=1&tag=old` with header `X-Trace-ID: t123`, the upstream receives:

```text
/api/users/42?path_user=42&source=litegate&tag=old&tag=migrated&trace=t123&user_id=7
```

The operations always run in the order **`remove → rename → set → add`**, regardless of their order in the YAML.

| Operation | Behavior |
| :--- | :--- |
| `remove` | Delete a parameter and all its values; skipped if absent |
| `rename` | Move all values of the source parameter, overwriting the target's values; if the source is absent the target is unchanged |
| `set` | Overwrite the parameter with one value; created if absent |
| `add` | Append a value, keeping existing values of the same name |

rename works from one snapshot of the source values rather than moving them serially in map iteration order. For example `a: b`, `b: c` moves the old `a` to `b` and the old `b` to `c`; the old `a` doesn't end up in `c`. Renaming several sources to the same target is rejected at load time.

`set` / `add` values support path capture groups and request variables such as `{host}`, `{path}`, `{query.x}`, `{header.X}` and `{cookie.x}`. Here `{path}` is the path after this rewrite; `{query.x}` reads the request URL's query parameters, not the query being built, so don't rely on the order of `set` entries. Query capture references use `$1`, `$2` and so on; the query template treats braces as request variables, so don't copy the path target's `${1}` form. Strings supplied by the request are expanded only once; a request value that is literally `$1` stays as plain text.

You can omit `path` and configure only `query`. **If `path` is configured but doesn't match, the whole rewrite is skipped, query operations included.** To change parameters on every request of a route, use a query-only rewrite, or make sure the path regex covers the route's requests.

## 4. Migrating from Nginx `last`: choose the upstream with matching rules

Suppose `/callback` normally goes to the old service, but requests whose `state` starts with `sub.` must go to a new service that only accepts `/sub_callback`. Don't rewrite to `/sub_callback` and expect another route to take over; match on the original request and set both the upstream and the target path in the same route:

```yaml
site: oauth.example.com

routes:
  - name: sub-callback
    priority: 200
    match:
      rule: 'Path("/callback") && QueryPrefix("state", "sub.")'
    proxy: ["127.0.0.1:9002"]
    rewrite:
      path:
        pattern: '^/callback$'
        target: '/sub_callback'

  - name: default-callback
    priority: 100
    match:
      rule: 'Path("/callback")'
    proxy: ["127.0.0.1:9001"]
```

`/callback?state=sub.abc` goes to 9002 as `/sub_callback?state=sub.abc`; other `/callback` requests go to 9001. If the new service also accepts `/callback`, just remove the first route's rewrite; the split still works.

The `state` prefix only selects the route; the OAuth backend must still verify that state is random, unexpired and bound to the session. See [Single callback URL routing](../09-advanced/oauth-single-callback.md) for the full approach.

## 5. Named middleware form

To reuse rules, define a named `rewrite` middleware:

```yaml
site: api.example.com

middlewares:
  legacy-adapter:
    type: rewrite
    config:
      path_pattern: '^/legacy/(.*)$'
      path_target: '/api/${1}'
      query_remove: 'debug,internal'
      query_rename.uid: user_id
      query_set.source: litegate
      query_add.tag: migrated

routes:
  - name: legacy
    match:
      path_prefix: /legacy/
    use: [legacy-adapter]
    proxy: ["127.0.0.1:8080"]
```

The named form is the same capability as the route's inline `rewrite`, with the same semantics. A route can have only one active rewrite: inline and named rewrites cannot be combined, nor can a chain reference several rewrites. The named form uses the flat fields above, not the nested `path` / `query` structure of the inline form.

## 6. Encoding, signatures and troubleshooting

- The path regex matches the decoded path. After rewriting, `RawPath` is cleared and the path is re-escaped when forwarded; protocols that depend on the original percent-encoding should be checked carefully.
- Rewriting only the path doesn't re-encode the query. After query changes the query string is generated with standard URL encoding, so parameter order, spaces and percent-encoding may change.
- Components that verify signatures over the original URI should use `{original_uri}` / `{original_path}`, or avoid changing signed content. rewrite keeps the original URI in the request context; to hand it to a trusted backend, project it into a request header with the Action's `headers`; see the [Proxy documentation](../04-actions/proxy.md#8-url-rewrite-rewrite).
- With query operations configured, a malformed query string returns `400`; a URI over 16 KiB after rewriting returns `414`. When the path regex doesn't match, this rewrite's processing and checks are skipped.
- When the backend returns 404, first check the matched route, the upstream address and the final path. Enable debug logs to see `URL rewrite executed`, or check the effective chain with MCP's `lookup_route`.

Choosing a tool: `strip_prefix` for simply removing a prefix, `replace_path_regex` for a pure regex path replacement, rewrite for path and parameters, redirect to send the browser elsewhere, `try_files` for SPA or front-controller fallback. See [Path rewrite and redirect middleware](../05-middleware/path-and-redirect.md) and [Serve](../04-actions/serve.md).
