# Benchmarking

This page gives a standard method for benchmarking LiteGate in an **ESXi virtualized environment**: how to set up the test environment, how to run it, and which metrics to read. The focus is performance attribution of the **core proxy layer**.

---

## 0. Two common questions first

### Can ESXi measure real performance?

Yes. ESXi is a type-1 bare-metal hypervisor with low virtualization overhead and underlies most production clouds. **Relative conclusions** (the proxy's own overhead, the cost of each middleware, bottleneck location, capacity knee points) are barely affected; **absolute peak QPS** is somewhat lower than bare metal (depending on the network path). Only chasing absolute limits needs bare metal plus physical switches, which most scenarios don't.

What actually makes measurements unreliable isn't ESXi but configuration pitfalls (see [§1.3 Required ESXi settings](#13-required-esxi-settings)).

### Why use LiteGate `respond` as the fake backend instead of nginx?

The fake backend's only job is to be "an upstream fast enough to ignore". LiteGate's `respond` action is a static responder equivalent to `nginx return 200` in performance, **so a LiteGate `respond` instance serves as the backend and nginx isn't needed**.

More importantly, distinguish two uses of `respond`; together they isolate the proxy layer's cost precisely:

| Route type | What it measures |
|---|---|
| A `respond` route on the gateway (no forwarding) | LiteGate's processing path **without the proxy layer** (accept + route matching + middleware + writing the response) = the gateway floor |
| A `proxy` route → separate upstream | The above **plus** the proxy layer (dialing, connection pool, `io.Copy`) |

> **`proxy route latency` − `respond route latency` ≈ the proxy layer's own cost.** This is the "core proxy layer metric".
>
> Use the difference to locate and compare, not as a strictly subtractable independent time: load, queueing and backend state change both paths, so compare under the same load and the same build.

So the backend VM is still needed (a proxy route needs a **real TCP upstream** to exercise dialing, pooling and copying), but it runs LiteGate `respond`, not nginx.

---

## 1. Test environment

### 1.1 Topology

```
[load generator gen] ──► [gateway under test gw] ──► [fake backend be]
  wrk2 / k6               LiteGate                    LiteGate (respond)
```

The three roles go on three VMs. **Never put the load generator and the gateway on the same VM**, or the generator takes the CPU and you measure contention, not the gateway.

### 1.2 VM sizing

| Role | VM | Suggested size | Software |
|---|---|---|---|
| Load generator | `gen` | 4–8 vCPU / 4G, **vCPU ≥ gateway** | wrk2, k6, vegeta |
| Gateway under test | `gw` | **Fixed 4 vCPU / 4G (the key variable, locked)** | LiteGate + node_exporter |
| Fake backend | `be` | 4 vCPU / 2G | LiteGate (respond) |

> The gateway's vCPU count is the object under test; **once chosen, don't change it**, or historical data can't be compared.

Use the same OS everywhere (Ubuntu Server 22.04 / Debian 12), on the same vSwitch and subnet.

### 1.3 Required ESXi settings

| Item | Requirement | Check |
|---|---|---|
| **No vCPU overcommit** | Total vCPUs ≤ physical cores; give gw and gen CPU **reservations** | esxtop `%RDY < 5%` |
| **Virtual NIC** | **vmxnet3** everywhere (not e1000) | — |
| **Host power policy** | High Performance, C-states off (BIOS + ESXi host) | — |
| **Generator and gateway don't compete for cores** | Put gen and gw on different NUMA nodes / physical hosts where possible | esxtop `%CSTP ≈ 0` |
| **Clock sync** | Install open-vm-tools | — |

### 1.4 Kernel tuning (all three VMs)

Linux defaults hit their limits before LiteGate does; adjust them before testing:

```bash
ulimit -n 1048576
sysctl -w net.ipv4.ip_local_port_range="1024 65535"
sysctl -w net.ipv4.tcp_tw_reuse=1
sysctl -w net.core.somaxconn=65535
sysctl -w net.ipv4.tcp_max_syn_backlog=65535
```

---

## 2. Node configuration

### 2.1 Fake backend (be)

`config.yaml`:

```yaml
mode: performance
http:
  port: 8080
sites_dir: ./sites
log:
  level: error        # errors only
  access_log:
    enabled: false    # access log off so the backend isn't the bottleneck
```

`sites/backend.yaml`:

```yaml
site: "0.0.0.0"
respond:
  status: 200
  body: "ok"
  content_type: "text/plain"
```

After starting, confirm `curl http://<be-ip>:8080/` returns `ok`.

> To test different response sizes or inject upstream latency, replace the backend with a configurable Go fake backend (response size and delay under control).

### 2.2 Gateway under test (gw)

`config.yaml`:

```yaml
# performance mode skips the per-request cost of dashboard real-time push (SSE) but keeps Prometheus metrics
mode: performance

http:
  port: 8080

# Metrics endpoint. Note: address defaults to 127.0.0.1; scraping across VMs requires 0.0.0.0
metrics:
  enabled: true
  address: "0.0.0.0"
  port: 9091           # scrape http://<gw-ip>:9091/metrics

# pprof. Also bound to 127.0.0.1 by default
pprof:
  enabled: true
  address: "0.0.0.0"
  port: 6060           # http://<gw-ip>:6060/debug/pprof/

sites_dir: ./sites

log:
  level: error
  access_log:
    enabled: false     # baseline round: access log off; run a separate round with it on for comparison
```

> ⚠️ `address: 0.0.0.0` exposes the metrics/pprof ports to the network. **Only on an isolated test network; never configure this in production.**

`sites/bench.yaml` (baseline route and proxy route together):

```yaml
site: "0.0.0.0"
# Baseline: pure gateway processing, no forwarding — the gateway floor
/respond:
  respond:
    status: 200
    body: "ok"
    content_type: "text/plain"

# Proxy: forward to be — the proxy layer
/proxy:
  proxy: "<be-ip>:8080"
  strip_prefix: true
```

### 2.3 Load generator (gen)

Install wrk2 (constant rate, corrects coordinated omission, trustworthy latency percentiles) and k6 (scriptable, cross-platform, supports WebSocket):

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

## 3. Running the tests

### 3.1 Basic procedure

1. **Baseline first**: gen directly against be records the backend's raw limit. Then go through gw; the difference is the gateway tax.
2. **Warm up**: run at a low rate for 30s so connection pools / GC settle, then load properly.
3. **Step up constant-rate load to find the knee** — not the maximum QPS, but **the step where P99 starts to curve up**; that step is the capacity limit.
4. **Change one variable per round** (response size / concurrency / keep-alive / TLS / HTTP2/3 / middleware on-off), or you can't attribute results.

### 3.2 Key comparison: isolating proxy layer cost

Hit both routes with the same load and subtract:

```bash
# Gateway floor: pure respond
wrk -t4 -c64 -R10000 -d60s --latency http://<gw-ip>:8080/respond

# Proxy path: forwarded to be
wrk -t4 -c64 -R10000 -d60s --latency http://<gw-ip>:8080/proxy/
```

You can also read the difference from the gateway's Prometheus metrics (see §4), more precisely.

### 3.3 Stepped load

```bash
for rate in 2000 5000 10000 20000 40000; do
  echo "=== ${rate} RPS ==="
  wrk -t4 -c128 -R${rate} -d60s --latency http://<gw-ip>:8080/proxy/
done
```

Record P50 / P90 / P99 / P99.9 and the error rate per step. The step where P99 starts rising non-linearly is the knee.

### 3.4 Capture the knee

When the latency knee appears, capture a CPU profile immediately:

```bash
go tool pprof -http=:0 'http://<gw-ip>:6060/debug/pprof/profile?seconds=30'
```

The flame graph tells you whether the bottleneck is route matching, GC, syscalls or a middleware. Capture `heap`, `goroutine` and `mutex` as well.

### 3.5 Scenario matrix (proxy layer)

Run them one by one; each targets a kind of proxy behavior:

| Scenario | Purpose | Key metrics |
|---|---|---|
| Small responses (<1KB) with keep-alive at full load | Peak forwarding QPS + own latency | Latency difference, goroutines, CPU |
| Large responses (1MB+) | Throughput / bandwidth, the `io.Copy` path | `http_response_bytes_total`, NIC, memory |
| New connection per request (no keep-alive) | Connection setup cost, fd pressure | goroutines, fd count |
| HTTPS / HTTP2 / HTTP3 | TLS and protocol overhead | CPU, handshake latency |
| WebSocket / Upgrade long connections | Tunnel concurrency limit | `litegate_proxy_active_tunnels`, goroutines, memory |
| Turn WAF / rate limiting / auth on one at a time | Quantify each middleware layer's cost | Latency difference comparison |

---

## 4. Metrics to read (all three layers together)

### A. Load generator (results)

QPS, **P50 / P90 / P99 / P99.9 latency**, error rate, timeouts. wrk2's `--latency` prints percentiles directly.

### B. LiteGate (attribution) — `http://<gw-ip>:9091/metrics`

| Metric | What to look for |
|---|---|
| `litegate_http_request_duration_seconds` vs `litegate_proxy_duration_seconds` | **The difference = the proxy's own overhead** (the most valuable number) |
| `litegate_goroutines_current` | Surging / not coming back down = a leak (watch closely with long connections) |
| `litegate_proxy_upstream_status_total{status_class}` | Do 5xx appear under load? |
| `litegate_proxy_requests_total{result}` | Distribution of forwarding results |
| `litegate_rate_limited_requests_total` / `litegate_waf_blocked_requests_total` | Make sure you aren't blocking yourself (mistaken for poor performance) |
| `litegate_circuit_breaker_state` | Unexpected breaker trips? (0=Closed, 1=Half, 2=Open) |
| `litegate_proxy_active_tunnels` | Active tunnels in WebSocket / Upgrade scenarios |

PromQL for the proxy layer's P99 overhead:

```promql
histogram_quantile(0.99, sum(rate(litegate_http_request_duration_seconds_bucket[1m])) by (le))
-
histogram_quantile(0.99, sum(rate(litegate_proxy_duration_seconds_bucket[1m])) by (le))
```

### C. Host / ESXi (bottleneck location)

- **Inside the VM** (node_exporter): CPU (including **sys%**), memory / GC, **fd count**, NIC bps/pps, `TIME_WAIT` connections.
- **ESXi layer** (esxtop, the most important virtualization health signals):
  - **`%RDY` (CPU Ready) must be < 5%** — above that, vCPUs are being preempted and latency data isn't trustworthy; add reservations or lower concurrency.
  - **`%CSTP` (co-stop) should be ≈ 0** — multi-vCPU synchronization waits.
  - Network `%DRPTX / %DRPRX` (drops) should be 0.

### How to read it

Latency curves up → **check esxtop `%RDY` first** to rule out ESXi stealing CPU → then look at gw's CPU `sys%` and the pprof flame graph to find whether it's route matching, GC, syscalls or a middleware.

---

## 5. Common pitfalls checklist

- [ ] Are the load generator and the gateway on separate machines? (on one machine results are always wrong)
- [ ] esxtop `%RDY < 5%`? (virtualization preemption pollutes all latency data)
- [ ] Virtual NIC vmxnet3, not e1000?
- [ ] `ulimit -n` and the ephemeral port range raised?
- [ ] Using wrk2 (constant rate) rather than wrk1 (open-loop maximum rate, which overestimates)?
- [ ] Confirmed the fake backend isn't the bottleneck? (watch be's CPU during the test)
- [ ] Tested with access logging both on and off? (log I/O is often a hidden bottleneck)
- [ ] metrics / pprof `address` set to `0.0.0.0` for cross-VM scraping?
- [ ] Only one variable changed per round?

## Related docs and examples

- [bench-lab: benchmark lab environment](../../../../examples/bench-lab/README.md)
- [bench-native: native service baseline](../../../../examples/bench-native/README.md)
- [bench-proxy: proxy benchmark configuration](../../../../examples/bench-proxy)
- [Metrics](../08-observability/metrics.md)
