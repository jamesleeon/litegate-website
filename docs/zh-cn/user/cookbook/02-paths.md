# 路径：匹配与改写

路由先按原始路径选中处理分支，再执行 rewrite。改写不重选路，也不改变浏览器地址；redirect 才产生客户端跳转。

用 Go 正则与明确捕获组适配后端路径，query 字段单独处理查询。路径前缀、精确路径、通配条件与优先级按 V2 指南配置，不能只靠文件书写顺序。

## 相关文档与代码

- [Rewrite example](../03-configuration/rewrite.md)
- [Matchers](06-matchers.md)
- [Priority](../02-concepts/routing-priority.md)
