# 压测与性能归因

使用压力机 → 网关 → 独立后端三角色，避免压力生成器与网关抢 CPU。分别测 respond 基线、proxy 转发以及实际 middleware 配置。固定提交、构建参数、CPU/内存、网络、协议、响应体、连接复用与并发，记录完整命令和错误率。

延迟差可帮助定位代理成本，但不能当作严格可相减的独立时间；负载、排队和后端都会改变结果。虚拟机的 CPU 调度、网卡与宿主负载也影响测量，不承诺与裸金属等价。

观察吞吐、P50/P95/P99、超时、CPU、分配/GC、连接和后端利用率；逐步加压找到延迟与错误拐点。结合 pprof 与 Prometheus 定位瓶颈。使用仓库 bench-proxy、bench-native、bench-lab 示例复现实验，不能用未记录环境的峰值作为开源性能承诺。

## 相关文档与代码

- [Proxy benchmark](../../../../examples/bench-proxy)
- [Native benchmark](../../../../examples/bench-native/README.md)
- [Benchmark lab](../../../../examples/bench-lab/README.md)
- [Metrics](../08-observability/metrics.md)
