# Scan Protection (扫描防护 / 治理规则引擎)

`scan_protection` 是 LiteGate 内置的**白盒流量风险检测与自动处置**模块。它复用网关本就要做的判断（Host 是否命中站点、请求是否 404、UA 特征、路径特征等），把这些信号聚合成「按来源 IP 的风险画像」，并在风险累积到阈值时自动执行 **限速 / tarpit（拖延）/ 临时封禁**。

本文档覆盖 `scan_protection` 的**全部配置项**，包括新版的**治理规则引擎**（`global_rules` / `site_policies` / `tech_profiles`）。

> 它**不是** WAF，也不是 DDoS/CC 防护。它是**单机内存状态、基于来源 IP** 的机会型缓解。分布式扫描、走 CDN、伪造来源等场景可以绕过。处置依赖 `real_ip.trusted_proxies` 解析出的真实客户端 IP，请务必正确配置可信代理，否则封禁可能落在错误 IP 上。

---

## 1. 快速开始

模块**默认关闭**。在配置文件顶层加入 `scan_protection` 段即可启用：

```yaml
scan_protection:
  enabled: true                  # 总开关
  block_duration: "1h"           # 长封禁时长
  max_404_attempts: 5            # 观察窗口内允许的最大 404 次数
  observation_period: "1m"       # 404 滑动观察窗口（也是风险分衰减基准）
  block_direct_ip: false         # 是否拦截「直接用 IP 当 Host 且无站点匹配」的访问
  forbidden_paths:               # 自定义敏感路径关键字（仅在 404 时计分）
    - ".env"
    - "/wp-admin"
    - "/phpmyadmin"
```

> 首次上线建议 `block_direct_ip: false`，先在看板观察风险数据，确认无误伤后再收紧。

---

## 2. 基础配置项

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `enabled` | bool | `false` | 总开关。可在启动后通过看板/API 热切换。 |
| `block_duration` | duration 字符串 | `"1h"` | 长封禁时长。短封禁为本值的 1/6（最小 1 分钟）。非法值回退到 `1h`。 |
| `max_404_attempts` | int | `5` | 在 `observation_period` 窗口内，同一 IP 的 404 次数达到此值即额外 `+5` 分。≤0 回退到 `5`。 |
| `observation_period` | duration 字符串 | `"1m"` | 404 滑动窗口长度。非法值回退到 `1m`。 |
| `forbidden_paths` | string 列表 | 空 | 自定义敏感路径关键字，**只在请求 404 时**做子串匹配。以 `/` 开头的项视为 `deny`（+30）；否则视为扩展名类，仅计分（+6）。 |
| `block_direct_ip` | bool | `false` | 开启后，「Host 是裸 IP 且无任何站点匹配」的请求直接判 `deny`（+8 分）并返回 403。 |
| `global_rules` | 列表 | 空 | 全局治理规则，见第 4 节。 |
| `site_policies` | map | 空 | 按站点的技术栈封禁策略，见第 5 节。 |
| `tech_profiles` | map | 空 | 技术栈路径指纹库，配合 `site_policies` 使用，见第 5 节。 |

> duration 字符串遵循 Go 格式：`"30s"`、`"5m"`、`"2h"`。

---

## 3. 治理流水线（执行阶段）

每个请求按以下钩子顺序流经治理引擎；任一阶段产生的决策会被合并（取最高优先级动作：`deny > tarpit > rate_limit > score > observe > allow`）：

| 阶段 | 时机 | 本模块做的事 |
|---|---|---|
| **OnIngress** | 入口最前（路由解析之前） | 检查来源 IP 是否已在封禁/tarpit/限速状态 |
| **OnRouteResolved** | Host 命中站点之后、路由匹配之前 | 复检 IP 黑名单；`block_direct_ip`；`site_policies` 技术栈封禁；`global_rules` 中的**终止类动作**（deny/tarpit/rate_limit） |
| **OnRouteMiss** | 请求 404 时 | 完整 404 评分（`global_rules` 的 `score`/`observe`、敏感路径、UA、未知 Host、频繁 404、多路径扫描等） |
| **OnDecisionCommit** | 终止决策被路由真正执行时 | 落账：写入看板事件与规则命中统计，更新 IP 风险状态 |

