# Large transfers and request body protection

`rate_limit` limits request counts; `bandwidth` limits upload and download bytes per second. Proxy requests and file responses remain streaming.

Global configuration (`config.yaml`):

```yaml
http:
  max_request_body_size: 67108864 # Default 64MiB; 0 means unlimited
  body_buffer_budget: 67108864   # Default 64MiB; 0 selects the default budget
  bandwidth:
    total_upload: 20971520       # All routed traffic in this process: 20MiB/s
    total_download: 52428800     # All routed traffic in this process: 50MiB/s
```

Site configuration:

```yaml
site: files.example.com
max_request_body_size: 1048576
bandwidth:
  total_download: 20971520

/upload:
  max_request_body_size: 4294967296 # 4GiB; explicit 0 means unlimited
  bandwidth:
    key: ip
    upload: 2097152
    download: 4194304
    total_upload: 10485760
  limit_conn: 4
  limit_conn_key: ip
  proxy: http://127.0.0.1:8080

/:
  serve: ./public
```

Rates are integer **bytes/second**; 0 disables that rate. `key` defaults to `ip`, using LiteGate's trusted client IP resolution rather than accepting arbitrary forwarding headers. `global` shares `upload` / `download` across all requests in that scope. Concurrent connections from one IP share their quota, including users behind the same NAT. Upload and download are independent.

Global, site and route quotas apply together. Site quotas span every route in that site; route quotas span every connection to that route. Token buckets allow an initial burst of at most 32KiB, or one second of quota for lower rates. Waiting responds to cancellation and deadlines. Adjust proxy timeouts for the intended file size and rate, and combine bandwidth quotas with `limit_conn` to bound long-lived requests.

Body size uses the explicit route value, then a positive site value, then the global value. Site 0 inherits the global setting; explicit route 0 allows unlimited size. A declared length exceeding the limit returns 413 before reading the body. Chunked and unknown-length bodies are limited while reading. A rejected streaming upload may already have sent a prefix to the backend; the backend must clean up failed uploads and commit files atomically. A limit error after the response has been committed cannot change its earlier status.

Retry buffering only handles known lengths below 1MiB. Larger and unknown-length bodies stream without retries or proxy mirroring. `disable_chunked` still buffers at most 2MiB and is unsuitable for large uploads. The named mirror middleware has a separate 4MiB body limit.

`body_buffer_budget` is a process-wide shared budget for proxy replay, `disable_chunked` and named mirror buffers. Reservations account for three times the read limit to cover buffer growth and remain held until asynchronous readers and mirrors finish. Budget exhaustion skips optional retry buffering or mirroring; mandatory `disable_chunked` buffering returns 503. This is not a process RSS limit: connections, IDS, response caches and plugins have their own overhead.

Bandwidth limits cover regular HTTP uploads, proxy responses, static files and cache hits. Download accounting counts compressed HTTP body bytes, excluding protocol and TLS overhead. WebSocket, CONNECT and other hijacked tunnel traffic are outside this feature. Quotas are local to one instance.

Handler rebuilds reuse limiter state. Idle client keys expire after five minutes. The process retains at most 10,000 client keys and 4,096 scopes; capacity exhaustion returns 503 with `Retry-After: 60`.

The new default 64MiB body limit changes unconfigured upload endpoints. Configure a suitable route override before upgrading those endpoints.
