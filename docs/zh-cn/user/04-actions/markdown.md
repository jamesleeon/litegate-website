# Markdown Action (文档渲染服务)

LiteGate 内置了功能强大的 Markdown 渲染引擎，允许您将服务器上的 `.md` 文档目录直接发布为美观的 HTML 预览页面。

---

## 1. 基础配置 (Markdown Rendering)

```yaml
domain: docs.example.com
routes:
  - name: internal-docs
    match:
      path_prefix: /
    action:
      type: markdown
      root: "./docs-repo"    # 文档存放路径
```

---

## 2. 核心特性

### 静态转动态
当用户访问 `https://docs.example.com/README` 时，网关会读取 `README.md`，并在内存中渲染为带有导航栏和样式表的 HTML 页面返还。

### Mermaid 图表支持
完全支持 Mermaid 语法。您可以在 Markdown 中直接嵌入流程图、时序图和甘特图。
- 示例：
  ```mermaid
  graph LR
    A[Markdown] --> B[HTML+CSS]
  ```

### 暗黑模式
支持跟随系统设置自动切换主题，或显式指定主题。

### 锚点导航
自动为每一个 `h1`, `h2` 级标题生成锚点，支持侧边栏快速跳转。

---

## 3. 常见应用场景

- **项目 Wiki**: 挂载现有的 Git 仓库文档目录。
- **内部操作手册**: 实时编辑即生效，无需部署。
- **技术博客**: 极简的静态博客发布方式。

---

## 4. 与 WebDAV 集成 (推荐)
配合 WebDAV Action，您可以实现一个“云端文档库”：通过 WebDAV 编辑文档 -> 通过 Markdown Action 实时预览。

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

## 延伸阅读
- [配置 WebDAV 集成](./webdav.md)
- [使用 Serve 托管纯静态 HTML](./serve.md)
