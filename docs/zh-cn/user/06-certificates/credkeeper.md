# LiteGate CredKeeper - DNS 凭证安全托管服务使用指南

> 默认 LiteGate 内置阿里云、腾讯云和 Cloudflare。本文的华为云配置需要先将对应第三方 DNS Provider 插件编译进 LiteGate；CredKeeper 可继续保存这些服务商的凭据。

## 一、背景与设计初衷

在使用 ACME 协议申请泛域名（Wildcard `*.example.com`）证书时，协议强制要求执行 **DNS-01 挑战**。这意味着网关系统通常需要调用公有云厂商（如阿里云、腾讯云、华为云、Cloudflare）的 DNS API，在域名解析中动态添加 `_acme-challenge` TXT 记录。

然而在企业私有化交付、金融合规或多租户场景下，存在以下关键安全痛点：
1. **禁止明文配置高危密钥**：公有云账号的全局 `AccessKey Secret` 属于高危凭证，直接以明文写在网关服务器的 `config.yaml` 或配置文件中，极易因配置文件泄露、代码误提交或主机运维审计违规导致核心资产面临威胁。
2. **禁止明文落盘（At-Rest Security）**：安全等保规范通常要求敏感机密在磁盘持久化时必须使用行业标准强加密（如 AES-256），防止脱机拷贝磁盘获取明文。
3. **集中管理**：多台网关共用一套云厂商凭据时，希望在一处录入、一处轮换。

为此，LiteGate 提供了 **CredKeeper**（凭据托管服务）。它作为一个独立的极简可执行程序部署在客户受控机房内，提供 Web 控制台录入凭据，本地 AES-256-GCM 加密落盘，LiteGate 按需拉取并只在内存中使用。

> **先看看是否需要 CredKeeper**：如果只是不想在 yaml 里写明文 AK/SK，更简单的做法是 [密文配置（Sealed Secrets）](sealed-secrets.md)：yaml 里直接写 `enc://` 密文，无需部署额外服务。CredKeeper 更适合多台网关集中管理凭据的场景。

> **安全边界说明**：
> - `secret_token` 同时用于鉴权和解密。拿到它的人就能取回全部凭据，因此它本身**不要明文写在 yaml 里**，请写成 `enc://` 密文或 `file://` 引用（见第六节）。
> - CredKeeper 默认只监听 `127.0.0.1`。跨主机部署走内网 HTTP 时，token 会随请求头传输，**内网传输安全由客户网络环境负责**；有抓包顾虑请在前面加 HTTPS。

> **适用场景说明**：
> - **常规单域名/多域名（开放公网 80 端口）**：直接使用标准的 **HTTP-01 验证** 即可，LiteGate 会自动拦截 `/.well-known/acme-challenge/*` 完成颁发，**完全不需要任何云厂商凭证或 CredKeeper**。
> - **泛域名证书（`*.example.com`）或内网无法暴露 80 端口的环境**：ACME 协议强制要求 **DNS-01 验证**，此时强烈推荐配合 **CredKeeper** 进行密钥安全托管。

---

## 二、架构设计与加密原理

```
                     +-------------------------------------------------------------+
                     |                    客户受控内网主机                          |
                     |                                                             |
+----------------+   |   +-----------------------------------------------------+   |
| 客户安全运维人员 |   |   | 内嵌 Web 控制台 (http://localhost:8088)              |   |
| 浏览器访问     | ----->| 1. 设置主通信密钥 Token                               |   |
+----------------+   |   | 2. 录入各云厂商 AK/SK                                |   |
                     |   +--------------------------+--------------------------+   |
                     |                              | 点击【加密并保存到本地】        |
                     |                              | SHA-256(Token) -> AES Key   |
                     |                              v                              |
                     |   +-----------------------------------------------------+   |
                     |   | 本地密文文件 data/credentials.enc (全密文落盘无明文)   |   |
                     |   +--------------------------+--------------------------+   |
                     |                              |                              |
                     |                              | 3. HTTP GET /v1/secret/:name |
+----------------+   |                              |    (带 Token Bearer 鉴权)    |
| LiteGate 网关  |<=================================+                              |
| (业务节点)     |   |   4. 返回: { encrypted: true, nonce: "...",                 |
+----------------+   |             ciphertext: "动态随机Nonce加密密文" }           |
  内存用 Token 解密  +-------------------------------------------------------------+
  执行 ACME 申请
  用完即焚不留存
```

### 1. 密钥衍生（Key Derivation）
系统使用双方约定的高熵字符串 Token（或通过界面一键生成的 32 字符随机口令），经由 `SHA-256` 算法严格衍生出 32 字节的二进制主密钥。

