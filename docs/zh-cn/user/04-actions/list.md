# List Action (目录浏览)

`list` Action 以美观的网页形式展示指定目录的文件列表，适用于文件下载站、资源共享等场景。

---

## 1. 基础配置

```yaml
domain: files.example.com
routes:
  - name: downloads
    match:
      path_prefix: /
    action:
      type: serve
      root: "/data/downloads"
      title: "公共资源下载站"      # 页面标题
      show_hidden: false           # 是否显示隐藏文件 (以 . 开头)
```

---

## 2. 参数说明

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `title` | string | 域名 | 文件列表页面的标题。 |
| `show_hidden` | bool | `false` | 是否展示以 `.` 开头的隐藏文件/目录。 |
| `root` | string | 必填 | 文件存放的根目录。 |

---

## 3. 安全提示

> [!IMPORTANT]
> 目录浏览会暴露服务器上的文件结构。生产环境中建议配合 `auth` 认证中间件使用。
