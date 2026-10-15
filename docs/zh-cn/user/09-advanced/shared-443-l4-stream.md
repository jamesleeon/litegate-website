# 共享 443：HTTPS 与 L4 Stream

TCP/443 可根据 TLS ClientHello 的 SNI 分流到 L4 Stream 或普通 HTTPS。它是一个监听器选择处理管道；未命中的连接继续 HTTPS，探测读取的字节会回放。HTTP/3 使用独立 UDP 监听，不参与 TCP SNI 分流。

挂载 Stream 使用 listen: false、entrypoints 和 hostnames，不再独立绑定同一端口。可以原样透传 TLS，或由 LiteGate 终止 TLS 后访问 TCP/Unix Socket 上游。终止 TLS 需要有效证书；Unix Socket 使用静态绝对路径。

明确设置入口对非 TLS、无 SNI 的处理，不依靠隐式兜底。检查域名冲突、证书覆盖、后端协议及权限。测试 HTTPS 和 Stream 同时可用，再验证热更新与删除 Stream 后的回退。

```yaml
entrypoints:
  websecure:
    address: ':443'
    tls: true
    default: http
    on_non_tls: reject
    on_no_sni: reject
```

```yaml
name: database
listen: false
entrypoints: [websecure]
hostnames: [db.example.com]
protocol: tcp
upstream: unix:///run/litegate/database.sock
enabled: true
tls:
  enabled: true
  auto_cert: true
  min_version: '1.2'
```

## 相关文档与代码

- [Entrypoints](../03-configuration/entrypoints.md)
- [Stream guide](../03-configuration/stream-config.md)
