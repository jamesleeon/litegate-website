# List Action (Directory Browsing)

The `list` action presents a structured, visually-pleasing web interface displaying file trees within a designated server directory. It is highly suitable for public download portals, resource repositories, and internal share grids.

---

## 1. Basic Configuration

```yaml
site: files.example.com
routes:
  - name: downloads
    match:
      path_prefix: /
    list:
      root: "/data/downloads"
      title: "Public Downloads Portal" # Visual title displayed on the web page
      show_hidden: false # Controls whether to display hidden dotfiles (files starting with .)
```

---

## 2. Parameter Reference

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `title` | string | `File List` | Title text injected at the top of the directory listing interface. |
| `show_hidden` | bool | `false` | Controls whether to display hidden files or folders starting with a dot (`.`). |
| `root` | string | **Required** | Physical host filesystem directory containing target files. |

---

## 3. Operational Security Guidelines

> [!IMPORTANT]
> Directory browsing exposes the physical file layout of your server host. In production environments, we strongly recommend wrapping this action inside an `auth` authentication middleware pipeline.

## List and Grid Views

Use the List / Grid buttons to switch layouts. Grid view previews PNG, JPEG, GIF, WebP, AVIF, BMP, and SVG images; other files and directories use icons. Search and sorting work in both views. The browser remembers the selected view. Previews load original images lazily; the server does not generate thumbnails.

Click an image in either view to open an in-page viewer. Previous/next buttons, arrow keys, mobile swipes, and Esc are supported. The viewer follows the current filtered and sorted image list. Closing it restores focus without navigating away. Use a root-level `list` with `auth.type: sso` to protect listing, images, and downloads together; see `examples/list-demo/site-sso.example.yaml`.