> **要点**：终止类动作（deny/tarpit/rate_limit）在路由解析阶段命中时**不会立即落账**，而是延迟到 `OnDecisionCommit`（确认真正拦截后）才记录，避免被 magic 路由兜底放行的请求产生误记录。`score`/`observe` 这类非终止动作则在命中时立即记录。

---

## 4. 全局规则 `global_rules`

`global_rules` 是新版规则引擎的核心，对**所有站点**生效（无论 Host 是否命中）。

```yaml
scan_protection:
  enabled: true
  global_rules:
    - name: "block_vcs"                 # 规则名（用于看板统计）
      match:
        path_exact: ["/.git", "/.svn"]  # 精确/段匹配
        path_prefix: ["/.git/"]         # 前缀匹配
        path_contains: ["/id_rsa"]      # 子串匹配
      action: "deny"                    # deny|tarpit|rate_limit|score|observe|allow
      score: 30                         # 该规则贡献的风险分
      reason: "vcs_probe"               # 命中原因标签（看板展示）

    - name: "soft_watch_admin"
      match:
        path_prefix: ["/admin"]
      action: "observe"                 # 只记录、不加分、不拦截
      score: 0
      reason: "admin_probe"
```

### 4.1 字段说明

| 字段 | 说明 |
|---|---|
| `name` | 规则标识，出现在看板「规则命中统计」。 |
| `match.path_exact` | 命中条件：`路径 == 项` **或** 路径以该项结尾 **或** 路径包含 `项 + "/"`（即把它当作路径段）。 |
| `match.path_prefix` | 路径前缀匹配。 |
| `match.path_contains` | 路径子串匹配。 |
| `action` | 见下方动作语义。大小写不敏感，未知动作回退为 `allow` 并打告警。 |
| `score` | 命中后累加到该 IP 的风险分。 |
| `reason` | 自定义原因标签。 |

### 4.2 动作语义

| 动作（同义词） | 含义 |
|---|---|
| `deny` / `block` / `ban` | 直接拒绝（403），并按 `score` 落账。 |
| `tarpit` | 拖延：命中请求 `sleep` 后再放行（每请求一次，约 3 秒）。 |
| `rate_limit` / `ratelimit` | 返回 429，限速 1 分钟。 |
| `score` / `suspicious` | 仅累加风险分，不直接拦截（由累计分阈值决定后续动作）。 |
| `observe` | 仅记录到看板，不加分、不拦截。 |
| `allow` / 空 | 显式放行（白名单），命中后**不计分、不记录**。可用于给敏感路径开口子。 |

> 终止类动作（deny/tarpit/rate_limit）即便 `score: 0` 也会**立即执行**——动作本身是强制的，分数只影响「累计画像」。

### 4.3 内置（legacy）规则

无论是否配置 `global_rules`，以下内置规则始终生效（你的规则会**追加**在前面优先匹配）：

- **关键路径直封**（`deny`, +30）：`/.git`、`/.svn`、`/.hg`、`/.bzr`、`/.env`、`/wp-config.php`、`/etc/passwd`、`/proc/self/environ`、`/.aws/credentials`、`/.docker/config.json`，以及包含 `/.git/`、`/.env.`、`/id_rsa`、`/wp-json/gravitysmtp/`、`/wp-json/gravityforms/` 等。
- **`forbidden_paths`** 中以 `/` 开头的项 → `deny` +30；其余（如 `.php`）→ `score` +6。
- **特殊探测路径**（仅 404 时，+10）：`/mcp`、`/sse`、`/actuator`、`/debug`、`/server-status` 前缀。
- **`/wp-admin`、`/phpmyadmin`**（仅 404 时，+10）。

---

## 5. 站点级技术栈封禁 `site_policies` + `tech_profiles`

用于「某站点不应该出现某种技术栈的路径」场景。例如一个纯 API 站点不该被探测 WordPress 路径。

