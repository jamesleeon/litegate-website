# WebSocket 代理

LiteGate **原生支持** WebSocket 协议代理，无需额外配置。当客户端发起 WebSocket 升级请求时，网关会自动检测并切换到 WebSocket 代理模式。

---

## 1. 基础配置

只需正常配置 `proxy` Action 即可：

```yaml
domain: ws.example.com
routes:
  - name: websocket-api
    match:
      path_prefix: /ws
    action:
      type: proxy
      upstream: ["10.0.0.5:8080"]
```

LiteGate 会自动处理 `Connection: Upgrade` 和 `Upgrade: websocket` 头部。

---

## 2. 超时配置

WebSocket 连接通常是长生命周期的。如果遇到连接被意外断开的情况，请调整超时参数：

```yaml
action:
  type: proxy
  upstream: ["10.0.0.5:8080"]
  flush_interval: -1          # 启用即时刷新（推荐）
```

---

## 3. 安全 WebSocket (WSS)

当站点启用 HTTPS 后（`force_https: true`），WebSocket 会自动升级为 WSS。客户端使用 `wss://` 协议连接即可。

---

## 4. 负载均衡注意事项

> [!IMPORTANT]
> WebSocket 连接一旦建立，会持续绑定到某一个后端实例。负载均衡仅在连接建立阶段生效。如果需要会话粘性，建议使用 `ip_hash` 策略。

---

## 5. 常见问题

### 连接后立即断开？
- 检查后端服务是否正确实现了 WebSocket 握手。
- 如果有中间代理（如 Nginx），确保其也配置了 WebSocket 支持。

### 大量 WebSocket 连接导致内存过高？
- WebSocket 每个连接会占用一个 Goroutine。建议在操作系统层面调整 `ulimit -n`。
