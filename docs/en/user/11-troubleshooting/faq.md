# Frequently Asked Questions (FAQ)

---

## 1. Installation & Bootstrapping

### Q: How do I install LiteGate?
**A:** Refer to the detailed [Installation & Quick Start Guide](../01-getting-started/installation.md).

### Q: LiteGate fails to start, throwing an "address already in use" error?
**A:** Modify the gateway port bindings inside `config.yaml` to use non-conflicting ports:
```yaml
http:
  port: 8080
  https_port: 8443
```

### Q: How do I bind LiteGate to privileged ports (such as 80 or 443) on Linux?
**A:** You can run the process via `sudo` or grant bound-service capabilities using `setcap`:
```bash
# Option 1: Execute with sudo
sudo litegate

# Option 2: Set kernel bind capabilities (Recommended best practice)
sudo setcap 'cap_net_bind_service=+ep' /usr/local/bin/litegate
litegate
```

---

## 2. Gateway Configurations

### Q: Where does LiteGate search for config files?
**A:** LiteGate scans the following pathways sequentially:
1. The pathway declared explicitly via the `--config` startup parameter flag.
2. The current working directory: `./config.yaml`.
3. The default system configuration directory: `/etc/litegate/config.yaml`.

### Q: How do I apply configuration modifications?
**A:** LiteGate automatically watches for filesystem changes in your configuration files. Configurations are hot-loaded in real-time without restarting active daemon processes or interrupting connections.

### Q: Does LiteGate support loading system environment variables?
**A:** Yes. Declare variables inside your configuration files using the standard `${VAR_NAME}` replacement syntax:
```yaml
auto_cert:
  email: ${ADMIN_EMAIL}
```

---

## 3. SSL/TLS Certificates

### Q: How do I enable automated HTTPS?
**A:** Turn on the `auto_cert` parameters block in your site YAML:
```yaml
auto_cert:
  enabled: true
  email: admin@example.com
```

### Q: Why is my ACME certificate generation failing?
**A:** Verify the following requirements:
1. Confirm your public DNS A-records resolve correctly to your gateway's IP address.
2. Confirm port 80 is open and publicly accessible from Let's Encrypt servers.
3. Check if you have exceeded Let's Encrypt's weekly certificate issuance rate-limits.

### Q: How do I configure wildcard SSL certificates?
**A:** Set up a globally defined DNS Provider under `auto_cert`:
```yaml
auto_cert:
  dns_providers:
    - name: aliyun
      type: aliyun
      domains: ["*.example.com"]
      config:
        access_key_id: "..."
        access_key_secret: "..."
```

---

## 4. Backends & Reverse Proxies

### Q: I am getting a "502 Bad Gateway" error. How do I fix it?
**A:** Verify the following issues:
1. Confirm your target backend microservice is active and running.
2. Confirm the physical IP address or hostname defined in the route's `upstream` block is correct.
3. Confirm the gateway host has routing connectivity to the backend service subnet.

### Q: The gateway returns "504 Gateway Timeout". How do I increase timeouts?
**A:** Adjust response timeouts inside your proxy action parameters:
```yaml
action:
  type: proxy
  upstream:
    - "backend:8080"
  response_header_timeout: 60s
```

### Q: How do I configure WebSocket connections?
**A:** LiteGate automatically detects and promotes WebSocket handshakes. Use standard proxy configurations:
```yaml
action:
  type: proxy
  upstream:
    - "ws-backend:8080"
  proto: http  # Keep proto as http; LiteGate automatically promotes WS requests
```

---

## 5. Performance Optimizations

### Q: How do I optimize LiteGate for high-traffic environments?
**A:** Refer to our [Production Deployment Best Practices](../10-deployment/production.md) blueprint.

### Q: LiteGate's memory footprint is higher than expected. How do I tune it?
**A:** The upstream connection pool is sized by built-in defaults tuned for high throughput; it is not configured via YAML. To reduce memory pressure, lower per-route concurrency (e.g. `rate_limit`) and set a sensible `http.response_header_timeout` in `config.yaml` so stalled upstreams release connections promptly:
```yaml
http:
  response_header_timeout: 30   # seconds
```

### Q: CPU utilization is spiking. What should I check?
**A:** Investigate the following potential causes:
1. Review if you have nested too many computationally heavy filters (e.g., extensive WAF regex checks or compression) on high-throughput routes.
2. Confirm that log levels are not set to `debug` in production.
3. Check if your backends are experiencing high volumes of error states or connection drops.

---

## 6. Telemetry & Monitoring

### Q: How do I access the visual administration panel?
**A:** Navigate to `http://localhost:9999` to access the Web Dashboard.

### Q: How do I integrate Prometheus metrics?
**A:** Turn on the global metrics configurations block:
```yaml
metrics:
  enabled: true
  port: 9091
```

### Q: Where are gateway logs written?
**A:** By default, logs write to standard stdout streams. You can configure file writers globally:
```yaml
log:
  level: info
  format: json
```

---

## 7. Troubleshooting & Verification

### Q: How do I enable debug log verbosity?
**A:** Start the gateway passing the `--log-level debug` flag, or declare it in your configuration:
```yaml
log:
  level: debug
```

### Q: How do I debug route evaluation paths and matcher cascades?
**A:** Send a test request containing the special administrative header `X-LiteGate-Debug: true` to get detailed routing decisions in response headers:
```bash
curl -H "X-LiteGate-Debug: true" http://localhost/
```

### Q: Why are configuration changes not taking effect?
**A:** Verify the following issues:
1. Check the gateway logs to ensure your YAML configuration files contain no syntax errors.
2. Review route ordering. LiteGate evaluates routes sequentially; a broader catch-all rule higher in the stack may intercept requests before they reach your target rule.

---

## 8. General Specifications

### Q: What operating systems are supported?
**A:** Linux, Windows, and macOS are fully supported.

### Q: Can LiteGate run in Docker?
**A:** Yes. Refer to the [Production Deployment Best Practices](../10-deployment/production.md) guide.

### Q: Is Kubernetes supported?
**A:** Yes, it is fully supported.

### Q: How do I contribute to the project?
**A:** Check out our [Contribution Guidelines](https://github.com/jamesleeon/LiteGate/blob/master/CONTRIBUTING.md).

---

## Getting Help
- [GitHub Issues](https://github.com/jamesleeon/LiteGate/issues)
- [GitHub Discussions Community](https://github.com/jamesleeon/LiteGate/discussions)
- [Troubleshooting & Debugging Guide](debugging.md)
