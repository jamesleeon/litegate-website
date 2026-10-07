# 压测指南 (Benchmarking)

本文档给出一套在 **ESXi 虚拟化环境**下对 LiteGate 进行性能压测的标准方法：如何部署测试环境、如何执行、以及该看哪些指标。重点是**核心 proxy 层**的性能归因。

---

## 0. 先回答两个常见疑问

### ESXi 能测出真实性能吗？

能。ESXi 是 type-1 裸金属 hypervisor，虚拟化开销很低，是绝大多数生产云的底座。**相对比较类结论**（代理自身开销、各中间件成本、瓶颈定位、容量拐点）几乎不受影响；**绝对峰值 QPS** 会比裸金属略低（视网络路径而定）。要追绝对极限才需要裸金属 + 物理交换机，绝大多数场景没必要。

真正让你"测不准"的不是 ESXi，而是配置坑（见 [§1.3 ESXi 必做配置](#13-esxi-必做配置)）。

### 假后端为什么用 LiteGate `respond`，而不是 nginx？

假后端的唯一职责是"快到可忽略的上游"。LiteGate 的 `respond` action 就是个静态响应器，和 `nginx return 200` 性能等价，**所以直接用一个 LiteGate `respond` 实例当后端即可，不必再装 nginx**。

更重要的是要区分 `respond` 的两种用法，二者结合才能精确分离出代理层成本：

| 路由类型 | 测量的是什么 |
|---|---|
| 网关上的 `respond` 路由（不转发） | LiteGate **去掉代理层**的纯处理路径（accept + 路由匹配 + 中间件 + 写响应）= 网关地板 |
| `proxy` 路由 → 独立上游 | 在上面的基础上**额外**加上代理层（拨号、连接池、`io.Copy`） |

> **`proxy 路由延迟` − `respond 路由延迟` ≈ 代理层本身的成本。** 这正是"核心 proxy 层指标"。

因此后端 VM 仍然需要（proxy 路由必须有一个**真实的 TCP 上游**才能跑到拨号/连接池/copy 这套代码），但它跑的是 LiteGate `respond`，不是 nginx。

---

## 1. 测试环境部署

### 1.1 拓扑

```
[压力机 gen] ──► [被测网关 gw] ──► [假后端 be]
  wrk2 / k6      LiteGate         LiteGate (respond)
```

三个角色分到三台 VM。**压力机和网关绝不能挤在一台**，否则压力机抢光 CPU，测的是抢占不是网关。

### 1.2 VM 规格

| 角色 | VM | 建议规格 | 部署 |
|---|---|---|---|
| 压力机 | `gen` | 4–8 vCPU / 4G，**vCPU ≥ 网关** | wrk2、k6、vegeta |
| 被测网关 | `gw` | **固定 4 vCPU / 4G（关键变量，锁死）** | LiteGate + node_exporter |
| 假后端 | `be` | 4 vCPU / 2G | LiteGate（respond） |

> 网关的 vCPU 数是被测对象，**一旦确定就不要改**，否则历史数据无法横比。

操作系统统一（Ubuntu Server 22.04 / Debian 12 均可），同一 vSwitch 同网段。

### 1.3 ESXi 必做配置

| 项 | 要求 | 验证 |
|---|---|---|
| **不超分 vCPU** | 各 VM 的 vCPU 总和 ≤ 物理核；给 gw、gen 设 CPU **预留(reservation)** | esxtop 看 `%RDY < 5%` |
| **虚拟网卡** | 全部用 **vmxnet3**（不要 e1000） | — |
| **主机电源策略** | High Performance，关 C-state（BIOS + ESXi 主机层） | — |
| **压力机不与网关同物理核竞争** | gen 与 gw 尽量分到不同 NUMA / 物理主机 | esxtop `%CSTP ≈ 0` |
| **时钟同步** | 装 open-vm-tools | — |

### 1.4 系统内核调优（三台都做）

Linux 默认上限会先于 LiteGate 撞墙，压测前务必调整：

```bash
ulimit -n 1048576
sysctl -w net.ipv4.ip_local_port_range="1024 65535"
sysctl -w net.ipv4.tcp_tw_reuse=1
sysctl -w net.core.somaxconn=65535
sysctl -w net.ipv4.tcp_max_syn_backlog=65535
```

---

## 2. 各节点配置

### 2.1 假后端（be）

`config.yaml`：

```yaml
mode: performance
http:
  port: 8080
sites_dir: ./sites
log:
  level: error        # 关掉访问日志，避免后端成为瓶颈
```

`sites/backend.yaml`：

```yaml
domain: "0.0.0.0"
routes:
  - name: "tiny"
    match:
      path_prefix: "/"
    action:
      type: "respond"
      status: 200
      body: "ok"
      content_type: "text/plain"
```

启动后用 `curl http://<be-ip>:8080/` 确认返回 `ok`。

> 需要测不同响应大小或注入上游延迟时，把后端换成可调参数的 Go 假后端（响应大小、延迟可控）。

### 2.2 被测网关（gw）

`config.yaml`：

```yaml
# performance 模式会跳过 dashboard 实时推送(SSE)的每请求开销，但仍保留 Prometheus 指标
mode: performance

http:
  port: 8080

# 指标端点。注意:address 默认 127.0.0.1,跨 VM 抓取必须显式设 0.0.0.0
metrics:
  enabled: true
  address: "0.0.0.0"
  port: 9091           # 抓取 http://<gw-ip>:9091/metrics

# pprof。同样默认只绑 127.0.0.1
pprof:
  enabled: true
  address: "0.0.0.0"
  port: 6060           # http://<gw-ip>:6060/debug/pprof/

sites_dir: ./sites

log:
  level: error         # 压测基准轮:关访问日志。再单独开一轮做对照
```

> ⚠️ `address: 0.0.0.0` 会把指标/pprof 端口暴露到网络，**仅限隔离的测试网，生产环境不要这样配**。

`sites/bench.yaml`（同时放基线路由和代理路由）：

```yaml
domain: "0.0.0.0"
routes:
  # 基线:纯网关处理,不转发 —— 测网关地板
  - name: "baseline-respond"
    match:
      path_prefix: "/respond"
    action:
      type: "respond"
      status: 200
      body: "ok"
      content_type: "text/plain"

  # 代理:转发到 be —— 测代理层
  - name: "proxy-tiny"
    match:
      path_prefix: "/proxy"
    action:
      type: "proxy"
      upstream_type: "static"
      upstream: ["<be-ip>:8080"]
      strip_prefix: "/proxy"
```

### 2.3 压力机（gen）

安装 wrk2（恒定速率、修正 coordinated omission，延迟分位数可信）与 k6（脚本化、跨平台、支持 WebSocket）：

```bash
# wrk2
git clone https://github.com/giltene/wrk2 && cd wrk2 && make
# k6 (Debian/Ubuntu)
sudo gpg -k && sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
  --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \
  | sudo tee /etc/apt/sources.list.d/k6.list && sudo apt update && sudo apt install k6
```

---

## 3. 执行方法

### 3.1 基本流程

1. **先测 baseline**：gen 直连 be，记录后端裸上限。再过 gw，两者差值才是网关税。
2. **预热**：先低速跑 30s，让连接池 / GC 稳定，再正式加压。
3. **阶梯恒定速率加压找拐点**——不是看最大 QPS，而是看 **P99 在哪一档开始翘**，那一档就是容量上限。
4. **每轮只改一个变量**（响应大小 / 并发 / keep-alive / TLS / HTTP2/3 / 中间件开关），否则无法归因。

### 3.2 关键对照：分离代理层成本

同一负载分别打两条路由，相减即得代理层开销：

```bash
# 网关地板:纯 respond
wrk -t4 -c64 -R10000 -d60s --latency http://<gw-ip>:8080/respond

# 代理路径:转发到 be
wrk -t4 -c64 -R10000 -d60s --latency http://<gw-ip>:8080/proxy/
```

也可在网关的 Prometheus 指标里直接读差值（见 §4），更精确。

### 3.3 阶梯加压

```bash
for rate in 2000 5000 10000 20000 40000; do
  echo "=== ${rate} RPS ==="
  wrk -t4 -c128 -R${rate} -d60s --latency http://<gw-ip>:8080/proxy/
done
```

记录每档的 P50 / P90 / P99 / P99.9 与错误率。P99 开始非线性上翘的那一档即为拐点。

### 3.4 拐点抓现场

延迟拐点出现时，立刻抓一份 CPU profile：

```bash
go tool pprof -http=:0 'http://<gw-ip>:6060/debug/pprof/profile?seconds=30'
```

火焰图直接告诉你瓶颈在路由匹配、GC、syscall 还是某个中间件。同时可抓 `heap`、`goroutine`、`mutex`。

### 3.5 场景矩阵（针对 proxy 层）

逐个跑，每个对应一类 proxy 行为：

| 场景 | 目的 | 重点指标 |
|---|---|---|
| 小响应(<1KB) keep-alive 拉满 | 转发极限 QPS + 自身延迟 | 延迟差值、goroutines、CPU |
| 大响应(1MB+) | 吞吐 / 带宽、`io.Copy` 路径 | `http_response_bytes_total`、网卡、内存 |
| 每请求新连接(无 keep-alive) | 连接建立成本、fd 压力 | goroutines、fd 数 |
| HTTPS / HTTP2 / HTTP3 | TLS 与协议开销 | CPU、握手延迟 |
| WebSocket / Upgrade 长连接 | 隧道并发上限 | `litegate_proxy_active_tunnels`、goroutines、内存 |
| 逐个打开 WAF / 限流 / auth | 量化每层中间件成本 | 延迟差值对比 |

---

## 4. 看什么指标（三层一起看）

### A. 压力机侧（结果）

QPS、**P50 / P90 / P99 / P99.9 延迟**、错误率、超时数。wrk2 的 `--latency` 直接输出分位数。

### B. LiteGate 侧（归因）—— `http://<gw-ip>:9091/metrics`

| 指标 | 看什么 |
|---|---|
| `litegate_http_request_duration_seconds` vs `litegate_proxy_duration_seconds` | **二者差值 = 代理自身开销**（最有价值的量） |
| `litegate_goroutines_current` | 暴涨 / 不回落 = 泄漏（长连接场景重点看） |
| `litegate_proxy_upstream_status_total{status_class}` | 高压下 5xx 是否冒头 |
| `litegate_proxy_requests_total{result}` | 转发成功 / 失败结果分布 |
| `litegate_rate_limited_requests_total` / `litegate_waf_blocked_requests_total` | 确认不是被自己拦了（误判成"性能差"） |
| `litegate_circuit_breaker_state` | 是否误熔断（0=Closed,1=Half,2=Open） |
| `litegate_proxy_active_tunnels` | WebSocket / Upgrade 场景的活跃隧道数 |

PromQL 直接算代理层 P99 开销：

```promql
histogram_quantile(0.99, sum(rate(litegate_http_request_duration_seconds_bucket[1m])) by (le))
-
histogram_quantile(0.99, sum(rate(litegate_proxy_duration_seconds_bucket[1m])) by (le))
```

### C. 主机 / ESXi 侧（瓶颈定位）

- **VM 内**（node_exporter）：CPU（含 **sys%**）、内存 / GC、**fd 数**、网卡 bps/pps、`TIME_WAIT` 连接数。
- **ESXi 层**（esxtop，最关键的虚拟化健康信号）：
  - **`%RDY`（CPU Ready）必须 < 5%**——超了说明 vCPU 被抢，延迟数据不可信，需加预留或降并发。
  - **`%CSTP`（co-stop）应 ≈ 0**——多 vCPU 同步等待。
  - 网络 `%DRPTX / %DRPRX`（丢包）应为 0。

### 判读逻辑

延迟翘了 → **先看 esxtop `%RDY`** 排除"是 ESXi 在抢 CPU" → 排除后再看 gw 的 CPU `sys%` 与 pprof 火焰图，定位是路由匹配、GC、syscall 还是中间件。

---

## 5. 常见陷阱清单

- [ ] 压力机和网关分开了吗？（同机必然测不准）
- [ ] esxtop `%RDY < 5%`？（虚拟化抢占会污染所有延迟数据）
- [ ] 虚拟网卡是 vmxnet3 不是 e1000？
- [ ] `ulimit -n` 和临时端口范围调大了吗？
- [ ] 用的是 wrk2（恒定速率）而非 wrk1（开环最大速率，会高估）？
- [ ] 假后端确认不是瓶颈？（压测时看 be 的 CPU 有没有打满）
- [ ] access log 单测过开 / 关两种情况？（日志 I/O 常是隐形瓶颈）
- [ ] metrics / pprof 的 `address` 设了 `0.0.0.0` 才能跨 VM 抓取？
- [ ] 每轮只改了一个变量？
