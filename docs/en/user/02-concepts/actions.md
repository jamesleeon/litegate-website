# Actions Detail: Request Processing Model

In LiteGate, when a route matches successfully, you must specify an **Action (动作)** and its associated handler. An Action defines how the gateway responds to requests, forwards traffic, or renders content.

---

## Core Action Types

### 1. Proxy (Reverse Proxy)
The most common action. It forwards HTTP/HTTPS/WebSocket requests to backends.
- **Features**: Load balancing (Round Robin, Least Conn), health checks, backend connection pool reuse.
- **Use Cases**: Microservices, traditional web applications, gRPC-Web.

### 2. Serve (Static File Server)
A built-in, high-performance static file server.
- **Features**: Smart compression (Brotli/Gzip), cache control headers, SPA routing fallbacks.
- **Use Cases**: Vue/React/Next.js frontend entries, public assets hosting.

### 3. Respond (Immediate Response)
The gateway directly returns fixed content, bypassing any backend servers.
- **Features**: Custom status codes, response headers, and bodies.
- **Use Cases**: Health check endpoints, system maintenance pages, mock testing.

### 4. Redirect (HTTP Redirect)
Performs HTTP 301/302/307 redirections.
- **Features**: Auto protocol completion (HTTP -> HTTPS), path restructuring.
- **Use Cases**: Domain migration, legacy path redirection.

### 5. WebDAV (File Management)
A built-in WebDAV file driver.
- **Features**: Cross-platform mounting, file read/write operations, authorization validation.
- **Use Cases**: Private cloud storage entry, automated backup nodes.

### 6. Markdown (Document Renderer)
Renders `.md` files in a directory as beautiful HTML preview pages in real-time.
- **Features**: Integrated Mermaid diagrams, dark-mode support, anchor navigation.
- **Use Cases**: Hosting and displaying project documentations online.

---

## How to Choose the Right Action?

| Requirement | Recommended Action |
| :--- | :--- |
| **Forward traffic to application servers** | `proxy` |
| **Render frontend static web pages** | `serve` |
| **Return raw JSON or plain text** | `respond` |
| **Enforce path/domain redirection** | `redirect` |
| **Mount a folder as a network drive** | `webdav` |
| **Show markdown README documents** | `markdown` |

---

## Next Steps
To learn more about the configuration parameters for each Action, see: [Site Configuration Reference](../03-configuration/site-config.md).
