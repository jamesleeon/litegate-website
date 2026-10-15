# 路径改写与重定向

这些命名中间件在 RequestTransform 阶段执行，早于安全、限流与认证。strip_prefix、rewrite、replace_path_regex 修改内部请求；redirect_scheme、redirect_regex 向客户端返回跳转。

strip_prefix 使用 prefixes，剥离第一个匹配前缀，空路径回退 `/`；每项必须以 `/` 开头。rewrite 的命名字段为 path_pattern、path_target、query_set.<name>、query_add.<name>、query_rename.<name>、query_remove。replace_path_regex 使用 regex/replacement，只改路径。

redirect_scheme 使用 scheme、port、permanent。redirect_regex 的 regex 匹配完整绝对 URL，包括协议、Host、路径和查询；不要把它当作仅路径匹配。正则使用 Go 语法。改写不会触发重新选路。

## 相关文档与代码

- [Rewrite](../03-configuration/rewrite.md)
- [Redirect action](../04-actions/redirect.md)
- [Pipeline](pipeline.md)
