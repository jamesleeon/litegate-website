# 常见问题 (FAQ)

## 安装与启动

### Q: 如何安装 LiteGate?

A: 参见 [安装指南](../01-getting-started/installation.md)

### Q: 启动时提示端口被占用?

A: 修改配置文件中的端口:
```yaml
http:
  port: 8080
  https_port: 8443
```

### Q: 如何在 Linux 上监听 80/443 端口?

A: 使用 sudo 或 setcap:
```bash
# 方式1: sudo
sudo litegate

# 方式2: setcap
sudo setcap 'cap_net_bind_service=+ep' /usr/local/bin/litegate
litegate
```

## 配置

### Q: 配置文件在哪里?

A: 默认查找顺序:
1. `--config` 参数指定的路径
2. `./config.yaml`
3. `/etc/litegate/config.yaml`

### Q: 如何热更新配置?

A: LiteGate 自动监听配置文件变化,无需重启。

### Q: 支持环境变量吗?

A: 支持,使用 `${VAR_NAME}` 语法:
```yaml
auto_cert:
  email: ${ADMIN_EMAIL}
```

## 证书

### Q: 如何启用 HTTPS?

A: 配置 Auto-Cert:
```yaml
auto_cert:
  enabled: true
  email: admin@example.com
```

### Q: 证书申请失败?

A: 检查:
1. 域名 DNS 是否正确解析
2. 80 端口是否可访问
3. 是否触发速率限制

### Q: 如何使用通配符证书?

A: 配置 DNS Provider:
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

## 代理

### Q: 502 Bad Gateway?

A: 检查:
1. 后端服务是否运行
2. 后端地址是否正确
3. 网络是否连通

### Q: 504 Gateway Timeout?

A: 增加超时时间:
```yaml
action:
  type: proxy
  upstream:
    - "backend:8080"
  response_header_timeout: 60s
```

### Q: WebSocket 连接失败?

A: 确保配置正确:
```yaml
action:
  type: proxy
  upstream:
    - "ws-backend:8080"
  proto: http  # LiteGate 自动检测 WebSocket
```

## 性能

### Q: 如何提升性能?

A: 参见 [生产环境部署建议](../10-deployment/production.md)

### Q: 内存占用过高?

A: 上游连接池使用内置的高吞吐默认值,不通过 YAML 调整。要降低内存压力,可减小单路由并发(如 `rate_limit`),并在 `config.yaml` 里设置合理的 `http.response_header_timeout`,让卡住的上游尽快释放连接:
```yaml
http:
  response_header_timeout: 30   # 秒
```

### Q: CPU 占用过高?

A: 检查:
1. 是否启用了过多中间件
2. 日志级别是否为 debug
3. 是否有大量错误请求

## 监控

### Q: 如何查看实时状态?

A: 访问 Dashboard: `http://localhost:9999`

### Q: 如何集成 Prometheus?

A: 启用 Metrics:
```yaml
metrics:
  enabled: true
  port: 9090
```

### Q: 日志在哪里?

A: 默认输出到 stdout,可配置:
```yaml
log:
  level: info
  format: json
```

## 故障排查

### Q: 如何开启调试日志?

A: 
```bash
litegate --log-level debug
```

或配置文件:
```yaml
log:
  level: debug
```

### Q: 如何查看详细的路由匹配?

A: 添加 Header:
```bash
curl -H "X-LiteGate-Debug: true" http://localhost/
```

### Q: 配置不生效?

A: 检查:
1. 配置文件语法是否正确
2. 查看日志是否有错误
3. 路由优先级是否正确

## 其他

### Q: 支持哪些操作系统?

A: Linux, Windows, macOS

### Q: 支持 Docker 吗?

A: 支持,参见 [生产环境部署](../10-deployment/production.md)

### Q: 支持 Kubernetes 吗?

A: 支持,参见 [生产环境部署](../10-deployment/production.md)

### Q: 如何贡献代码?

A: 参见 [贡献指南](https://github.com/jamesleeon/LiteGate/blob/master/CONTRIBUTING.md)

## 获取帮助

- [GitHub Issues](https://github.com/jamesleeon/LiteGate/issues)
- [讨论社区](https://github.com/jamesleeon/LiteGate/discussions)
- [故障排查](debugging.md)
