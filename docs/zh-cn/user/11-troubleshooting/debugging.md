# 故障排查与调试 (Debugging Guide)

当 LiteGate 运行不及预期或出现报错时，可以按照以下步骤进行分层调试。

---

## 1. 检查日志 (Log Analysis)

日志是排查问题的首要信息源。

### 开启 Debug 级别日志
在 `config.yaml` 中设置级别，或通过命令行启动：
```bash
litegate --log-level debug
```

### 重点关注关键词
- **`ERROR: Failed to load site...`**: 站点 YAML 语法错误。
- **`WARN: All upstreams are critical...`**: 后端全线宕机。
- **`Violation: ... Detected`**: 被 WAF 或限流中间件拦截。

---

## 2. 网络连通性调试 (CURL)

确认网关是否正常接收请求：

```bash
# 测试本地回环
curl -v http://localhost/health

# 测试特定域名 (通过指定 Header)
curl -v -H "Host: api.example.com" http://127.0.0.1/
```

---

## 3. 服务发现调试

如果请求返回 `503 Service Unavailable`，说明网关找不到健康的后端。

1.  **检查 Dashboard**: 进入 `Discovery` 面板查看服务列表。
2.  **手动查询 API**:
    ```bash
    curl http://localhost:9999/status/json | jq .Discovery
    ```
3.  **检查发现中心**: 如果是 Consul，在浏览器查看 `http://consul-ip:8500` 是否有服务处于健康状态。

---

## 4. 常见报错及对策 (FAQ)

### 证书不安全 (小红叉)
- **原因**: 证书申请失败或过期。
- **对策**: 检查 Auto-Cert 日志，确认 80 端口和 DNS 解析。

### 接口跨域 (CORS Error)
- **原因**: 后端返回了重复的 CORS Header，或网关 `cors` 中间件未开启。
- **对策**: 使用控制台查看响应头，开启 `cors` 中间件。

### 请求重定向循环
- **原因**: `force_https` 与后端服务的跳转冲突。
- **对策**: 确认后端服务不要在 HTTP 层再次执行跳转。

---

## 5. 获取社区支持

如果仍无法解决，请准备好以下信息并联系我们：
1.  操作系统的类型与版本。
2.  `litegate --version` 输出。
3.  关键的错误日志片段。
4.  最小可复现的站点 YAML 配置。