```yaml
scan_protection:
  enabled: true

  # 技术栈路径指纹库（可复用）
  tech_profiles:
    wordpress:
      path_prefix: ["/wp-admin", "/wp-content", "/wp-json/"]
      path_exact:  ["/xmlrpc.php"]
    phpmyadmin:
      path_prefix: ["/phpmyadmin", "/pma"]

  # 按站点声明要封禁的技术栈
  site_policies:
    api.example.com:
      deny_tech: ["wordpress", "phpmyadmin"]
      critical_action: "deny"     # 命中后的动作：deny|tarpit|rate_limit|score|observe|allow
```

| 字段 | 说明 |
|---|---|
| `tech_profiles.<name>.path_prefix` / `path_exact` | 该技术栈的特征路径。 |
| `site_policies.<host>.deny_tech` | 该站点禁止出现的技术栈名（引用 `tech_profiles` 的 key）。 |
| `site_policies.<host>.critical_action` | 命中后的动作。`deny`=30 分、`tarpit`=15、`rate_limit`=10、`score`=5、`observe`=0、`allow`=放行。 |

> `site_policies` 的 key 是 **Host（站点域名）**，大小写不敏感。命中发生在 **OnRouteResolved** 阶段（站点已匹配、路由未匹配前），可在请求真正到达后端前拦截。

---

## 6. 评分与处置阈值

每个来源 IP 维护一个累计风险分 `score`，由「决策引擎」按累计分决定动作：

| 累计分 | 动作 | 行为 |
|---|---|---|
| ≥ 30 | `temp_ban_long` | 封禁 `block_duration`，返回 403 |
| ≥ 20 | `temp_ban_short` | 短封禁 `block_duration/6`（最小 1 分钟），返回 403 |
| ≥ 15 | `tarpit` | 拖延：每请求 `sleep` 约 3 秒，持续 1 分钟 |
| ≥ 10 | `rate_limit` | 返回 429，持续 1 分钟 |
| ≥ 5 | `suspicious` | 仅标记观察 |
| < 5 | `observe` | 正常放行 |

### 6.1 404 评分信号（OnRouteMiss）

| 信号 | 加分 | 条件 |
|---|---|---|
| `not_found` | +1 | 每次 404 |
| `post_unknown_path` | +6 | 404 且方法为 POST |
| `unknown_host` | +5 | 请求未命中任何站点（同一 Host 在窗口内只计一次） |
| `direct_ip_access` | +3 | 未命中站点且 Host 是裸 IP |
| `bad_user_agent` | +2 | 未命中站点且 UA 缺失/含扫描器特征 |
| `sensitive_path` | +10 | 命中特殊探测前缀（`/mcp` 等）或 `/wp-admin`、`/phpmyadmin` |
| `frequent_404` | +5 | 窗口内**不同路径**的 404 数 ≥ `max_404_attempts` |
| `scan_multiple_paths` | +8 | 同一 IP 访问 ≥ 3 个不同路径（一次性计分） |
| `robots_txt` | +1 | 404 访问 `/robots.txt` |
| `global_rules` 命中 | 规则 `score` | 见第 4 节 |

> **防误报设计**：`bad_user_agent`、`unknown_host`、`direct_ip_access` 这类弱信号**只在请求未命中任何站点时**才计分。合法客户端（`curl`、`Go-http-client`、`python-requests`、监控探针）访问**已配置站点**时不会因 UA 累积风险分。
>
> 扫描器 UA 特征关键字：`curl`、`wget`、`python`、`go-http-client`、`nmap`、`sqlmap`、`scan`、`headless`、`nikto`、`masscan`、`zgrab`。

> **重复请求去重**：同一 IP 在 `observation_period` 窗口内对同一 `方法 + Host + 路径` 的重复 404 **只计一次分**（SSE 重连、前端轮询、刷新、表单重复提交不会累积）。扫描器不会重复打同一个路径，所以去重不影响检出。
>
> **强/弱信号与封顶**：`not_found`、`post_unknown_path`、`unknown_host`、`frequent_404`、`scan_multiple_paths` 属于**弱信号**，真实浏览器在站点未部署完或接口配错时也会产生。一个 IP 如果只有弱信号，分数照常累积，但处置**最多是 `suspicious`**；只有窗口内不同路径 404 数达到 `max_404_attempts` 时才会升到 `rate_limit`，**永远不会 tarpit 或封禁**。出现**强信号**后（`direct_ip_access`、`bad_user_agent`、`sensitive_path`、带分数的 `global_rules`/`deny_tech` 命中），按上表正常升级，之前累积的弱信号分数也一并计入。

