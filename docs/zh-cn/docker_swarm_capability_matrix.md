# Docker 与 Swarm 能力矩阵

更新于 2026-10-15。已实现接受的 P0/P1/P2 工作，下列边界仍适用。最终联合网关通过限定范围的三节点 Swarm、standalone Docker 和命名 L4 验收；已验证自有资源按完整 ID 清理，以及业务 Service 的 Spec 和版本未变。这不等于无限制功能对等或生产 HA。

只有已注册 DSL 字段能够配置网关，任意 Docker 标签都不是网关配置；YAML 支持也不自动等于标签支持。Docker 读取容器标签，Swarm 读取 Service 的 `deploy.labels`。IDS 必须具备已编译或注册的 provider、对应能力、配置资源和操作方授权；标签不能安装插件或授予访问权限。发现别名使用 `litegate.http.services.<name>.discovery.name`，顶层 `litegate.discovery.name` 不是同义配置。

| 能力 | YAML | Docker 标签 | Swarm 标签 | 实现行为和边界 |
|---|---|---|---|---|
| HTTP Router/Service 与匹配 | 支持 | 支持 | 支持 | 已知属性、引用校验、Host/路径/Header/Query 规则 |
| IDS 与响应钩子 | 支持 | 支持 | 支持 | Provider/options/失败策略/可信头投影/条件合并，能力和隔离校验保留 |
| 上游主动健康检查 | 支持 | 支持 | 支持 | 启用/超时/协议/gRPC service/阈值；启用检查并设置 `initialready=false` 后成功前不转发 |
| 重试 | 支持 | 支持 | 支持 | 额外尝试次数、状态码和方法条件、有限请求体重放；真实连接失败保留 502 |
| 粘性 Cookie | 支持 | 支持 | 支持 | 名称/TTL/Secure/HttpOnly/SameSite/path/domain，普通和升级响应均覆盖；组合服务不支持 |
| Router TLS | 站点/监听器策略 | 有限已注册选项 | 有限已注册选项 | 按主机策略保留证书来源；不支持工作负载任意证书路径或命名 cert-resolver DSL |
| 上游传输 | 支持 | 支持 | 支持 | SNI/信任/超时/连接池，中央信任资源由操作方配置 |
| 共享资源 | 中央/本地 | 本地或显式 `@file` | 本地或显式 `@file` | Middleware/transport/TLS options 事务校验和重载，包含组合叶节点；无隐式跨 provider 查找 |
| 容器/Task 健康 | 取决于发现源 | 排除 starting/unhealthy | running Task 初始可用 | Task 状态不等于 HTTP 应用就绪；主动检查提供就绪门禁 |
| 零副本/删除/API 故障 | 可保留声明路由 | 最后容器消失即移除声明 | 零 Task 保留声明和空池 | HTTP 无可用实例返回 503；Service 删除移除路由；失败的完整快照保留最近成功状态 |
| 多端口/发布映射 | 每 Service 配置 | 类型化 TCP/UDP 宿主映射 | Task 网络端口 | 按容器端口和协议正确映射、IPv6、缺失映射排除、纯 UDP 发布；不宣称 Swarm 宿主发布端口解析 |
| 来源归属 | 显式 Docker 来源 | 每容器独立声明 | 物理 Service 拥有 Tasks/VIP | 同别名多个物理 Service 的显式查询拒绝歧义，指定实例也不绕过；保留 standalone 分组和旧别名聚合 |
| 网络与 VIP | 操作方 catalog | 容器网络 | 显式 Service VIP | 校验非 ingress 网络；歧义/缺失网络、DNSRR、缺失 VIP 不回退到 Task；零 Task 仍为空 |
| VIP 选择限制 | 强制 | 不适用 | 强制 | 静态实例条件拒绝编译；最终 IDS 条件/metadata/tags/gray 即使 override 也失败关闭 |
| 发现约束与 SSH | 操作方 catalog | 适用 | 适用 | 所有来源路径严格执行 Label/LabelRegex/`!`/`&&`/`||`；纯 Go SSH、known_hosts 固定密钥/主机 CA 校验、有界建立和清理、禁止 URL 密码 |
| HTTP 加权/故障转移图 | 静态/显式 Docker 叶 | 注册来源内的叶 | 注册来源内的叶 | 组权重独立于副本数；嵌套、严格引用/循环校验、叶节点独立端口/TLS/健康/池；其他显式来源 provider 不支持 |
| 组合请求治理 | 支持 | 支持 | 支持 | 一次 IDS/请求体缓冲/根超时/重试预算/最终钩子；硬条件与最终 IDS 取交集；未解析模板拒绝全请求 |
| 命名 TCP/UDP | Stream YAML | 已实现 | 已实现 | 原始 TCP/UDP、共享 TCP 端口 TLS SNI 透传、监听器原子准入已本地测试；真实 Swarm 更新/零副本/恢复和同别名来源隔离通过 |

组合仅支持普通 HTTP(S)。拒绝 Cookie 和子节点重试/超时；升级请求返回 503，gRPC/gRPC-Web 返回 RPC unavailable（14），不访问上游。主分支自身条件不会变成同级备用的授权边界；共同租户条件须在组或根节点声明。空/不健康主分支切换不消耗实际尝试，允许重试的失败共用根预算。

命名 L4 不支持 IDS、中间件、组合图和命名 TLS 终止/证书路径/解析器。操作方 TCP 附着必须明确处理非 TLS/无 SNI 流量及现有 HTTP/操作方路由；冲突准入被拒绝。共享传输上限作用于同一端点和传输策略，不是每 Service 独立配额。

## 与 Traefik Proxy OSS 3.4 的比较及剩余差距

