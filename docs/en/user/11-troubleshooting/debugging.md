# Troubleshooting & Debugging Guide

When LiteGate is not executing as expected or returns unexpected HTTP errors, DevOps and SRE teams can diagnose and resolve issues using this layered debugging framework.

---

## 1. Log Diagnostics

Process logs are the primary source of truth for L7 edge diagnostics.

### Activating Verbose Logging
Increase log verbosity directly inside `config.yaml` or pass execution flags during startup:

```bash
litegate --log-level debug
```

### Critical Log Markers to Watch:
- **`ERROR: Failed to load site...`**: Highlights YAML configuration parsing errors.
- **`WARN: All upstreams are critical...`**: Indicates that active health checks have marked all target backend instances unhealthy.
- **`Violation: ... Detected`**: Indicates that a request was blocked by WAF, IP restrictions, or rate limiters.

---

## 2. Ingress & Connectivity Testing

Ensure that your public WAN requests or internal queries are routing correctly to the gateway interface:

```bash
# Verify internal health check loop
curl -v http://localhost/health

# Test virtual host routing maps using host header flags
curl -v -H "Host: api.example.com" http://127.0.0.1/
```

---

## 3. Microservice Discovery Diagnostics

If incoming L7 requests yield **`503 Service Unavailable`** errors, LiteGate is unable to locate a healthy, registered backend instance for the requested routing prefix.

1. **Web Dashboard Inspection**: Navigate to the `Discovery` module on your Web Dashboard to review live service catalogs.
2. **REST API Queries**: Query the system status API and parse active catalog registers:
   ```bash
   curl -s http://localhost:9999/status/json | jq .Discovery
   ```
3. **Control Plane Health**: If Consul integration is active, query the active Consul UI agent at `http://consul-ip:8500` to verify that backend health states are marked as `Passing`.

---

## 4. Diagnostics for Common Error Scenarios

### TLS/SSL Handshake Failures ("Not Secure" Warnings)
- **Root Cause**: ACME certificate request handshakes failed, or a self-signed fallback certificate is active.
- **Resolution**: Check the Auto-Cert logs. Verify that port 80 is accessible from Let's Encrypt servers (for HTTP-01 challenges) and confirm that your public DNS A-records are fully propagated.

### CORS Header Conflicts
- **Root Cause**: Backend applications return duplicate CORS headers that conflict with those injected by the gateway's `cors` middleware, or the `cors` middleware is missing key configuration flags.
- **Resolution**: Inspect browser network panels to see if multiple `Access-Control-Allow-Origin` values are returned. Adjust your gateway `cors` configuration or upstream headers to prevent duplicates.

### Infinite Redirect Loops
- **Root Cause**: The gateway's `force_https` redirect rules conflict with downstream HTTP redirections implemented inside your application web server.
- **Resolution**: Confirm that downstream application servers do not redirect secure HTTPS traffic back to plain HTTP.

---

## 5. Submitting Community Support Tickets

If a diagnostic issue remains unresolved, compile the following system footprint details before submitting support requests:
1. Host operating system type and kernel version (e.g. `cat /etc/os-release`).
2. Gateway output details returned by: `litegate --version`.
3. Anonymized log payloads showing the exception trace.
4. A minimal, reproducible YAML site configuration.
