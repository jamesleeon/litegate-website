# WebDAV Action (文件管理服务)

LiteGate 内置了高性能的 WebDAV 处理器，允许您将服务器上的目录挂载为网络磁盘。它支持跨平台（Windows, macOS, Linux）访问，并与网关的认证中间件完美集成。

---

## 1. 基础配置 (Basic WebDAV)

```yaml
domain: cloud.example.com
routes:
  - name: my-storage
    match:
      path_prefix: /dav
    action:
      type: webdav
      root: "/data/shared"   # 需要挂载的本地目录
      strip_prefix: "/dav"   # 必须剥离路径前缀，否则 WebDAV 会报错
```

---

## 2. 权限与安全

> [!IMPORTANT]
> **强烈建议**: 生产环境下使用 WebDAV 务必开启 `authentication` 中间件，避免数据泄露。

```yaml
domain: cloud.example.com
routes:
  - name: dav-private
    match:
      path_prefix: /
    action:
      type: webdav
      root: "./private-data"
      auth:
        type: basic
        realm: "Private Storage"
        users:
          alice: "<sha256-hash>"     # 用 litegate -hash "你的密码" 生成
        permissions:
          alice: "rw"                # rw(读写)或 ro(只读)
```

---

## 3. 如何挂载到操作系统？

### Windows
1. 打开“此电脑”，点击上方“映射网络驱动器”。
2. 输入地址：`https://cloud.example.com/`。
3. 输入用户名与密码（如果您开启了认证）。

### macOS (Finder)
1. 在 Finder 中按下 `Cmd + K`。
2. 输入地址：`http://cloud.example.com/`（推荐使用 HTTPS）。
3. 点击“连接”。

---

## 4. 常见问题排查 (FAQ)

### 无法删除或重命名文件？
- 确保运行 LiteGate 的用户对 `root` 目录拥有读写权限。
- 检查 `strip_prefix` 是否配置正确。

### 大文件上传超时？
- 调整全局配置 `http.write_timeout`。
- 如果使用了 Nginx 等前置代理，请调大 `client_max_body_size`。

---

## 延伸阅读
- [配置 Basic Auth 认证](../05-middleware/authentication.md)
- [使用 Serve Action 进行静态预览](./serve.md)
