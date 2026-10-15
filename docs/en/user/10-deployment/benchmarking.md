# Benchmarking and performance attribution

Use separate load-generator → gateway → backend roles to avoid CPU competition. Measure a respond baseline, proxy forwarding and the actual middleware configuration separately. Fix the commit, build flags, CPU/memory, network, protocol, response size, connection reuse and concurrency; record full commands and error rates.

Latency differences help investigate proxy costs but are not strictly additive independent timings: load, queueing and backend behavior change the result. VM scheduling, network adapters and host contention also affect measurements; do not promise bare-metal equivalence.

Track throughput, P50/P95/P99, timeouts, CPU, allocations/GC, connections and backend utilization. Increase load gradually to locate latency/error inflection points. Use pprof and Prometheus for attribution. Reproduce experiments with bench-proxy, bench-native and bench-lab examples; peaks without recorded environments are not public performance guarantees.

## Related documentation and code

- [Proxy benchmark](../../../../examples/bench-proxy)
- [Native benchmark](../../../../examples/bench-native/README.md)
- [Benchmark lab](../../../../examples/bench-lab/README.md)
- [Metrics](../08-observability/metrics.md)