### 2. 本地静态加密存储（Storage at Rest）
所有凭证经由 `AES-256-GCM` 认证加密后以 JSON 格式原子写入本地磁盘（默认 `data/credentials.enc`）。脱机导出该文件只能看到密文与随机 Nonce，脱离 Token 无法还原任何明文。

### 3. 响应载荷加密
LiteGate 发起 `GET` 获取凭证时，CredKeeper 通过 Token 鉴权后，用随机 Nonce 对凭据加密后返回，响应体里不出现明文。
注意：这一层加密与鉴权使用同一个 Token，而 Token 在请求头中传输，因此它**不能替代 HTTPS**。它的作用是避免响应明文出现在代理日志、调试输出中；需要防御网络抓包时请使用 HTTPS 或仅在本机回环地址访问。

### 4. LiteGate 端透明解密
LiteGate 内置机密解析器（`internal/secret`）在接收到标有 `"encrypted": true` 的载荷时，自动利用 `config.yaml` 中配置的 `secret_token` 执行端到端解密，并在内存中完成 DNS-01 验证，网关本地不生成持久化文件（为减少请求，解密结果会在内存中缓存 5 分钟；CredKeeper 返回 401/403 时缓存立即失效）。

---

## 三、支持的 4 大 DNS 服务商字段规范

CredKeeper Web 界面完整覆盖了 LiteGate 原生支持的全部 4 个主流 DNS 提供商：

| 提供商名称 | 类型标识 (`type`) | 必填字段 | 可选字段 | 权限建议 |
| :--- | :--- | :--- | :--- | :--- |
| **阿里云 (Aliyun DNS)** | `aliyun` | `access_key_id`<br>`access_key_secret` | `zone`（托管域，缺省按 SOA 自动查找） | RAM 用户授予 `AliyunDNSFullAccess` 或指定域名解析修改权限 |
| **腾讯云 (Tencent Cloud)** | `tencent` | `secret_id`<br>`secret_key` | 无 | CAM 密钥授予 `QcloudDNSPodFullAccess` |
| **华为云 (Huawei Cloud)** | `huawei` | `access_key_id`<br>`secret_access_key` | `region` (默认 `cn-north-1`) | IAM 用户具备 DNS Administrator 或指定域名操作权限 |
| **Cloudflare** | `cloudflare` | **模式 1 (推荐)**：`api_token`<br>**模式 2 (传统)**：`api_key` + `email` | `timeout` (默认 `120s`) | 仅需分配 `Zone.DNS:Edit` 权限令牌，权限最小化更安全 |

---

## 四、编译与启动指南

### 1. 编译二进制
在项目根目录执行 Makefile 指令：

```bash
# 本地单架构编译（输出到 cmd/bin/credkeeper 或 credkeeper.exe）
make credkeeper

# 或者全平台统一编译（同时产出 Windows/Linux/macOS 多架构包）
make all
```

### 2. 命令行参数与环境变量

CredKeeper 支持极简命令行参数，同时也完全支持环境变量配置（非常适合容器化或 Systemd 托管）：

| 参数名 | 对应环境变量 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `-port` | `CREDKEEPER_PORT` | `8088` | HTTP 服务监听端口 |
| `-host` | `CREDKEEPER_HOST` | `127.0.0.1` | HTTP 服务监听网卡 IP。仅当 LiteGate 在其他主机上时才改为内网 IP 或 `0.0.0.0` |
| `-data` | `CREDKEEPER_DATA_FILE` | `data/credentials.enc` | 本地加密文件持久化路径 |

#### 快速启动示例：
```bash
# 默认端口 8088 启动
./cmd/bin/credkeeper

# 指定端口与存储目录
./cmd/bin/credkeeper -port 9090 -data /var/lib/credkeeper/secrets.enc
```

---

## 五、Web 控制台使用步骤

1. 打开浏览器访问：`http://<服务所在IP>:8088`
2. **设置主通信密钥 (Master Token)**：
   * 在步骤 1 输入框中输入双方约定的密钥，或点击 **【随机生成】** 自动获取一个 32 位高熵口令。
   * *提示：点击小眼睛图标可查看明文，请妥善保存该 Token。*
3. **录入 DNS 提供商凭证**：
   * 切换标签页（阿里云 / 腾讯云 / 华为云 / Cloudflare）；
   * 填入对应的 Key 与 Secret（不需要填写的服务商直接留空即可）。
4. **点击【加密并保存到本地】**：
   * 控制台提示保存成功，此时本地对应路径将生成强加密的 `credentials.enc` 文件。
   * 保存是**合并**的：本次没有填写的服务商保留原有凭据，不会被清空。
   * 加密文件已存在时，必须使用**原 Token** 才能保存，防止他人覆盖。需要更换 Token 时，先备份并删除 `credentials.enc`，再用新 Token 重新录入。
