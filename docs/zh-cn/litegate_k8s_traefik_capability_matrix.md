# LiteGate Kubernetes 能力对标与提升规划

评估日期：2026-10-15。

以 Traefik 开源版为对标对象，梳理 LiteGate 在 Kubernetes 场景中的当前基础、提升方向和验收标准。重点是 Kubernetes 资源表达、标准一致性和控制面可靠性，同时保留 LiteGate 的原生 WebServer 与性能优势。

本文是对标与提升规划，不是完整支持承诺或 Gateway API 认证报告。当前使用方式与边界见 [Kubernetes 部署与使用](litegate_k8s_usage_guide.md)和 [Kubernetes 当前能力与边界](litegate_kubernetes_capabilities.md)。

以下规划表保留实施前基线；本轮交付和环境复验状态见文末“统一验收对照”，详细构建身份、测量口径和历史失败见[优化与验收记录](litegate_k8s_optimization_report.md)。

## 评估口径

- 对比时固定 LiteGate、Traefik、Kubernetes 和 Gateway API 版本；Traefik 商业版能力单独比较。
- “已实测”只表示相关场景经过验证，不代表该能力的全部边界均已覆盖。
- “已有实现”表示代码中存在实现，仍需结合配置入口和实际行为验收。
- “待验证”表示证据不足，不等于功能不存在。
- 优先级：P0 为生产可靠性基础，P1 为主要功能补齐，P2 为规模与产品体验提升。
- 修复后的源码、测试二进制和实际部署镜像需要分别核对，不能将源码修复直接视为所有运行实例已更新。

## 标准与可靠性

| 优先级 | 能力 | LiteGate 当前状态 | 需要提升的内容 | 验收标准 |
|---|---|---|---|---|
| P0 | Gateway API 标准一致性 | 主链路已实测；尚无完整 conformance 结果 | 固定支持版本，建立逐项兼容清单 | 官方测试逐项记录通过、失败、不支持及原因 |
| P0 | 不支持配置的明确拒绝 | 资源结构为手写子集 | 审查未知过滤器、字段和引用，避免静默忽略关键配置 | 不支持的配置按规范报告状态，实际行为与状态一致 |
| P0 | List/Watch 异常恢复 | 已有 resourceVersion、BOOKMARK、410 重列举及退避 | 系统验证断连、429、临时认证失败和权限恢复 | 恢复后自动收敛，无需重启；不存在永久漏更新 |
| P0 | 配置发布与监听器对账 | 晚到证书及无 HTTPRoute 场景已有修复和实测 | 扩展创建、删除、乱序到达和并发更新测试 | 路由、证书、监听状态一致；无请求误转发 |
| P0 | 多副本与选主 | Lease 已实现，切换有实测 | 验证网络分区、续租失败、旧 leader 恢复 | 状态写入权限正确，业务代理按设计继续运行 |
| P0 | TLS 策略与失败拒绝 | CA/SNI、端口优先级、缓存缺失拒绝已验证 | 补证书撤销、过期、错误引用和组合场景 | 无明文降级；策略变更、删除后正确恢复 |
| P0 | 多租户隔离 | ReferenceGrant 撤销等场景已实测 | 完整验证 Namespace、AllowedRoutes、Secret 引用及多个控制器共存 | 未授权路由和证书引用始终无法生效 |
| P0 | Kubernetes 版本兼容 | 当前主要在单套 K3s 环境验证 | 建立明确的支持版本矩阵 | 在声明支持的版本上自动运行安装、路由和升级测试 |

