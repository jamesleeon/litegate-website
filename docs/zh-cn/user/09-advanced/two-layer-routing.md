# 选上游与改路径

把选路和 URL 改写分别处理：原始请求先匹配 Site/Route，确定当前 Action/Service；rewrite 再修改发往这个上游的路径和查询。改写不会再次匹配路由。

例如先按 Host、Path、Header 或 Query 选择 tenant-a 后端，再把 /legacy/orders 改为 /api/orders。若选路依赖业务身份，使用 IDS Provider 返回 Selector；Meta 只表达隔离池内的版本偏好。

调试时依次确认原始请求、命中的路由、Service/Selector、rewrite 结果、实际目标地址。不要用路径改写模拟跨路由跳转；需要浏览器更换 URL 时使用 redirect。

## 相关文档与代码

- [Rewrite](../03-configuration/rewrite.md)
- [IDS](../05-middleware/ids-governance.md)
- [Routing priority](../02-concepts/routing-priority.md)
