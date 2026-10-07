# 理解 Sites 与 Routes

LiteGate 的核心配置模型遵循“域级隔离，路径分发”的原则。理解 Site 和 Route 的关系是玩转网关的关键。

---

## 1. 核心模型：Site (站点)

一个 **Site** 对应一个唯一的域名（Domain）。它是 LiteGate 负载均衡的最小独立单元。

- **隔离性**：每个 Site 拥有独立的证书、中间件策略和路由表。
- **配置位置**：通常存放在 `sites/*.yaml` 中，文件名即为域名。

### Site 级全局参数
- `domain`: 站点域名 (如 `example.com`)。
- `force_https`: 是否强制启用浏览器 HTTPS 跳转。
- `middleware`: 该域名下所有路由共享的安全策略（如认证、限流）。

---

## 2. 路由分发：Route (路由)

**Route** 是 Site 内部的具体分发规则。它决定了请求到达域名后，具体交给哪个后端处理。

### 组成部分
1.  **Match (匹配)**：通过 `path_prefix` 等条件确定请求是否属于该路由。
2.  **Action (动作)**：匹配成功后执行的具体操作（如反向代理 `proxy` 或静态服务 `serve`）。

---

## 3. 路由匹配条件 (Match Options)

LiteGate 支持极其丰富的多维请求匹配。一个路由的 `match` 块中可以同时声明以下匹配条件：

### 1. `path_prefix` (前缀匹配)
*   **YAML 标签**: `path_prefix`
*   **说明**: 匹配请求路径的前缀。只要请求路径以指定的字符开头即命中。
*   **示例**:
    ```yaml
    match:
      path_prefix: /api/v1
    ```

### 2. `path` (精确路径匹配)
*   **YAML 标签**: `path`
*   **说明**: 精确对点匹配。只有当请求的绝对路径完全一致时才会命中（常用于首页单点重定向或特定单页跳转）。
*   **示例**:
    ```yaml
    match:
      path: /
    ```

### 3. `method` (HTTP 方法匹配)
*   **YAML 标签**: `method` (支持单字符串或字符串数组)
*   **说明**: 限制特定的 HTTP 请求方法（如 `GET`, `POST`, `DELETE` 等）。
*   **示例**:
    ```yaml
    match:
      path_prefix: /users
      method: ["GET", "POST"] # 仅拦截该路径的 GET 和 POST 请求
    ```

### 4. `header` (请求头匹配)
*   **YAML 标签**: `header`
*   **说明**: 匹配指定的 HTTP 请求头键值。支持单值精确匹配，也支持值数组（其中任何一个命中均可）。
*   **示例**:
    ```yaml
    match:
      path_prefix: /management
      header:
        X-Gate-Client: "internal"      # 精确匹配请求头键值
        X-Role: ["admin", "superadmin"] # 匹配其中任意一个角色头即可
    ```

### 5. `rule` (高级 DSL 规则匹配)
*   **YAML 标签**: `rule`
*   **说明**: 支持强大的类似于 Traefik 的条件表达式 DSL。当您需要处理极度复杂的匹配关系（例如 Host 匹配与多字段的与或非逻辑组合）时采用。
*   **示例**:
    ```yaml
    match:
      rule: "Host(`api.demo.com`) && Path(`/v1/health`)"
    ```

---

## 4. 优先级匹配逻辑

LiteGate 在处理请求时遵循 **“最长匹配优先”** 原则：

假设你有两个路由：
1.  路由 A：`path_prefix: /`
2.  路由 B：`path_prefix: /api/v1`

**匹配过程**：
- 当访问 `/api/v1/user` 时，网关会同时匹配到 A 和 B，但由于 B 的路径更具体（更长），请求将优先分发给 **路由 B**。
- 当访问 `/index.html` 时，仅匹配到 A，请求分发给 **路由 A**。

---

## 5. 配置组织结构示例

```yaml
domain: api.demo.com
routes:
  - name: auth-engine
    match:
      path_prefix: /auth
    action:
      type: proxy
      upstream: ["10.0.0.1:9000"]
      
  - name: default-handler
    match:
      path_prefix: /
    action:
      type: respond
      status: 200
      body: "Default API Gateway Response"
```

---

## 下一步
了解匹配后的具体动作，请参考：[Actions 详解](./actions.md)。
