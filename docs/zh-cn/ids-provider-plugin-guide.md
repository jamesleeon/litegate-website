# IDS Provider 开发与上线

实现 pkg/plugin.IDSProvider，使用 RegisterIDSProvider 注册 Factory、Description、Options 描述与 Validate；另注册同名 Kind: ids 的 Manifest，以便 CLI 显示版本和配置示例。Manifest 与 IDS Options 元数据不是一份对象，inspect 不自动展示完整 Options Schema。

在构建入口空导入包或用 litegate build --with，然后将路由 ids.provider 绑定注册名。options 提供非敏感策略和引用，每请求读取；plugin_config.path/watch 提供进程侧动态配置。DB/Redis/HTTP 客户端由单例管理，密钥轮换应清理旧缓存与客户端。

使用 Dependencies 的日志/配置能力，不直接读取 Router。可用 pkg/plugin/idskit 的有界缓存、IdentityLoader 和响应工具减少并发回源与缓存键错误；不能假设任何 Provider 都使用共享 Redis。输出 Forward/Respond，系统 error 由默认 deny 处理。输入 Body 需恢复，Header 投影需白名单。

先用 plugins list/inspect/doctor 确认注册，再通过 Dashboard JSON、日志、指标与真实请求确认实例化和绑定；注册成功不等于调用成功。监控超时、panic、并发拒绝、熔断和实际未退出调用。所有生命周期/通知方法需并发安全，遵守取消；不要记录密钥、完整签名或原始 Body。

## 相关文档与代码

- [IDS SDK](../../pkg/plugin/ids.go)
- [Helper kit](../../pkg/plugin/idskit)
- [MD5 compatibility provider](openapi-md5-ids-plugin.md)
- [SaaS login api logout refresh 与响应关联](ids-saas-session-guide.md)
