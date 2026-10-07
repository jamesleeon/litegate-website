# Markdown Action (Document Rendering Service)

LiteGate features a powerful server-side Markdown compilation engine, enabling you to expose raw `.md` document directories on your server directly as styled, responsive HTML portal layouts.

---

## 1. Basic Configuration

```yaml
domain: docs.example.com
routes:
  - name: internal-docs
    match:
      path_prefix: /
    action:
      type: markdown
      root: "./docs-repo"    # Filesystem path to your markdown files
```

---

## 2. Core Functional Features

### Dynamic Compilation
When a client requests `https://docs.example.com/README`, the gateway reads the raw file `README.md` from the filesystem, compiles it into HTML in-memory, wraps it with navigation stylesheets, and returns it directly to the browser.

### Mermaid Visualization Support
LiteGate natively processes Mermaid diagram scopes. You can embed flowcharts, sequence diagrams, and Gantt charts directly in your markdown documents.
- **Example**:
  ```mermaid
  graph LR
    A[Markdown Source] --> B[HTML+CSS Portal]
  ```

### Automatic Theme Adaptation (Dark/Light Modes)
The rendered page includes a built-in light/dark toggle and follows the visitor's system color-scheme preference automatically. This is part of the rendered output and needs no configuration.

### Nested Anchor Sidebars
The compiler dynamically evaluates `h1` and `h2` headings to generate hierarchical anchor sidebars, enabling users to jump instantly to document subsections.

---

## 3. Practical Implementations

- **Project Wikis**: Instantly serve Git repository documentation hubs.
- **Collaborative Operations Manuals**: Real-time content editing; updates take effect immediately without redeployment pipelines.
- **Minimalist Portals & Technical Blogs**: Highly productive, lightweight web posting without complex static compilers.

---

## 4. Collaborative Wiki Workflow (WebDAV Integration)

By combining the WebDAV action with the Markdown action, you can establish a robust "collaborative cloud wiki": author and update pages via WebDAV, and instantly preview compiled versions via the Markdown engine.

```yaml
# sites/wiki.yaml
domain: wiki.local
routes:
  - name: view
    match: { path_prefix: "/view" }
    action: { type: markdown, root: "./data/wiki" }
  - name: edit
    match: { path_prefix: "/edit" }
    action: { type: webdav, root: "./data/wiki", strip_prefix: "/edit" }
```

---

## Further Reading
- [Configuring WebDAV Integration](./webdav.md)
- [Hosting Pure Static Assets via Serve](./serve.md)
