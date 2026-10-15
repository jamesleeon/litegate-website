# Kubernetes 能力矩阵优化与验收记录

日期：2026-10-15。对应[能力矩阵](litegate_k8s_traefik_capability_matrix.md)的全部 23 项任务。候选 12 已通过统一计划全部 28 阶段、官方测试、真实浏览器及独立扩缩容复验，完整两小时长稳通过。候选 10 的启动就绪缺口和候选 11 的旧路由未撤销问题均已修复，原失败证据保留。

## 本轮实现

| 范围 | 具体变化 |
|---|---|
| 标准一致性 | 固定 Gateway API v1.4.1；修复 generation、listener conditions、匹配优先级、重复条件、响应头操作及通配域名语义 |
| 控制面 | Watch 410/429/401/403 恢复、真实 RBAC 撤销恢复、Lease 分区、UID/resourceVersion CAS、保留第三方 parent 状态、控制器归属变化后的发布过滤 |
| 有界发布 | provider、catalog、状态对账均有最大批次等待时间，持续变更不会无限推迟配置 |
| 启动就绪 | 全部启用 Kubernetes 资源首次 List 应用完成、Catalog 首次成功提交、监听与路由重载成功后才放行 readyz；后续租户坏配置不会撤下已就绪副本 |
| 撤销语义 | 有效 HTTPRoute 改为不支持的匹配后撤销旧 Gateway 转发；保留同域有效路由及合法 HTTPS 无路由证书占位；真实 native 标签混合来源回归通过 |
| 监听与证书 | 路由绑定真实 HTTP/HTTPS 入口；同域名不同端口独立证书、轮换及撤销；共享默认/额外 HTTPS 端口的 TLS 透传；协议冲突明确拒绝 |
| TLS 后端 | 独立 CA/SNI、DNS/URI subjectAltNames、CA ConfigMap 动态轮换、过期/错误证书与策略撤销失败关闭 |
| 资源治理 | 同 namespace ExtensionRef 复用；后端级头部/重写/镜像/策略；标准请求与后端超时、重试退避与请求体重放、Cookie/Header 会话保持 |
| 认证资源 | Basic/JWT Secret、JWKS、OIDC PKCE/nonce/双副本回调、ForwardAuth、Secret 轮换/删除及 Redis 故障恢复 |
| 协议与升级 | GRPCRoute、HTTPRoute h2c、TLS gRPC、双向流/trailers/取消、WebSocket/SSE；应用退出不提前取消存量请求，长连接有界排空 |
| Helm 与一体化 | Secret 运行配置、共享密钥升级保留、不可变前端挂载、多副本文件一致、前端回滚、API JSON 503 兜底、实际浏览器验证 |
| 发布验收 | 统一计划、输入哈希、逐次日志与退出码、运行镜像身份校验、跨版本安装升级回滚、两套规模模型、完整两小时稳定性、同源 H2 回归 |

匹配顺序为 Exact、最长段前缀、method、header 数量、query 数量；相同条件按创建时间、namespace/name 和规则顺序稳定选择。等价前缀的尾随斜杠不改变优先级。Header 的等价名称不区分大小写，只考虑首条；query 名称区分大小写，只考虑首条。无效后端的错误响应不得回显注入给上游的凭据。

## 环境和构建身份

- 主环境：192.168.50.32、.33、.34，K3s v1.36.5+k3s1，Linux amd64。
- Gateway API CRD 和原版官方测试模块：v1.4.1 experimental。
- 工具链：Go 1.27.1；CGO 关闭；trimpath 开启，buildvcs 关闭。
- 最终候选：litegate-lab:complete-20261015-12-patched。
- 二进制 SHA256：f52a1979863ba74974715babfa481d3d304b7e12e590fa1388ff0f6f88477336。
- Docker config/实际运行 imageID：5c6d105cb7c7a6ca5431e15fe3ca5d77604b13bd1b48dd803d8fb129e9ba7033。
- 源码超集指纹：a2a36f9696f47cd2a614c00febe1d3ab1d66b1cdc614f243fbbd5bb1574cf13e。
- 同源 stock 镜像用于 H2 对照；H2 overlay 标记为 h2coalesce.1。
- 621 个非测试 Go 源码文件的冻结清单、34 项自动枚举的嵌入资源/模块输入、工具链补丁、二进制、归档和 Docker config 摘要分别记录于[构建证明](../../examples/k8s-acceptance/results/20261015/complete/build-image12.json)。源码清单覆盖主程序并包括样例和工具，是构建来源的超集指纹，不表示主二进制编译了全部 621 个文件。