实验固定 **3.4.4**，不比较 Hub/Enterprise。这是配置与行为比较，不是性能排名。

| 项目 | 差异和剩余边界 |
|---|---|
| 空上游 | LiteGate 声明 Swarm 路由返回 503；固定实验配置下 Traefik 返回 404。Traefik 可配置 `allowEmptyServices`，因此不是通用差异。[官方 Swarm provider](https://doc.traefik.io/traefik/v3.4/providers/swarm/#allowemptyservices) |
| 重试 | LiteGate 增加显式状态码/方法条件；Traefik Retry 收到任意 HTTP 响应后停止重试，不看状态码。[官方 Retry](https://doc.traefik.io/traefik/v3.4/middlewares/http/retry/) |
| 组合 | Traefik 3.4 文档中 Service WRR 支持 File/IngressRoute，failover 支持 File，不能推断 Docker/Swarm 标签对等。LiteGate 实现自身受限的命名组合标签。[官方 Services](https://doc.traefik.io/traefik/v3.4/routing/services/) |
| 证书 | Traefik 使用命名静态证书解析器并由路由引用。LiteGate 保留站点/auto-cert 来源和有限 TLS 选项；解析器及 provider 生态仍有差距。[官方 ACME](https://doc.traefik.io/traefik/v3.4/https/acme/) |
| L4 | Traefik 文档覆盖 TCP TLS 终止/透传和 UDP 路由；LiteGate 命名 L4 范围更窄。[官方 Routers](https://doc.traefik.io/traefik/v3.4/routing/routers/) |

IDS 是 LiteGate 专有契约，不是 Traefik 对等性测试。剩余差距包括更广组合来源、组合 Cookie/升级协议、命名 L4 终止与治理、证书解析器生态覆盖。不宣称吞吐基准、Manager/节点故障 HA 或生产可靠性结论。

## 最终验收证据

证据在本地 `artifacts/swarm-acceptance/`，下列路径不是公开下载链接。冻结 manifest 通过哈希记录未提交实现，仅基础 Git revision 不能识别这些版本。P8 网关 SHA-256：`c3f47480b84f9fb3246c5b8c49b6f85440cd00bca5760d7ea8ab49c9ebd56f7c`；后续修复不归属于该二进制。

- `baseline-report.json`：11 项中 8 项成功、3 项失败，失败证据保留。`docker-baseline-report.json`：standalone 发现/IDS/可信头。
- `p1-report.json`：分阶段生命周期/端口/零副本/健康/就绪/IDS 检查通过。`phase6-second-report.json`：中央资源重载、拒绝代际保留和恢复。主 JSON 不直接监听，实验使用现有被监听的重载触发路径。
- `phase7-fourth-report.json`：VIP/零副本/网络/DNSRR/约束/静态与 IDS 拒绝/恢复。`ssh-p7-final-report.json`、`ssh-p7-final-wrong-key-report.json`、`ssh-p8-report.json`：严格 SSH 证据。`phase8-report.json`：其冻结版本的副本无关权重与故障转移/不健康/零副本/恢复。
- 本地测试和 race 覆盖主机 CA、健康 GC/就绪、物理来源归属/歧义、纯 UDP 发布映射和命名 L4。警告捕获测试隔离到测试子进程，全部原断言保留；修复的是测试干扰，不是生产日志。
- 早期失败 SSH/VIP/中央资源报告保留。旧自有 Service 的 VIP 拒绝流量，而其 Tasks 和新建同 Spec 夹具正常；重建夹具后分阶段 VIP 验收通过。该观察不能证明 LiteGate 缺陷或 Docker 根因。
- 下列六组实机验收使用同一个 `gateway:p9` 二进制，SHA-256 为 `15787bbd63ffab562cb2de866353f9282557e9b743191a65def398afe3a1068b`：`phase9-second-report.json`（命名 TCP/UDP/共享 SNI/同别名隔离）、`final-swarm-second-report.json`（11/11）、`final-docker-report.json`（3/3）、`final-central-report.json`、`final-vip-report.json`、`final-graphs-report.json`，均通过。`final-ssh-report.json` 使用单独记录哈希的连接器探针，验证三个 Manager 的严格固定密钥连接及错误密钥拒绝。
- 健康比较保留早期观察：Traefik 曾向新启动、尚未就绪的 Task 转发并收到 HTTP 200。最终具有健康状态证据的不可用窗口中，LiteGate 和 Traefik 均返回 503；不能由此宣称 Traefik 总会向不健康 Task 转发。
- 完整 Go `./...`、十一包 race、vet 和最终 46 项 Python 实验测试通过。只读审核保存在 `requirements-audit-source-fixes.md`、`requirements-audit-phase9-live.md`、`requirements-audit-final-live-progress.md` 和 `requirements-audit-health-final.md`，各自审核范围及早期失败观察仍属于证据。
- `final-cleanup-report.json` 通过：按完整 ID 移除自有 Service/network/config，三个节点均无自有 Service/network/config/container 清单残留，本地状态清除，业务 Spec 和版本与基线一致，节点保持 Ready/Active。首次短 ID 清理失败及修复恢复保存在 `final-cleanup-first-failed-report.json` 和 `final-cleanup-state-recovery.json`。
- 保留自有镜像和 owner 范围临时构建资产用于复现；清理不代表磁盘剪枝。`phase10-source.zip` 和 `phase10-build.json` 冻结文档及实验/测试更新后的最终源码与 manifest。实际 P10 构建得到的 SHA-256 与上文实机验收 P9 网关完全一致，是已验证的同一二进制，不是新生成但未经验证的程序。

参见[隔离验收实验](../../examples/swarm-acceptance/README.md)。验收完成后，本矩阵列出的功能限制仍适用。
