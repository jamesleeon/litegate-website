# 扫描防护与治理规则

scan_protection 默认关闭，是基于来源 IP 的内存风险检测与机会型缓解，不替代 WAF 或 DDoS 防护。状态和封禁每进程独立，当前没有 Redis 共享封禁。可信代理使用全局 real_ip.trusted_proxies；错误配置会将风险记到代理 IP。

基础字段：enabled 默认 false；block_duration 默认 1h；max_404_attempts 默认 5；observation_period 默认 1m；forbidden_paths 扩展敏感路径；block_direct_ip 默认 false，仅拦截裸 IP Host 且未命中站点的访问。

global_rules 提供 name、match.path_exact/path_prefix/path_contains、action、score、reason。动作支持 deny、tarpit、rate_limit、score、observe、allow。allow 不计分；终止动作即使 score 为 0 也执行。tech_profiles 定义技术栈路径；site_policies.<host>.deny_tech 引用这些名称，critical_action 定义处置。

流水线为 OnIngress → OnRouteResolved → OnRouteMiss → OnDecisionCommit。终止决策真正执行后才落账，避免 magic 路由兜底产生误记录。404 同一方法、Host、路径在窗口内去重。仅弱信号最多标记 suspicious；不同路径达到阈值可限速，不能直接 tarpit/封禁；强信号参与完整升级。

风险阈值为 5 suspicious、10 限速、15 tarpit、20 短封禁、30 长封禁。短封禁为 block_duration/6，至少一分钟；tarpit 约三秒。新 IP 首次风险至少 5 分才跟踪；空闲且未处置时风险会衰减。约五万 IP 状态上限、定期清理与有限事件队列约束资源。

Dashboard 或 POST /api/scan-protection/toggle?enabled=true/false 可在鉴权和 CSRF 校验后切换；运行时开关在 reload 后保留，配置 enabled 仅提供进程启动初值。先 observe，确认风险后再 deny。

```yaml
scan_protection:
  enabled: true
  block_duration: 1h
  max_404_attempts: 5
  observation_period: 1m
  block_direct_ip: false
  global_rules:
    - name: watch-admin
      match: {path_prefix: [/admin]}
      action: observe
      score: 0
      reason: admin_probe
```

## 相关文档与代码

- [Implementation](../../../../internal/middleware/scan_protection.go)
- [HA state](../10-deployment/ha-state.md)
