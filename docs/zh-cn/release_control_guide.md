# 配置发布控制面（Release Control）

LiteGate 内置的**配置灰度发布**能力：把对站点/流配置的修改先暂存为「草稿」，经过校验、确认 diff、显式「发布」后才真正生效；并保留每一次发布的历史，支持一键回滚。

> 一句话区别：默认模式下，改动配置文件即被 watcher 热加载、立刻生效；开启发布控制面后，Dashboard 的保存/删除会先进**草稿**，需要你**显式发布**才会落盘生效。这是一个「白盒、内生」的配置变更管控层，而不是外挂的 CI/CD。

---

## 1. 适用场景与前提

适合需要「改配置前先校验、确认、可回滚」的生产场景：

- 改完配置希望先 dry-run 校验（schema、端口冲突、保留路径、安全告警），确认无误再生效；
- 一次改多个文件，希望**原子地**一起生效，而不是边改边热加载产生中间态；
- 需要变更历史与**一键回滚**到上一个已知良好版本；
- 需要导出/导入整套配置快照做备份或迁移。

### 启用前提（重要）

发布控制面**只在本地文件模式下生效**。当启用了 Consul 或 LiteMesh 的配置下发（`consul.enabled` 或 `litemesh.enabled`）时，配置由 KV 中心下发，发布控制面会**自动禁用**——此时配置发布应由 KV 侧的流程负责。

启动日志会明确告诉你当前状态：

- 已启用：`Configuration release control plane successfully initialized`
- 未启用：`Consul, LiteMesh mode active or Release Control disabled. Configuration release control plane disabled.`

---

## 2. 如何启用

在主配置文件的 `dashboard` 段下打开 `release_control`：

```yaml
dashboard:
  enabled: true
  port: 9999
  username: admin
  password: "your-strong-password"
  # 开启配置发布控制面
  release_control:
    enabled: true
```

同时满足以下条件才会真正启用：

1. `dashboard.enabled: true`（控制面通过 Dashboard 暴露）；
2. `dashboard.release_control.enabled: true`；
3. **未**启用 Consul / LiteMesh 配置下发（即本地文件模式）。

