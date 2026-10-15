# 配置发布控制面

发布控制启用后，Dashboard 保存/删除先形成草稿，校验和检查 diff 后显式发布，并保留历史供回滚。它管理配置版本，不是请求按百分比灰度分流。

dashboard.enabled 与 dashboard.release_control.enabled 都需打开，配置后端和历史存储需可读写。支持本地文件、Consul 与 LiteMesh；roles.config_watch 决定配置后端，仅开启服务发现不切换配置存储。KV 模式用站点前缀下 _release.json 的 CAS 提交快照。

流程为 draft → validated → publishing → active/active_with_warnings 或 failed；回滚创建新的 active 版本并保留历史。已有工作草稿再次修改会重置到 draft。发布前验证错误、告警与差异；发布后确认实际运行状态，失败时检查日志与文件/KV 权限。不要把外部直接改文件也描述为必经 Dashboard 草稿。

```yaml
dashboard:
  enabled: true
  port: 9999
  username: admin
  password: REPLACE_WITH_STRONG_PASSWORD
  release_control:
    enabled: true
```

## 相关文档与代码

- [Implementation](../../internal/release)
- [Dashboard](user/08-observability/dashboard.md)
