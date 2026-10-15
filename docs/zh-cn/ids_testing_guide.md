# IDS Provider 验收指南

验收当前统一 Provider 契约，不用历史固定 Redis Session/Cookie/Key 格式当内置能力。先构建包含插件的二进制，用 plugins list/inspect/doctor 确认注册与元数据，再把 ids.provider 绑定路由并进行配置预检。

验证 Forward 默认下游与白名单 Header，Respond 的状态/Body，系统 error 的 fail_policy。业务拒绝在 allow 策略下也不能放行。验证静态/动态 Selector 冲突、Meta 缺失仅回默认池、错租户与空候选池；同时确认 serve/respond 也受到 IDS 保护。

使用真实请求 Body 验证读取后恢复；并发测试 Provider 单例、context 取消、超时、panic、熔断与并发上限。配置热更新、密钥轮换、缓存失效和可选 Resync 需单独验证。检查日志/指标，不记录密钥和完整签名；注册可见不等于业务链路已运行。

```bash
litegate plugins list
litegate plugins inspect ids/openapi-md5
litegate plugins doctor
go test ./internal/middleware ./pkg/plugin/...
```

## 相关文档与代码

- [Provider guide](ids-provider-plugin-guide.md)
- [Guard tests](../../internal/middleware/ids_guard_test.go)
- [Governance tests](../../internal/middleware/ids_governance_test.go)
