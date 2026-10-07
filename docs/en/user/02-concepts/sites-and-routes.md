# Understanding Sites and Routes

LiteGate's core configuration model follows the principle of "domain-level isolation and path-based routing." Understanding the relationship between Sites and Routes is the key to mastering this cloud-native gateway.

---

## 1. Core Model: Site

A **Site** corresponds to a unique domain name (Domain). It represents the smallest independent unit of load balancing and traffic governance in LiteGate.

- **Isolation**: Each Site possesses its own independent SSL certificates, middleware strategies, and routing tables.
- **File Location**: Usually placed under the `sites/*.yaml` folder, where the file name corresponds to the domain name.

### Site-Level Global Settings
- `domain`: The domain name of the site (e.g., `example.com`).
- `force_https`: Whether to automatically enforce redirection from HTTP to HTTPS in browsers.
- `middleware`: Security policies (e.g., authentication, rate limiting) shared by all routes under this domain.

---

## 2. Traffic Distribution: Route

A **Route** represents the specific forwarding rule inside a Site. It determines which backend handler will process an incoming request when it matches the domain name.

### Components
1.  **Match**: Criteria (such as path prefixes) that determine whether the incoming request hits this route.
2.  **Action**: The actual operation performed once a request successfully matches (such as reverse proxy `proxy` or static file serving `serve`).

---

## 3. Route Matching Options

LiteGate supports rich, multi-dimensional request matching criteria. You can declare the following matching fields in a route's `match` block simultaneously:

### 1. `path_prefix` (Prefix Matching)
*   **YAML Field**: `path_prefix`
*   **Description**: Matches the prefix of the request path. It hits if the incoming request path begins with the specified string.
*   **Example**:
    ```yaml
    match:
      path_prefix: /api/v1
    ```

### 2. `path` (Exact Path Matching)
*   **YAML Field**: `path`
*   **Description**: Exact point-to-point matching. It only hits when the absolute path of the request matches precisely (useful for index redirects or specific single-page routings).
*   **Example**:
    ```yaml
    match:
      path: /
    ```

### 3. `method` (HTTP Method Matching)
*   **YAML Field**: `method` (supports a single string or an array of strings)
*   **Description**: Restricts access to specific HTTP request methods (e.g., `GET`, `POST`, `DELETE`, etc.).
*   **Example**:
    ```yaml
    match:
      path_prefix: /users
      method: ["GET", "POST"] # Only intercepts GET and POST requests under this path
    ```

### 4. `header` (Request Header Matching)
*   **YAML Field**: `header`
*   **Description**: Matches specified HTTP request header keys and values. Supports single-value exact matches or arrays of values (where any match hits).
*   **Example**:
    ```yaml
    match:
      path_prefix: /management
      header:
        X-Gate-Client: "internal"      # Exact match for the header value
        X-Role: ["admin", "superadmin"] # Matches if the client has either role
    ```

### 5. `rule` (Advanced DSL Rule Matching)
*   **YAML Field**: `rule`
*   **Description**: Supports a powerful condition expression DSL similar to Traefik. Use this when you need complex logic combinations (e.g., combining Host matching with multiple boolean operators like AND/OR/NOT).
*   **Example**:
    ```yaml
    match:
      rule: "Host(`api.demo.com`) && Path(`/v1/health`)"
    ```

---

## 4. Matching Priority Logic

LiteGate follows the **"longest match wins"** principle when resolving routing priorities:

Suppose you have defined two routes:
1.  Route A: `path_prefix: /`
2.  Route B: `path_prefix: /api/v1`

**Resolution Process**:
- When a client requests `/api/v1/user`, the gateway matches both A and B, but B's path is more specific (longer). Therefore, traffic goes to **Route B**.
- When a client requests `/index.html`, it only matches A. Therefore, traffic goes to **Route A**.

---

## 5. Sample Configuration File

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

## Next Steps
To understand what happens after a route successfully matches, see: [Actions Detail](./actions.md).
