# Authentication (网关身份认证与治理概述)

LiteGate 提供了两套不同的身份认证与流量治理组件，它们分别解决不同的业务问题：

- **`action.auth`** (本地静态认证中间件)
  - 面向静态 YAML 路由。
  - 适合 `basic`、`sso`、`jwt` 等本地单站点简单认证场景。
- **`action.remote_auth`** (OIDC 认证中间件)
  - 面向标准 OIDC (OpenID Connect) / OAuth2 单点登录回跳与会话管理场景。
- **`action.ids`** (数据代理前置 IDS 治理)
  - 面向动态服务发现、多租户 SaaS 架构和 IDS（身份驱动选路治理）平台的高速深度协同。
  - 由统一 Provider 自定义验证、缓存、直接响应、Header 投影和可选的物理隔离选路。
  - 执行在 Proxy 数据代理阶段的前置接缝（pre-proxy seam），而非传统 HTTP 路由中间件。

---

## 1. 核心分类说明

### 1.1 静态认证：`auth`
这是传统的本地站点/YAML 路由静态认证，走 `Action.Auth`。支持 `basic` / `sso` / `jwt`，适合不需要依赖外部统一认证平台的简单场景。

### 1.2 OIDC 认证：`remote_auth`
托管 OAuth2 标准协议的回跳与会话维持，走 `Action.RemoteAuth`。由 `OIDCHandler` 中间件执行登录重定向与会话生命周期维护。详见 [OIDC 指南](./oidc.md)。

### 1.3 身份驱动选路与治理：`ids`
这是 LiteGate 核心数据流的前置接缝，走 `Action.IDS`。不同路径选择不同 Provider；内核只理解 Forward、Respond、错误和可选 Selector/Meta，不理解具体业务动作。详见 [IDS 治理指南](./ids-governance.md)。

---

## 2. 延伸阅读

- [Basic Auth 基本认证中间件](./basic-auth.md)
- [IDS 治理指南](./ids-governance.md)
- [OIDC 指南](./oidc.md)
- [IDS Provider 插件开发与配置](../../ids-provider-plugin-guide.md)
