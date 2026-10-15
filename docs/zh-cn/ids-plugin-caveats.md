# IDS 插件约束与排错

Provider 是并发单例，不为每请求新建数据库连接，也不共享请求对象。所有外部调用使用传入 context；宿主超时后插件仍可能运行，不能忽略取消或无限创建 goroutine。缓存设置容量、TTL、失败语义和租户隔离键；并发回源使用受控合并。

读取请求 Body 后恢复；业务拒绝返回 Respond，系统故障返回 error。fail_policy: allow 只对系统错误放行，应评估安全边界。Selector 保证硬隔离，Meta 不可替代；Header 必须显式白名单并覆盖不可信输入。

动态配置和密钥轮换需考虑缓存过期；NotifySubscriber 只提供在线信号和 Resync，重连后主动重同步。调试先检查注册、绑定、options、真实请求和实例状态，不记录敏感内容。

## 相关文档与代码

- [Provider guide](ids-provider-plugin-guide.md)
- [Helper kit](../../pkg/plugin/idskit)