运行身份阶段直接检查归档内二进制摘要与就绪 Pod imageID。镜像标签不独立构成构建证明。源码修改不能借用旧镜像结果；历史镜像 1–5 未应用 H2 overlay，不作为该补丁的验证证据。

本地冻结源码、当前工作区和远端验收源码副本逐文件核对一致，55 项验收输入摘要匹配，见[源码与依赖校验](../../examples/k8s-acceptance/results/20261015/complete/source-audit-image12.json)。本地 Windows/amd64 全量 Go 测试 71 个包零失败，四包启动/撤销相关竞态检查通过；新增真实 native 标签混合来源回归另跑完整 loader 包通过，见[本地验证记录](../../examples/k8s-acceptance/results/20261015/complete/local-verification-image12.json)。`go mod verify` 在相同 go.mod/go.sum 依赖输入上通过。

## 最终候选验收

统一计划全部 28 阶段通过。长稳成功退出后，以原计划执行不带 `--only` 的全阶段 `--resume`，28 项均匹配原成功证据及输入指纹，退出码为零。逐阶段结果见[完整计划汇总](../../examples/k8s-acceptance/results/20261015/complete/final12/stages/summary.json)，全部 23 项任务与原始报告的关联见[证据索引](../../examples/k8s-acceptance/results/20261015/complete/final12/acceptance-evidence-index.json)。

| 原版官方 v1.4.1 范围 | 通过 | 失败 | 跳过 |
|---|---:|---:|---:|
| HTTP core | 33 | 0 | 0 |
| GRPC core | 13 | 0 | 0 |
| TLS core | 11 | 0 | 0 |
| 七种声明扩展对应测试 | 8 | 0 | 0 |

各 profile 共享 Gateway 测试，声明扩展执行也重跑部分核心项，不合计为独立用例总数。HTTP 第二次执行快照仅包含候选 12 的非终止中 Pod；首次执行成功时包含旧副本终止过程的历史观察，因此保留原记录并以第二次作为最终版本归因证据。

集群脚本分别通过：基础 21、进阶 13、矩阵 8、SAN 7、治理 9、认证 6、共存 2、拒绝/恢复 5、监听隔离 5、双副本治理边界 4、Helm 3、故障 9、权重 7。协议脚本的三个外层步骤包含 24 个实际客户端场景；持续背景变更中的六次关键发布最大观测收敛 0.9773 秒，背景错误为零。各组保留独立报告，不把组数和内部场景混算为一个覆盖率。

候选 12 独立五轮 `1→2→1` 扩缩容中，HTTP/TLS 各 1694 次新连接全部成功；六个实际测量就绪 Pod 的 imageID 均与本轮归档一致。新 Pod 就绪至 443 首次成功探测之间没有连接错误；约 ±5ms 的首样本差在并行 50ms 探针的调度分辨率内。

Helm 升级与回滚期间持续 API 请求 898 次零错误，双向 gRPC、WebSocket、SSE 各 20 秒保持；两副本前端文件哈希一致、共享密钥保留。真实浏览器完成 v1/Connected、v2/Connected、API 删除后 Unavailable、恢复 Connected、回滚 v1/Connected 五态，见[浏览器记录](../../examples/k8s-acceptance/results/20261015/complete/final12/evidence/browser-attempt2/summary.json)。第一次手工检查单次加载读到升级前 v1，保留失败；第二次先验证两就绪副本哈希及入口连续十次版本收敛，再用相同 URL 完成全部断言，没有修改运行时或固定验收脚本。

K3s v1.34.5+k3s1、v1.35.5+k3s1 分别在 emptyDir、无 host mount/hostNetwork 的隔离环境执行安装、配置升级、回滚，每阶段 30 次请求通过，运行 imageID 均匹配候选 12。兼容 Pod 已按测试清理，主三节点环境保留。

持续运行合同为：100/500/1000 Route 各至少 100 次变更，7200 秒 HTTP/TLS 流量，至少六轮证书轮换、控制器扩缩容及后端故障恢复；初末静置采样比较同一 Pod UID 和进程的 RSS、goroutine、FD、socket。只有注入窗口的 HTTP 502/503/504 计为预期后端错误；TLS、传输异常和其他状态仍计为非预期错误。缩短的预检不能代替完整合同。

