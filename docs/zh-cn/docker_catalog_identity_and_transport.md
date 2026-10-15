# Docker catalog 标识和连接配置

## 位置标识的迁移

**不兼容变更：原来的 `discovery.instance: docker/0`、`docker/1` 等位置标识不再生效，需要改成 catalog 名。** 旧引用不会按位置自动绑定到另一个守护进程。

多个 Docker catalog 应配置唯一的 `name`。例如 catalog 名为 `daemon-b` 时，`discovery.instance` 可写 `daemon-b` 或 `docker/daemon-b`。调整 catalog 顺序不会改变服务归属或显式引用。

加载和预览站点配置时，显式 `discovery.instance` 必须对应一个已启用的 Docker catalog。旧位置引用、拼错名称或引用已禁用的 catalog 会直接报错，并提示可用名称；不会等到请求时才表现为 503。主配置 reload 也会检查现有路由及服务图叶子的引用，拒绝移除仍被使用的 catalog。校验依据 catalog 配置，不要求守护进程在线或服务已产生实例。

未命名的 catalog 用连接地址与 namespace 的 SHA-256 生成稳定标识。这串哈希供系统内部使用，**需要显式引用 catalog 时，请给它起名**。重复标识会使配置校验失败，请为这些 catalog 配置不同名称。

```yaml
service_discovery:
  catalogs:
    - name: daemon-b
      enabled: true
      provider: docker
      namespace: default
      socket_path: tcp://docker-b.example:2376
      default_domain: b.example
      tls:
        ca_file: /etc/litegate/docker-b/ca.pem
        cert_file: /etc/litegate/docker-b/cert.pem
        key_file: /etc/litegate/docker-b/key.pem
```

## TLS 和连接方式

`tls` 配置按 catalog 隔离，覆盖全局证书目录；`cert_file` 和 `key_file` 必须同时指定。`tls.*` 只适用于 `tcp://` 或 `https://` 端点，配在 SSH、Unix socket、Windows named pipe 或 `http://` 上会被拒绝。省略 `socket_path` 时会校验 `DOCKER_HOST`；两者均未设置时，默认本地 socket 不接受 TLS 配置。

TCP 配置 TLS 后使用 HTTPS。无 TLS 的 HTTP/TCP 连接会在初始化时输出警告。Windows 默认连接 `npipe:////./pipe/docker_engine`，也可显式指定此地址。

首次 API 请求通过 `/version` 协商，使用守护进程与客户端共同支持的版本（客户端最高 1.47）。协商失败可重试；仅 `/version` 返回 404 的旧代理保持无版本路径兼容。

## 同步和 Swarm 网络选择

standalone 每 60 秒全量对账，事件更新与全量同步互斥。内部网络、明确端口且列表信息完整的容器直接使用列表摘要，保留健康状态；host 网络、host 端口映射和不完整摘要仍需 inspect。

Swarm 默认按配置周期轮询，检测到服务 `UpdateStatus.State` 为 `updating` 或 `rollback_started` 后，将超过 1 秒的周期暂时缩短到 1 秒；更新或回滚结束后恢复配置周期。

网络选择依次为显式指定网络、网关共享网络、按名称排序的其他非 ingress 网络。显式设置 `litegate.docker.network`，但 task 在该网络上没有可用地址时，会给出警告诊断，再尝试回退。Docker Stack 的网络名前缀同样参与匹配。无有效非 ingress 地址时跳过 task 并记录错误诊断；重复日志仅在 task 状态变化后输出。
