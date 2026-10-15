# LiteGate v2 快速上线指南

新建配置使用普通 .yaml 文件与顶层 site，不需要选择 Lite 或标准模式。旧 .lite.yaml 文件继续兼容。

## 最快上线

运行 `litegate -hello`，在本机 8080 端口体验 hello world。正式配置保存为 sites/app.yaml：

```yaml
site: https://app.example.com
/api:
  proxy: 127.0.0.1:8080
  strip_prefix: true
spa: ./dist
```

裸域名默认不启用 HTTPS 跳转，使用 https:// 或 https: true 显式启用。复杂条件使用 routes 与 match；高级选项使用 action。这些都是 v2 的配置能力。

- [WebDAV v2 指南](user/04-actions/webdav.md)
- [站点配置](user/03-configuration/site-config.md)
- [快速开始](user/01-getting-started/quick-start.md)