最终实测流量时长 7200.0008 秒（12:43:12 至 14:43:12），随后完成约 75 秒静置与 GC 采样。成功请求 71,700 次；故障窗口内预期响应 244 次（502 两次、503 共 242 次）；非预期错误零次，传输异常零次。六轮证书轮换、控制器 1→2→1 扩缩容及后端故障恢复全部通过。稳定副本 UID、PID 7 和进程启动时刻保持不变，运行 imageID 匹配候选 12。初末实际进程 RSS 从 78,147,584 增至 80,601,088 字节，增加 2,453,504 字节（2.34 MiB，小于预设 64 MiB）；goroutine 91→91、FD 30→30、socket FD 22→22。完整时序和增长判定见[长稳原始报告](../../examples/k8s-acceptance/results/20261015/complete/final12/evidence/scale-soak-attempt1/summary.json)。这些数据证明本次两小时合同通过，不构成无限时间无泄漏保证。

同一隔离控制器的 Route-only 模型在进入长稳前完成全部 300 次变更：

| Route 数量 | 变更样本 | P95 秒 | P99 秒 | 最大秒 | 窗口 API 读请求 |
|---:|---:|---:|---:|---:|---:|
| 100 | 100 | 0.6436 | 0.8165 | 1.1778 | 216 |
| 500 | 100 | 0.6655 | 0.7358 | 0.7380 | 229 |
| 1000 | 100 | 0.6373 | 0.7097 | 0.7353 | 229 |

另行测量 100/500/1000 个各类 HTTPRoute、Service、EndpointSlice，各档至少 100 次 EndpointSlice 变更。收敛包含 patch 请求及轮询时间；API 请求量来自隔离控制器代理，CPU/RSS 为实际进程采样，RSS 最大值为观测样本最大值。

| 各类对象数量 | 变更样本 | P95 秒 | P99 秒 | 窗口 API 读请求 | 窗口平均 CPU 核 | 窗口结束 RSS MiB |
|---:|---:|---:|---:|---:|---:|---:|
| 100 | 100 | 0.2075 | 0.2189 | 131 | 0.0360 | 48.43 |
| 500 | 100 | 0.2078 | 0.2119 | 30 | 0.0877 | 67.37 |
| 1000 | 100 | 0.2138 | 0.2240 | 35 | 0.1601 | 94.41 |

该表为单控制器的 Route+Service+EndpointSlice 独立对象模型，原始 300 条变更均保留于[规模报告目录](../../examples/k8s-acceptance/results/20261015/complete/final12/evidence/object-scale-attempt1/)。上表 Route-only 模型与持续运行共用隔离控制器，原始数据随长稳报告归档。CPU/API 窗口可包含后台状态对账；窗口结束 RSS 不代表连续峰值或长期增长结论。

H2 使用同一源码、同一工具链、stock/overlay 交替三轮测量，协议正确性先于性能门槛。数据是本实验室回归，不拼接历史轮次推算竞品优势。两小时资源观测按预设增长阈值验收，不据此承诺无限时间无泄漏。

| 同一 litegate-be 节点、各三轮中位数 | 成功 RPS | P99 毫秒 | CPU 核 | 各轮最大 RSS 样本的中位数 MiB |
|---|---:|---:|---:|---:|
| 同源 stock | 5996.69 | 41.118 | 1.3960 | 52.76 |
| 同源 h2coalesce.1 overlay | 6864.86 | 38.285 | 1.4014 | 53.36 |

六轮正确性通过且错误为零，RPS 比值 1.1448、P99 比值 0.9311，满足预设回归门槛（RPS 至少 0.8、P99 至多 1.5）。每轮首末节点、Pod UID、进程身份和运行 imageID 均保留于[H2 原始报告](../../examples/k8s-acceptance/results/20261015/complete/final12/evidence/h2-attempt1/summary.json)。

## 历史结果与失败保留

候选 11 完成 71 个 Go 测试包、四包启动竞态检查、官方三类核心 profile 与七种声明扩展，且独立五轮扩缩容的 HTTP 1694/TLS 1693 次新连接全部成功。严格长稳首轮扩缩容也未见传输错误，但完整验收的路径表达式负例暴露了另一个问题：已有有效 HTTPRoute 更新为不支持的匹配后，状态报告当前 generation 拒绝，通用 last-good 配置保留逻辑却留下旧 200 站点。该失败的逐副本证据和原日志已保留；候选 12 在 Gateway 转换阶段撤销不能生成有效路由的站点，保留无 HTTPRoute 的合法 HTTPS 证书占位。候选 11 的长稳明确中断，不作为完整两小时通过结果。

