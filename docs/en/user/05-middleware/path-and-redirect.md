# Path transformations and redirects

These named middleware run in RequestTransform, before security, rate limiting and authentication. strip_prefix, rewrite and replace_path_regex modify internal requests; redirect_scheme and redirect_regex return redirects to clients.

strip_prefix uses prefixes, removes the first matching prefix and falls back to `/` for an empty path; every entry must start with `/`. Named rewrite fields are path_pattern, path_target, query_set.<name>, query_add.<name>, query_rename.<name> and query_remove. replace_path_regex uses regex/replacement and only changes the path.

redirect_scheme uses scheme, port and permanent. redirect_regex matches the complete absolute URL, including scheme, Host, path and query, rather than only the path. Expressions use Go syntax. Transformations do not trigger route selection again.

## Related documentation and code

- [Rewrite](../03-configuration/rewrite.md)
- [Redirect action](../04-actions/redirect.md)
- [Pipeline](pipeline.md)