5. **复制配置**：
   * 页面底部的“步骤 3”会根据你填写的信息**实时联动生成可直接使用的 YAML 配置**，点击 **【复制配置】** 即可。

---

## 六、LiteGate 网关端完整配置实战

### 1. LiteGate `config.yaml` 配置样例（直接配置，无需环境变量）

在 LiteGate 的配置文件中，在 `auto_cert` 根节点下配置 `secret_token`（或在各个 DNS Provider 下配置 `secret_token`），即可完成与 CredKeeper 的鉴权和解密。`secret_token` 支持 `enc://`、`file://`、`env://`、`${VAR}` 引用：

```yaml
auto_cert:
  enabled: true
  email: "admin@mycompany.com"
  renew_days: 30
  check_interval: 24
  # 与 CredKeeper 约定的 Token。不要写明文，推荐写成密文：
  #   litegate secret keygen          # 网关主机上执行一次
  #   litegate secret encrypt         # 输入 Token，得到 enc://...
  # 也可以写成 "file:///etc/litegate/credkeeper.token"（文件权限 0600）
  secret_token: "enc://AWoirIpF..."

  dns_providers:
    # 1. 阿里云泛域名证书配置
    - name: aliyun
      type: aliyun
      domains:
        - "*.aliyun.mycompany.com"
      config:
        access_key_id: "secret+http://127.0.0.1:8088/v1/secret/aliyun#access_key_id"
        access_key_secret: "secret+http://127.0.0.1:8088/v1/secret/aliyun#access_key_secret"
        region_id: "cn-hangzhou"

    # 2. 腾讯云泛域名证书配置
    - name: tencent
      type: tencent
      domains:
        - "*.tencent.mycompany.com"
      config:
        secret_id: "secret+http://127.0.0.1:8088/v1/secret/tencent#secret_id"
        secret_key: "secret+http://127.0.0.1:8088/v1/secret/tencent#secret_key"

    # 3. 华为云泛域名证书配置
    - name: huawei
      type: huawei
      domains:
        - "*.huawei.mycompany.com"
      config:
        access_key_id: "secret+http://127.0.0.1:8088/v1/secret/huawei#access_key_id"
        secret_access_key: "secret+http://127.0.0.1:8088/v1/secret/huawei#secret_access_key"

    # 4. Cloudflare 泛域名证书配置
    - name: cloudflare
      type: cloudflare
      domains:
        - "*.cloudflare.mycompany.com"
      config:
        api_token: "secret+http://127.0.0.1:8088/v1/secret/cloudflare#api_token"
        timeout: "120s"
```

---

## 七、常见问题排查 (FAQ)

### Q1: 提示 `Unauthorized: token mismatch or corrupted data`？
- **原因**：LiteGate 发起请求时携带的 Token 与 CredKeeper 保存加密文件时使用的 Token 不一致，导致 AES-GCM 消息鉴权标签（Auth Tag）校验失败。
- **解决**：检查 LiteGate `config.yaml` 中的 `secret_token` 是否与 CredKeeper Web 页面上填写的 Token 完全一致。

### Q2: 保存时提示 Token 与已保存的凭据不匹配？
- **原因**：加密文件已存在，本次填写的 Token 与原 Token 不一致。为防止他人覆盖凭据，CredKeeper 拒绝了这次保存。
- **解决**：使用原 Token 保存。如确需更换 Token，先备份并删除 `credentials.enc`，重新录入全部凭据，并同步更新各网关的 `secret_token`。

### Q3: 能否通过 Systemd 将 CredKeeper 注册为后台自启动服务？
创建 `/etc/systemd/system/credkeeper.service`：
```ini
[Unit]
Description=LiteGate CredKeeper Security Sidecar
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/credkeeper
ExecStart=/opt/credkeeper/credkeeper -host 127.0.0.1 -port 8088 -data /opt/credkeeper/data/credentials.enc
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
执行 `systemctl enable --now credkeeper` 即可常驻后台运行。

---

## 八、总结

通过引入 CredKeeper：
* **客户方**：拥有直观友好的 Web 录入页面，敏感 Key 仅在本地被 AES-256 加密落盘，云权限完全受控；
* **实施/运维方**：配置文件里只有引用和密文，不再出现明文密钥；
* **边界**：CredKeeper 解决的是“配置文件与磁盘上没有明文凭据”和“集中管理”；网络传输安全请依赖 HTTPS 或内网环境，主机被完全控制的情况任何纯软件方案都无法防御。