启用后，草稿与发布历史存放在进程工作目录下的 `./.litegate/releases/`（详见 [第 7 节](#7-存储与限制)）。

---

## 3. 核心概念

| 概念 | 说明 |
|---|---|
| **Release（发布版本）** | 一次配置快照，包含若干 ConfigArtifact、校验报告、diff 摘要、状态、创建/发布信息。 |
| **ConfigArtifact（配置制品）** | 一个配置文件单元。字段：`kind`（`site`/`stream`）、`name`（文件名，如 `example.com.yaml`）、`content`（YAML 原文）、`checksum`（SHA256）、`source`、`path`。 |
| **Draft（草稿）** | 尚未发布的工作版本。同一时刻只保留一个「当前草稿」。 |
| **Active（当前生效）** | 已发布并落盘生效的版本，由 `active.txt` 指针记录。 |
| **Previous（上一个生效）** | 上一个生效版本，由 `previous.txt` 指针记录，用于「回滚到上一版」。 |

### 状态流转

```
draft ──validate──> validated ──publish──> active
  │                     │                    │
  │                     └──publish──> active_with_warnings（发布成功但有非阻塞告警）
  │
  └──publish 校验失败──> 保持 draft（报告写入 validation，不降级）
                                            │
                       rollback ──> 旧 active 标记为 rolled_back，新建一条 active
```

状态常量：`draft`、`validated`、`publishing`、`active`、`active_with_warnings`、`failed`、`rolled_back`。

> 说明：保存或删除时，若已存在 `draft`/`validated`/`failed` 的工作版本，会复用同一条草稿并把状态重置回 `draft`，**不会**丢失你之前暂存的改动。

---

## 4. 在 Dashboard 中使用

开启发布控制面后，Dashboard 现有的「保存配置 / 删除配置」行为发生变化：

1. **保存/删除** → 改动进入**当前草稿**，接口返回 `requires_publish: true` 与 `draft_id`，配置**尚未生效**；
2. 前端会弹出提示「已保存为草稿（ID: …），是否立即发布？」：
   - 选「是」→ 调用发布接口，配置落盘、watcher 热加载、立即生效；
   - 选「否」→ 改动留在草稿中，可稍后通过 API 校验/发布。

> 常见疑问：**「我点了保存，为什么站点没生效？」**
> 因为开启了发布控制面,保存只入草稿。请在弹窗里确认发布,或调用 `POST /api/releases/{id}/publish`。

---

## 5. 工作流（推荐顺序）

```
保存改动（入草稿）
   └─> （可选）校验草稿  POST /api/releases/{id}/validate
        └─> 查看 diff    GET  /api/releases/{id}/diff
             └─> 发布     POST /api/releases/{id}/publish   ← 发布内部会再次 dry-run 校验
                  └─> 如有问题 一键回滚  POST /api/releases/previous/rollback
```

要点：

- **发布会自带 dry-run 校验**：即使你跳过 `validate` 直接 `publish`，发布前也会强制校验；校验不通过则中止、配置不落盘。
- **发布是原子的**：本地实现采用「临时文件 → 备份原文件 → 原子 rename → 清理」的方式，跨 `sites/` 与 `streams/` 两个目录统一提交；任一步失败会回滚全部改动,生产目录不会留下半成品或残留的 `.tmp-*/.bak-*` 文件。
- **回滚也是一次发布**：回滚会新建一条发布记录（保留审计轨迹），并把被替换的旧 active 标记为 `rolled_back`。

---

## 6. API 参考

所有接口都需要通过 Dashboard 鉴权（见 [鉴权](#鉴权)），路径前缀随 Dashboard 的反代前缀而定，下文以根路径为例。

### 6.1 Release 管理：`/api/releases`

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/releases` | 列出全部发布版本（按创建时间倒序）。 |
| `POST` | `/api/releases` | 用请求体的 artifact 列表创建/更新草稿。**见下方全量替换警告**。 |
| `GET` | `/api/releases/{id}` | 获取单个发布版本详情。 |
| `POST` | `/api/releases/{id}/validate` | 对草稿执行 dry-run 校验，返回校验报告。 |
| `POST` | `/api/releases/{id}/publish` | 发布指定版本（发布前自动校验）。 |
| `POST` | `/api/releases/{id}/rollback` | 回滚。`{id}` 传 `previous` 表示回滚到上一个生效版本，传具体 release ID 表示回滚到该版本。 |
| `GET` | `/api/releases/{id}/diff` | 返回该版本相对**当前物理生效配置**的差异（add/modify/delete）。 |

返回统一为 `{ "success": <bool>, "data": <对象> }`。

> ⚠️ **`POST /api/releases` 是「声明式全量替换」语义。**
> 草稿 = 请求体里给出的 artifact **全集**。发布该草稿时，发布逻辑会删除生产目录里**不在该列表中的**所有 `.yaml/.yml` 配置。
> 这意味着：如果你只 POST 了一个文件就发布，其余站点/流配置会被清空。
> 在 Dashboard 里走「保存→发布」流程是安全的（它会从当前草稿/生效配置累积全集）；但如果你用脚本直接对接这个裸接口，**务必传完整集合**，否则会误删配置。

**创建草稿请求体示例：**

```json
[
  {
    "kind": "site",
    "name": "example.com.yaml",
    "content": "domain: example.com\nroutes:\n  - name: r1\n    match:\n      path_prefix: /\n    action:\n      type: respond\n      status: 200\n      body: OK\n"
  }
]
```

**发布示例（curl，使用 API Token）：**

```bash
# 1. 校验
curl -X POST -H "X-API-Key: $TOKEN" \
  http://127.0.0.1:9999/api/releases/20260627-153411-a1b2c3d4/validate

# 2. 查看 diff
curl -H "X-API-Key: $TOKEN" \
  http://127.0.0.1:9999/api/releases/20260627-153411-a1b2c3d4/diff

# 3. 发布
curl -X POST -H "X-API-Key: $TOKEN" \
  http://127.0.0.1:9999/api/releases/20260627-153411-a1b2c3d4/publish

# 4. 出问题，回滚到上一版
curl -X POST -H "X-API-Key: $TOKEN" \
  http://127.0.0.1:9999/api/releases/previous/rollback
```

### 6.2 快照导入导出：`/api/snapshot/*`

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/snapshot/export` | 导出当前**物理生效**的全部配置为快照 JSON（附 `Content-Disposition`，含 `exported_at` 与 artifacts；导出时会清除平台相关绝对路径以便迁移）。 |
| `POST` | `/api/snapshot/import` | 导入快照 JSON，**作为草稿**落地（不直接生效）。请求体上限 10MB；会校验 artifact 文件名安全性。 |
| `GET` | `/api/snapshot/resolved-sites` | 导出运行时**已解析**的站点视图（含动态发现解析后的路由），用于排查与留档。 |

### 鉴权

复用 Dashboard 的鉴权（`checkAuth`）：

- **API Token**（自动化优先）：请求头 `X-API-Key: <dashboard.token>`，命中即放行，且**不触发 CSRF 校验**；
- **Cookie 会话**（浏览器）：登录后携带签名 Cookie，写操作（POST/DELETE/PUT）会额外校验 `Origin`/`Referer`（CSRF 防护）。

---

## 7. 校验都查什么

发布/校验时，会在一个**临时目录**里用独立的 loader 实例 dry-run 加载（不污染线上 loader、不读写生产路径），并执行以下检查：

- **Schema 解析**：站点与流配置能否正确解析、加载；
- **端口冲突**：同 `域名:端口` 重复定义、同 `端口/协议` 的 L4 流重复监听（报错，阻塞发布）；
- **保留路径冲突**：路由是否直接命中 `/_litegate`、`/healthz`、`/readyz`、`/metrics`、`/pprof` 等内部端点（精确/前缀匹配报错，DSL 规则中包含关键字给告警）；
- **安全最佳实践**：proxy 路由开启 `insecure_skip_verify: true` 会产生**告警**（不阻塞，发布后状态变为 `active_with_warnings`）。

> 错误（errors）会阻塞发布；告警（warnings）不阻塞，但会记录在校验报告并使发布状态标记为「带告警生效」。

---

## 8. 存储与限制

- **存储位置**：`./.litegate/releases/`（相对进程工作目录）。
  - `revisions/{id}/manifest.json`：每个版本的完整记录；
  - `active.txt` / `previous.txt`：当前 / 上一个生效版本指针。
- **Release ID**：`YYYYMMDD-HHMMSS-<随机十六进制>`，按时间可排序。
- **暂无自动保留/清理策略**：历史版本会持续累积，长期运行需自行清理 `revisions/` 目录（可保留最近 N 个）。
- **落盘先于状态提交**：发布时先写文件再更新发布记录指针；极端情况下若指针写入失败，配置可能已生效但记录未更新——本地写盘极少失败，留意即可。
- **非本地 ConfigSource 暂不可用于生产**：当前仅本地文件源（`LocalFileSource`）接线；代码中保留的非本地回退路径**不是原子的**，接入 KV 类配置源前需补两阶段提交。

---

## 9. FAQ

**Q：开了发布控制面，Dashboard 保存后站点不生效？**
A：这是预期行为。保存只入草稿，需在弹窗确认发布，或调用 `POST /api/releases/{id}/publish`。

**Q：为什么 Consul/LiteMesh 模式下没有这个功能？**
A：那两种模式下配置由 KV 中心下发，发布控制面会自动禁用，发布应由 KV 侧流程负责。看启动日志可确认当前状态。

**Q：我用脚本 POST `/api/releases` 后发布，别的站点不见了？**
A：该接口是声明式全量替换，草稿即你给的全集，发布会清理不在集合内的配置。请传完整集合，或改走 Dashboard 的「保存→发布」累积流程。

**Q：发布失败了，草稿还在吗？**
A：在。发布前校验不通过时，草稿不会被降级删除，校验报告会写入该版本，修正后可重新发布。

**Q：怎么回滚？**
A：`POST /api/releases/previous/rollback` 回滚到上一个生效版本；也可对具体 release ID 回滚。回滚会新建一条审计记录并将旧版本标记为 `rolled_back`。

---

## 相关文档

- [Dashboard 管理控制台](user/08-observability/dashboard.md)
- [站点配置](user/03-configuration/site-config.md)
- [L4 Stream 配置](user/03-configuration/stream-config.md)