Traefik 已公开 Gateway API 支持范围、conformance 报告入口和 Kubernetes 版本策略，可作为交付基线：[官方支持说明](https://doc.traefik.io/traefik/reference/install-configuration/providers/kubernetes/kubernetes-gateway/)。该页面随版本更新，验收时应记录对应版本。

## Kubernetes 资源配置能力

数据面已有某项功能，不等于用户已经能够完整地通过 Kubernetes YAML 配置该功能。以下任务重点补齐资源结构、引用关系、状态反馈与动态更新行为。

| 优先级 | 能力 | LiteGate 当前状态 | 需要提升的内容 | 验收标准 |
|---|---|---|---|---|
| P1 | 可复用中间件与 ExtensionRef | 常用过滤器已有实现；尚未建模 ExtensionRef | 设计可引用、可组合的 LiteGate 中间件资源 | 多条路由复用；修改、删除、引用失败均正确生效 |
| P1 | 后端级过滤器 | 当前 HTTPBackendRef 未建模 filters | 支持对不同 backend 分别配置过滤器 | 灰度后端可使用不同请求头，互不污染 |
| P1 | 标准超时配置 | 自定义策略有 timeout；HTTPRoute 标准字段未完整建模 | 对齐目标版本的标准超时语义 | 能区分请求和后端超时，并验证取消与资源释放 |
| P1 | 重试与流量治理 | 自定义策略已有重试、限流、熔断、并发限制 | 补齐 Kubernetes 配置表达、冲突规则和组合测试 | 重试次数、触发条件、请求体重放和多副本限流语义明确 |
| P1 | 认证能力资源化 | 数据面已有多种认证；当前 TrafficPolicy 未完整暴露 | 将认证策略、Secret 引用和失败行为接入 Kubernetes 资源 | 常用认证场景可只用 YAML 配置，凭据轮换无需重启 |
| P1 | BackendTLSPolicy 扩展字段 | 已支持 CA、Hostname、System CA；未建模 subjectAltNames | 按声明的支持版本补齐字段与校验 | 正确匹配证书身份；错误证书失败拒绝 |
| P1 | gRPC 与长连接 | GRPCRoute 有代码实现；完整实测证据不足 | 补 unary、双向流、WebSocket、SSE 验证 | 验证 trailers、取消、超时、滚动更新和连接排空 |
| P1 | 灰度、镜像与会话保持 | 权重路由已实测，镜像有实现；会话保持需审查 | 分别明确支持范围并补测试 | 权重分布符合预期；镜像故障不影响主请求；会话规则可验证 |

Traefik 提供通过 ExtensionRef 引用 Middleware，以及 backend 级过滤器配置。这两项可直接列入功能补齐任务：[官方配置示例](https://doc.traefik.io/traefik/reference/routing-configuration/kubernetes/gateway-api/)。其余扩展字段应逐项核对双方固定版本，不推定 Traefik 支持所有 Gateway API 扩展。

## 规模 运维与一体化部署

| 优先级 | 能力 | 当前基础 | 提升目标与验收 |
|---|---|---|---|
| P1 | Kubernetes 控制面可观测性 | 已有通用日志和监控 | 展示 Watch 健康、同步延迟、配置拒绝原因、最近成功对账时间；能定位路由未生效的原因 |
| P1 | Helm 与滚动升级 | 已有 Chart、RBAC、PDB | 自动验证安装、升级、回滚、优雅退出；持续流量下统计错误与中断 |
| P2 | 大规模配置收敛 | 当前以三节点功能测试为主 | 分级测试大量 Route、Service、EndpointSlice；记录收敛 P95/P99、API 请求量、CPU、内存 |
| P2 | 长时间稳定性 | 主要为短时验收 | 持续运行并反复扩缩容、轮换证书、注入故障；检查内存、goroutine、连接和文件描述符 |
| P1 | WebServer、SPA 与 Kubernetes API 一体化 | 已实测，是 LiteGate 的差异化能力 | 提供正式 Helm 示例、前端发布回滚、多副本文件一致性和浏览器端到端测试 |
| P1 | 静态配置与动态路由融合 | 已跑通，证书合并问题已有修复 | 明确优先级、路径占用和 API 失效行为，避免 API 请求误落到 SPA |
| P2 | H2 patch 与性能回归 | 已有根因分析及重复测量 | 固定补丁来源和升级流程；覆盖协议正确性、流式响应，并将性能回归纳入发布检查 |

性能与功能成熟度分别评价。H2 性能评估应采用后续补丁测试结果，不能继续以早期基线的领先幅度代表补丁版本；跨轮次结果不能直接拼算为同轮竞品对比。

## 实施顺序与覆盖率

1. 建立标准测试和异常恢复基线，把现有功能的正确性固定下来。
2. 补齐 ExtensionRef、后端过滤器、超时和认证资源化，提高纯 Kubernetes YAML 的可用性。
3. 开展规模、升级和长期稳定性验证，同时完善一体化前端部署体验。

覆盖率至少分为三个指标，不能用一个未经定义的百分比替代：

| 指标 | 计算口径 |
|---|---|
| 功能实现率 | 固定对标清单中，已完成数据面实现的项目占比 |
| Kubernetes 资源可配置率 | 固定对标清单中，可通过 Kubernetes 资源完整配置的项目占比 |
| 验收通过率 | 固定测试集中，通过的测试项占比；未运行项单独列出 |

每项任务保留支持版本、状态、测试入口和结果。功能大类不能代替字段级兼容性，也不能用单元测试通过率替代 Gateway API conformance。

## 相关文档与代码

- [Kubernetes 部署与使用](litegate_k8s_usage_guide.md)
- [Kubernetes 当前能力与边界](litegate_kubernetes_capabilities.md)
- [Kubernetes Provider](../../internal/provider/k8s/provider.go)
- [Gateway API 资源类型](../../internal/provider/k8s/types_gateway.go)
- [LiteGateTrafficPolicy 资源类型](../../internal/provider/k8s/types_policy.go)
- [Gateway API 路由转换](../../internal/loader/gateway_translator.go)
- [Kubernetes 实验验收脚本](../../examples/k8s-acceptance/)

## 2026-10-15 首轮实施记录（历史）

已补齐同命名空间 `ExtensionRef → LiteGateTrafficPolicy`、后端请求/响应头过滤器、HTTPRoute 标准超时，以及 Basic Auth/JWT 的 Secret 引用和动态轮换。已修复 Watch 权限失败后永久退出、无效证书继续使用旧缓存，以及内部配置复制与发布指纹遗漏等问题。

该首轮阶段当时尚未完成官方 conformance、subjectAltNames、跨版本、长连接、规模和长期稳定性验收。后续交付状态见下表，原始阶段记录作为历史保留。

## 2026-10-15 统一验收对照

候选 `complete-20261015-12-patched` 已通过统一计划全部 28 阶段、真实浏览器五态及完整两小时长稳验收。逐阶段构建身份、原始报告和全部 23 项映射见[验收证据索引](../../examples/k8s-acceptance/results/20261015/complete/final12/acceptance-evidence-index.json)。下表的“通过”限定为所列范围与环境，不扩展为所有 Gateway API 字段支持或竞品完全替代承诺。

| 序号 | 矩阵项目 | 本轮交付及环境证据 | 范围与边界 | 状态 |
|---|---|---|---|---|
| 1 | Gateway API 标准一致性 | 原版 v1.4.1 官方 HTTP 33、GRPC 13、TLS 11；7 项声明扩展对应 8 测试，分别零失败/跳过 | profile 共享用例，不能合计为独立测试数；没有宣称标准认证 | 通过 |
| 2 | 不支持配置的明确拒绝 | strict API 校验、保留字段拒绝、两副本有效→无效匹配撤销→恢复 | 不支持的匹配撤回旧转发；已知匹配上的不支持 filter 失败关闭 | 通过 |
| 3 | List/Watch 异常恢复 | 断连、410/429/401/403、真实 RBAC 撤销与恢复，`faults` 9 场景 | 隔离代理注入和真实 RBAC 场景，不推定全集群灾难恢复 | 通过 |
| 4 | 配置发布与监听器对账 | 五轮扩缩容 HTTP/TLS 各 1694 次新连接零错；listener-isolation、持续 churn | 首次缓存、Catalog 提交及实际监听发布成功后才就绪；保留 TLS 无路由证书占位 | 通过 |
| 5 | 多副本与选主 | Lease 分区/恢复、状态写入 fencing、UID/RV CAS、独立控制器共存 | Lease 协调状态写者，不共享所有数据面计数 | 通过 |
| 6 | TLS 策略与失败拒绝 | CA/SNI、过期/错误证书、Secret 轮换/撤销、端口证书隔离 | 无明文降级；不是 CRL/OCSP 撤销服务实现 | 通过 |
| 7 | 多租户隔离 | Namespace/AllowedRoutes/ReferenceGrant、跨 namespace 后端/证书/镜像、控制器归属 | ExtensionRef 限同 namespace，未授权引用失败关闭 | 通过 |
| 8 | Kubernetes 版本兼容 | 主环境 K3s 1.36.5；隔离 K3s 1.35.5/1.34.5 安装、配置升级、回滚各 30 请求通过 | 限实际 K3s 版本与场景，不代表全部发行版 | 通过 |
| 9 | 可复用中间件与 ExtensionRef | 同 namespace LiteGateTrafficPolicy 引用、修改、删除和失败恢复 | 明确支持的项目策略，不支持任意第三方 Middleware | 通过 |
| 10 | 后端级过滤器 | backend 头部/重写/镜像/策略，重复 Service 引用保持过滤器身份 | 选中后端独立生效；支持集合见 CRD 与能力文档 | 通过 |
| 11 | 标准超时配置 | HTTPRoute request/backendRequest、取消、deadline、官方超时扩展 | 区分预算，零值禁用；流协议按各自已测语义 | 通过 |
| 12 | 重试与流量治理 | 重放/退避；双副本逐 Pod 限流、并发拒绝释放、熔断与重试组合 | 限流/并发/熔断为副本本地计数；熔断按上游 attempt 计数 | 通过 |
| 13 | 认证能力资源化 | Basic/JWT Secret、JWKS、OIDC PKCE/nonce、ForwardAuth；轮换/删除/Redis 故障恢复 | OIDC 多副本依赖共享 Redis 与一致加密密钥 | 通过 |
| 14 | BackendTLSPolicy 扩展字段 | DNS/URI subjectAltNames、独立 SNI、CA ConfigMap 轮换，SAN 7 场景 | 按声明字段验证链与身份，错误证书拒绝 | 通过 |
| 15 | gRPC 与长连接 | 24 客户端场景、h2c/grpcs/trailers/取消；20 秒双向流、WS/SSE 跨升级 | 记录实际时长与排空边界，不承诺无限长流永不中断 | 通过 |
| 16 | 灰度、镜像与会话保持 | weighted 7 场景、无效后端概率、镜像隔离、Cookie/Header persistence | 镜像支持 percent，fraction 明确拒绝；会话不等于共享后端健康状态 | 通过 |
| 17 | Kubernetes 控制面可观测性 | List/Watch/状态/拒绝/选主/通知指标，故障及 churn 原始采样 | 标签有界；通知耗时与请求可见收敛分别测量 | 通过 |
| 18 | Helm 与滚动升级 | 3 场景；持续 API 898 请求零错，三类 20 秒长连接保持，共享 key 保留 | CRD 需显式升级；PDB 不单独证明任意停机无损 | 通过 |
| 19 | 大规模配置收敛 | 两套模型：Route-only，以及各 100/500/1000 Route+Service+EndpointSlice，各档 100 次变更 | 单控制器测量；P95/P99 包含 patch 与轮询，不是整批创建时间 | 通过 |
| 20 | 长时间稳定性 | 全部 300 次 Route 变更后，7200 秒 HTTP/TLS、六轮证书/扩缩容/后端故障；71,700 成功，非预期错误及传输异常零次 | 同一稳定进程静置 RSS 增加 2.34 MiB，goroutine/FD/socket 无增长；限本次两小时合同 | 通过 |
| 21 | WebServer、SPA 与 Kubernetes API 一体化 | 不可变前端、两副本文件哈希、v1/v2/回滚；真实浏览器五态通过 | 浏览器使用本地桥接固定 Host；Host 路由另由集群测试验证 | 通过 |
| 22 | 静态配置与动态路由融合 | API 删除返回 JSON 503、SPA 仍 200、恢复正确；混合来源撤回回归 | Gateway 撤回与原生 last-good 分别处理，API 不误落 SPA | 通过 |
| 23 | H2 patch 与性能回归 | 同源 stock/overlay、同一 litegate-be 节点交替三轮，正确性及回归预算通过 | 仅本轮实验室同源回归，不拼接历史轮次推算 Traefik 优势 | 通过 |
