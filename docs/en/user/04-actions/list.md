# List Action (Directory Browsing)

The `list` action presents a structured, visually-pleasing web interface displaying file trees within a designated server directory. It is highly suitable for public download portals, resource repositories, and internal share grids.

---

## 1. Basic Configuration

```yaml
domain: files.example.com
routes:
  - name: downloads
    match:
      path_prefix: /
    action:
      type: serve
      root: "/data/downloads"
      title: "Public Downloads Portal"  # Visual title displayed on the web page
      show_hidden: false                 # Controls whether to display hidden dotfiles (files starting with .)
```

---

## 2. Parameter Reference

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `title` | string | Matches domain | Title text injected at the top of the directory listing interface. |
| `show_hidden` | bool | `false` | Controls whether to display hidden files or folders starting with a dot (`.`). |
| `root` | string | **Required** | Physical host filesystem directory containing target files. |

---

## 3. Operational Security Guidelines

> [!IMPORTANT]
> Directory browsing exposes the physical file layout of your server host. In production environments, we strongly recommend wrapping this action inside an `auth` authentication middleware pipeline.
