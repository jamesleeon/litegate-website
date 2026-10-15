# IDS 概览

IDS 是路由匹配后、Action 执行前的业务决策接口，适合按业务身份验证、注入可信头与动态选路。内核不内置 tenant_id、app_id、登录或 JWT 生命周期；插件自行查询业务系统并返回决定。

Forward 继续执行，Respond 直接响应，error 表示系统故障并受 fail_policy 控制。IDS 可保护所有 Action；Selector/Meta 动态实例选路只对 proxy 有意义。普通 HTTP 认证/路径处理使用 Middleware，业务身份与下游隔离可以使用 IDS。

默认优先选择 Go Provider，能管理数据库、HTTP、Redis 和缓存。实验性 WASM 仅用于计算，不提供通用 I/O，默认不编译。先定义业务拒绝、失败策略、隔离边界与 Header 白名单，再开发插件。

## 相关文档与代码

- [Provider authoring](ids-provider-plugin-guide.md)
- [Go / WASM](ids-go-vs-wasm.md)