候选 10 的严格长稳流量记录了三次非预期连接异常，不能作为验收通过结果。独立五轮扩缩容复现进一步记录：五个新副本的 readyz/Kubernetes Ready 早于 HTTPS 监听约 1.3～1.7 秒，TLS NodePort 出现 19 次连接拒绝；缩容窗口没有传输错误。候选 11 增加缓存同步、首次发布与监听重载的就绪屏障，并重新计时验收。历史候选 5 虽完成两小时，其旧分类器可能把注入窗口的传输错误归为预期，因此也不能替代严格最终结果。

候选 10 的 H2 三轮对照实际分布在不同节点，只保留为历史数据。候选 11 固定所有 stock/overlay 轮次到同一节点，并对每轮首末实际节点进行断言。

候选 9 原版官方测试已通过：HTTP core 33/33、GRPC core 13/13、TLS core 11/11，七种声明 HTTP 扩展覆盖八项测试并全部通过；各 profile 零失败、零跳过。profile 共享部分 Gateway 测试，不能将这些数字相加解释为唯一用例数。

首次串行运行遇到上一 suite namespace 尚在删除的竞态，失败 attempt 保留；等待实际删除后重跑通过。修订 runner 只等待已经删除中的 namespace，不主动删除活跃对象，也不改上游断言。新增真实端口测试发现旧 admission 校验仍只允许 websecure，促成额外端口透传修复。路由匹配和证书端口隔离的独立审查结果也已纳入候选 10。

候选 9 的部分矩阵失败来自验收脚本：并发状态写入导致 replace 的 resourceVersion 过期，以及对代理失败响应添加了无关头部假设；修订后真实诊断通过，原失败仍保留。最终候选重新跑完整阶段，诊断结果不冒充原阶段通过。候选 9 的持续运行已明确标记 interrupted/superseded，最终候选重新计完整两小时。

候选 7 的 Helm 持续 API 请求 1383 次零错误，20 秒双向 gRPC/WebSocket/SSE 跨升级保持；实际浏览器验证 v2、回滚 v1、API 删除后的 503/Unavailable 与恢复后的 200/Connected。候选 8 的持续 EndpointSlice 变更修复保留旧版本失败与新版本两次通过对照。历史规模与 H2 数据保留作回归参考，最终结论使用最终同源测量。

## 支持边界

官方声明范围与产品另有功能验收的范围分别记录。官方报告 unsupportedFeatures 表示该轮未声明/未运行，不能推断所有列出功能均无实现；例如 BackendTLS/SAN、h2c、WebSocket 和镜像另有实际验收。未声明的 Mesh 不计入 Gateway profile 结果。

当前不实现路径 RegularExpression、标准 CORS filter、镜像 fraction、任意非 Service 后端及嵌套策略扩展。保留的未知字段明确拒绝；API Server 已裁剪的未知字段须通过 strict 校验发现。无法理解的匹配不生成替代匹配，也不遮蔽同域名有效规则；只有被拒绝匹配时返回 404。已知匹配上的不支持过滤器使用失败动作。两者均要求状态明确，配置校正后恢复。

跨 namespace 后端、镜像和证书需要 ReferenceGrant；ExtensionRef 限同 namespace。OIDC 多副本要求共享 Redis 与一致 session 加密密钥。Lease 不同步各副本内存限流/熔断计数。TLS listener 仅支持显式 Passthrough，终止使用 HTTPS；TCP 协议冲突明确拒绝，UDP 使用独立网络协议。

兼容结论仅覆盖实际验证的 K3s 版本与场景，不代表全部 Kubernetes 发行版、全部 Gateway API 扩展或完整替代 Traefik。

## 复验

统一入口、资源 YAML、夹具及采样口径见[验收说明](../../examples/k8s-acceptance/README.md)。make_plan.py 固定镜像、二进制、脚本、Chart、CRD 与夹具摘要；run_acceptance.py 保留逐次记录，只复用完全相同指纹的成功阶段。部分 only 选择不能冒充完整计划通过。

Helm 的运行配置和密钥保存在 Secret，证据不含部署凭据。CRD 必须显式升级，Helm upgrade 不会自动更新已安装的 crds 资源。最新隔离环境保留供统一验收，历史失败、诊断和修订后结果均保留；没有提交或推送代码。
