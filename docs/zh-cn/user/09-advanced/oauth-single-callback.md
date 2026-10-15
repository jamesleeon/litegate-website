# 单一 OAuth 回调地址选路

OAuth 身份服务只登记一个回调地址时，可以在该地址上按原始请求条件或经过验证的业务身份选择后端。路由匹配与 rewrite 是不同阶段，不能先改写再期待网关重选路。

state 参数必须由应用或可信 Provider 验证签名、过期和会话绑定；网关不会自动把用户传入的 tenant、redirect_uri 或 state 变成可信授权。使用 IDS Selector 做租户硬隔离，并对白名单身份头做投影。

保留应用需要的 code/state 查询参数；通过 query.remove/set 改写时避免误删。验证回调重放、过期、错租户、无匹配实例和登录返回地址。OIDC 内置流程与业务应用 OAuth 回调不能混为一套配置。

## 相关文档与代码

- [OIDC](../05-middleware/oidc.md)
- [Rewrite](../03-configuration/rewrite.md)
- [IDS](../05-middleware/ids-governance.md)
