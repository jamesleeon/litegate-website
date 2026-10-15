# WebDAV 文件共享（v2）

保存为 `sites/webdav.yaml`，或当前 KV 站点前缀下的 `webdav.yaml`；两种来源使用相同的 YAML。

## 基础配置

```yaml
site: https://cloud.example.com
webdav: ./shared
```

此示例公开读写，仅适合受信环境。预先创建目录，相对路径以 LiteGate 工作目录为基准。HTTPS 证书需要满足全局配置和域名验证条件。

## 路径挂载与认证

运行 `litegate -hash "your-password"` 生成 bcrypt 密码哈希，把生成的哈希替换到 users.alice：

```yaml
site: https://cloud.example.com
/dav:
  webdav:
    root: ./private-data
    web_ui: true
    browse: false
    direct_download: false
  auth:
    type: basic
    realm: Private Storage
    users:
      alice: "<bcrypt-hash>"
    permissions:
      alice: rw
```

连接地址为 `https://cloud.example.com/dav/`。处理器自动使用匹配的 `/dav` 前缀，无需额外配置 strip_prefix，也不要再次通过 rewrite 剥离。

- auth 与 webdav 平级；文件服务选项写在 webdav 映射内。
- rw 允许读写，ro 限制账号只读；webdav.read_only: true 设置默认只读，但显式账号 rw 可覆盖；需要所有账号只读时，将权限统一设为 ro。
- web_ui 启用浏览器界面；browse: false 和 direct_download: false 禁止匿名浏览和直接下载。
- WebDAV 需要 PROPFIND、PUT、MKCOL、DELETE、MOVE、COPY、LOCK 等方法，不要把路由限制为 GET/POST。
- 文件存储在本地目录，WebDAV 不支持 kv_mode；通过 KV 加载站点配置不等于把文件存入 KV。

## 管理员登录界面，不开放匿名共享

以下是 LiteGate 内置的表单登录与 SSO cookie，使用本地管理员账号；不需要 OIDC Provider。用独立域名承载整个 WebDAV 站点，登录路径 `/_auth/login` 也由同一配置处理：

```yaml
site: https://files.example.com
webdav:
  root: ./private-data
  web_ui: true
  browse: false
  direct_download: false
auth:
  type: sso
  sso_enabled: true
  allow_anonymous: false
  secret: "REPLACE_WITH_A_RANDOM_SECRET_AT_LEAST_32_BYTES"
  cookie_secure: true
  cookie_same_site: lax
  session_ttl: 3600
  users:
    admin: "<bcrypt-hash>"
  permissions:
    admin: rw
```

用 `litegate -hash "your-password"` 生成管理员密码哈希。secret 替换为随机的至少 32 字节密钥；此私有站点使用独立密钥，避免接受其他站点签发的 SSO cookie。只定义允许进入的管理员账号；permissions 控制读写，不是登录账号白名单。

浏览器访问 `https://files.example.com/`，未登录会跳转登录页。匿名目录浏览与直接文件下载均关闭。常规 WebDAV 客户端使用同一个 admin 账号的 Basic Auth；通常无法完成浏览器表单登录。此配置限制访问权限，若要求公网无法连接，还需通过私网监听、VPN 或 IP 限制控制网络入口。

如果指的是 Keycloak、Authentik 等外部统一登录，请参阅 [OIDC](../05-middleware/oidc.md)。`remote_auth` 的登录态与这里的 WebDAV 本地账号 SSO 不同，不能仅开启 OIDC 就认为完成了管理员角色限制。

## 连接与排查

在系统或 WebDAV 客户端中填写上述 HTTPS 地址、用户名和密码。401 检查认证；403 检查账号权限、read_only 和进程对目录的文件系统权限。路径异常时检查前置代理是否保留 /dav；上传失败检查磁盘及前置代理的大小／超时限制，不要使用不存在的 http.write_timeout 字段。HTTPS 失败先检查 DNS、证书和监听器。

使用 `litegate -t -config config.yaml` 校验配置。

## 延伸阅读

- [v2 站点配置](../03-configuration/site-config.md)
- [Basic Auth](../05-middleware/basic-auth.md)
- [静态文件服务](serve.md)
