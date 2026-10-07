# Access Log (访问日志)

访问日志记录了通过 LiteGate 的每一个 HTTP(S) 请求。它是分析流量分布、定位接口报错和审计安全事件的核心数据源。

---

## 1. 启用配置

在 `config.yaml` 中全局定义访问日志的输出行为：

```yaml
log:
  format: json            # json 或 console —— 控制所有日志输出(含访问日志)
  access_log:
    enabled: true
    stdout: true          # 访问日志输出到控制台
    level: info           # none / error / warn / info / debug
    file_enabled: false   # 设为 true 后写入文件
    file: ""              # 可选；file_enabled=true 时默认 ./logs/access.log
    max_size: 100         # 可选；单日志文件最大大小 (MB)
    max_age: 7            # 可选；旧日志文件最大保留天数
    max_backups: 30       # 可选；最大保留的旧日志文件个数
    compress: true        # 可选；是否压缩旧日志文件 (gzip)
    routing_detail: false # 设为 true 输出详细的路由决策日志
```

---

## 2. 日志字段说明 (JSON 格式)

LiteGate 的访问日志包含丰富的路由元数据，方便下游大数据平台分析。

| 字段 | 说明 | 示例 |
| :--- | :--- | :--- |
| `time` | 请求完成的时间 | `2026-03-22T10:00:00Z` |
| `client_ip` | 客户端真实 IP | `1.2.3.4` |
| `method` | HTTP 方法 | `POST` |
| `path` | 请求路径 | `/api/v1/user` |
| `status` | HTTP 响应状态码 | `200` |
| `latency` | 网关处理总延迟 (ms) | `15.5` |
| `upstream` | 后端真实实例 IP | `10.0.0.5:8080` |
| `site` | 所属站点域名 | `api.example.com` |
| `route` | 匹配到的路由名称 | `user-service-route`|

---

## 3. 采集模式与性能

访问日志支持三种输出目标（`stdout` / `file` / `webhook`），可同时开启。但它们对请求热路径的影响**截然不同**，请按场景选择：

| 输出目标 | 写入方式 | 对请求性能的影响 | 适用场景 |
| :--- | :--- | :--- | :--- |
| `webhook` | **异步**（内存拷贝 + 非阻塞入队，后台批量 POST） | 几乎为零，**不阻塞请求** | **生产默认（集中式）** |
| `file` | 同步落盘（含轮转切割时的磁盘 I/O） | 在请求 goroutine 内同步写，**会占用热路径** | 仅低请求量 / 单机调试 |
| `stdout` | 同步写控制台 | 在请求 goroutine 内同步写，**会占用热路径** | 开发调试 |

> ⚠️ **关键**：只有 `webhook` 是异步的；`stdout` 和 `file` 都是在请求 goroutine 内**同步写**。高吞吐生产环境务必关闭 `stdout` 与 `file`，仅保留 `webhook`，否则同步 I/O 会成为转发性能瓶颈。

**两种推荐部署模式：**

1.  **集中式模式（生产默认，推荐）**：通过 `webhook` 将日志异步推送到统一的 MQ 入口服务，再由独立消费者落库（如 OpenObserve / Elasticsearch）。日志投递为"尽力而为"——队列满或下游不可用时会**主动丢弃**而非阻塞，确保 LiteGate 转发性能不受任何影响。

    ```yaml
    log:
      format: json
      access_log:
        enabled: true
        stdout: false       # 生产关闭，避免同步写控制台拖慢热路径
        file_enabled: false # 生产关闭，避免同步磁盘 I/O 拖慢热路径
        webhook:
          enabled: true
          url: http://<mq-ingress>/access-log  # 异步入队即返回的 MQ 入口
          batch_size: 100   # 每批最多条数，默认 100
          interval: 1s      # 批量发送间隔，默认 1s
    ```

2.  **文件模式（仅低请求量场景）**：无外部依赖，直接落盘并自带轮转清理。由于是**同步写**，仅建议在低流量或无集中式日志平台时使用。

    **默认安全兜底**：开启 `file_enabled: true` 但未配置轮转参数时，网关默认在单文件达到 100MB 时切割，且仅保留最近 7 天历史日志，防止磁盘无限堆积。可按磁盘空间自定义：

    ```yaml
    log:
      access_log:
        file_enabled: true
        max_size: 100      # 可选；单日志文件最大大小 (单位: MB)
        max_age: 7         # 可选；旧日志文件最大保留天数 (若与 max_backups 均未配置，默认保留 7 天)
        max_backups: 30    # 可选；最多保留的历史归档日志文件个数
        compress: true     # 可选；是否将历史日志进行 gzip 压缩
    ```

---

## 4. 其他最佳实践

1.  **分流存储**: 使用文件模式时，建议将日志存储在单独的磁盘分区，以防因磁盘爆满影响系统运行。
2.  **优雅关闭**: 进程关闭时，网关会在停止接收请求后自动 Flush webhook 缓冲区，尽量减少日志丢失（集中式模式下日志投递本身为尽力而为，极端情况下仍可能丢弃）。
3.  **ELK 集成**: 文件模式下推荐配合 Filebeat 直接采集 JSON 格式日志到 Elasticsearch。


## 自定义访问日志模板

```yaml
log:
  format: json
  access_log:
    enabled: true
    stdout: true
    file_enabled: true
    file: ./logs/access.log
    template: '{client_ip} - [{timestamp}] "{method} {uri}" {status} {size_bytes} "{referer}" "{user_agent}" {cost_ms}'
```

`template` 控制访问日志的终端和文件输出；留空沿用现有格式。运行日志继续由 `log.format` 控制，Webhook 和看板保留结构化数据。文件轮转、异步写入和日志级别过滤照常生效。

支持字段：`timestamp`、`client_ip`、`method`、`path`、`uri`（含查询参数）、`host`、`status`、`size_bytes`、`cost_ms`、`upstream`、`route`、`site`、`trace_id`、`referer`、`user_agent`。时间为现有结构化日志时间戳，耗时单位为毫秒，保留小数精度；空的 Referer 和 User-Agent 输出 `-`。缺失字段输出 `-`。字段值中的换行、控制字符、引号和反斜杠会转义，防止请求伪造额外日志行。模板必须为单行，未知字段或不完整占位符会在配置验证时报告错误。这是 LiteGate 的 `{字段}` 模板，不直接解析 Nginx `$变量` 格式。

修改 `log.access_log.template` 后需要重启 LiteGate；当前全局日志配置只有 `log.level` 支持热更新。通过 MCP 保存配置会进行校验并请求重载，但保存成功不表示这些启动时配置已生效。`litegate -init` 生成的示例配置也包含空模板和自定义模板示例。
