# 文件浏览器：List、图片查看与本地 SSO

此配置提供登录后访问的文件浏览器，包括列表／网格切换、图片预览、页面内上一张／下一张、搜索、排序和文件下载。目录、图片原文件和下载使用同一个 SSO 登录态。

下载配置：

- [list-config.yaml：全局入口配置](list-config.yaml)
- [list-sso.yaml：文件浏览与 SSO 站点配置](list-sso.yaml)

## 1. 准备目录和配置

使用独立工作目录，将 `list-config.yaml` 复制为 `config.yaml`，将 `list-sso.yaml` 复制为 `sites/list.yaml`。准备以下目录，将要分享的文件和图片放入 `www`：

```text
file-browser/
├── config.yaml
├── sites/
│   └── list.yaml
├── streams/
└── www/
    └── images/
```

修改全局配置中的 `entrypoints.web.address` 和站点中的 `site`，使其对应服务器实际 IP。示例地址为 `192.168.50.24:18091`；本机测试可以改用 `127.0.0.1:18091` 和 `site: 127.0.0.1`。将 `list.root` 改为实际共享目录，相对路径以启动 LiteGate 的工作目录为基准。

已有 LiteGate 实例只需合并站点配置，并将 `entrypoints: [web]` 改成实际入口名称；不要直接覆盖已有全局配置。

## 2. 配置登录账号

生成独立会话密钥与密码哈希：

```sh
litegate -secret
litegate -hash 'replace-with-your-own-password'
```

将生成的密钥填入 `auth.secret`，将 bcrypt 哈希填入 `auth.users.demo`，也可以将 `demo` 改为自己的用户名。保留哈希中的 `$` 字符，不填写明文密码。示例不包含测试服务器的真实账号密码或密钥。

此演示使用 HTTP，所以 `cookie_secure: false`。正式部署应使用 HTTPS，并设置 `cookie_secure: true`。会话有效期为 3600 秒；此本地 SSO 无需外部身份服务，不提供跨域统一登录或 MFA。

## 3. 校验与启动

在上述工作目录运行：

```sh
litegate -t -config ./config.yaml
litegate -config ./config.yaml
```

访问 `http://192.168.50.24:18091/`，未登录会跳转到登录页。输入配置的账号密码后返回文件列表，页面底部的 **Sign out** 可退出。

点击 **List / Grid** 切换布局；点击图片打开页面内查看器，用上一张／下一张按钮、左右方向键或手机滑动浏览，按 Esc 或 **Close** 关闭。图片浏览按当前搜索结果及排序顺序进行。预览延迟加载原图，服务端不生成独立缩略图。

`show_hidden: false` 会隐藏并禁止直接访问点号开头的路径。`list` 始终展示目录，不自动优先打开 `index.html`。`auth` 与 `list` 在此示例中均放在站点根级；若改成 `routes`，应将认证配置放入对应路由，并确保登录路径也由认证路由处理。

## 相关文档

- [List](../04-actions/list.md)
- [认证与 SSO](../05-middleware/authentication.md)