### 6.2 新 IP 门槛与风险分衰减

- **新 IP 门槛**：一个从未见过的 IP，只有当首次违规分 ≥ 5 时才会被分配跟踪状态；低于 5 的一次性 404 直接放行、不占内存。
- **风险分自愈**：当 IP 当前不处于封禁/tarpit/限速状态时，每空闲约 2 分钟自动 `-3` 分（下限 0）。偶发探测会随时间衰减归零；被误标记的客户端只要停止异常行为，分数会自动回落。

---

## 7. 运行时开关与配置热重载

- `enabled` 在**进程启动时**作为初始值。
- 运行时可通过看板顶部 **「Scan Protection (Runtime)」** 开关，或 API 热切换：
  ```
  POST /api/scan-protection/toggle?enabled=true     # 开启
  POST /api/scan-protection/toggle?enabled=false    # 关闭
  ```
  需通过看板鉴权与 CSRF 校验，内存级生效。
- 其余配置项（`block_duration`、`global_rules`、`site_policies` 等）支持**热重载**，reload 后重新编译策略并立即生效。

> ✅ **运行时开关是权威来源**：配置热重载（reload）**不会覆盖**你通过看板/API 设置的运行时开关。`UpdateConfig` 会保留当前 `enabled` 状态、只更新其余字段并以当前状态重新编译策略。因此「压力大时临时关闭、且保证保持关闭」的场景是成立的——即使期间发生 reload，也不会被配置文件里的 `enabled: true` 重新打开。配置文件里的 `enabled` 仅在**进程启动**时作为初始值。

---

## 8. 性能与资源约束

模块对自身资源做了硬约束，避免被针对扫描时成为资源放大点：

- **分片状态表**：32 个分片，每片上限 1560 条（合计约 5 万 IP）。达到上限优先驱逐过期条目，仍满则拒绝跟踪新 IP。
- **后台清理**：每 10 秒一次，移除超过 1 小时无活动且未封禁的 IP。
- **每 IP 404 时间戳上限 64**；**多路径集合**在触发「多路径扫描」后立即释放。
- **看板事件队列上限 100**；跟踪路径截断 256 字节、看板路径截断 512 字节。
- **热路径开销**：正常请求做「一次原子读总开关 + 一次分片读锁查 IP 状态 + 一次全局规则线性扫描」。`global_rules` 越多、路径模式越多，OnRouteResolved 的线性扫描成本越高——建议规则集保持精简。命中合法路由的请求不做 404 评分。

---

## 9. 调优与排错

- **先观察、再拦截**：上线初期把高风险规则设为 `observe`/`score`，在看板确认无误伤后改 `deny`。
- **自家前端 bug 会污染评分**：前端反复请求不存在路径（如 URL 拼进 `undefined`）会让该真实用户 IP 累积分。应修前端，而非靠本模块兜底。可对这些路径配 `allow` 规则临时止血。
- **给敏感路径开白名单**：用 `action: "allow"` 的 `global_rules` 精确放行。
- **更激进**：调小 `max_404_attempts`、调短 `observation_period`，或增加 `deny` 规则。
- **更宽松**：调大 `max_404_attempts`，精简规则集。

---

## 10. FAQ

**Q：合法的 `curl` / Python / Go SDK 客户端会被封吗？**
A：不会——只要它们访问**已配置的站点**。弱信号（UA、未知 Host）只在请求未命中站点时计分。

**Q：合法的 `.php` 站点会因 `forbidden_paths` 含 `.php` 被误杀吗？**
A：不会。`forbidden_paths` 只在请求 **404** 时匹配；合法 `.php` 站点正常响应、不产生 404。

**Q：它能防 DDoS / CC 吗？**
A：不能。它是基于来源 IP 的白盒检测与机会型缓解，不替代专业 DDoS/CC 防护或前置 WAF。

---

## 相关文档

- 看板与可观测：[dashboard.md](../08-observability/dashboard.md)
- IP 限制：[ip-restriction.md](ip-restriction.md)
- 限速：[rate-limit.md](rate-limit.md)
