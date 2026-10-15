# Proxy Cache（代理响应缓存）

支持 `local` 和 `redis` 后端，默认本地缓存。多节点必须显式选择 Redis，并使用相同的 Redis、命名空间和路由配置。仅启用 `cache.redis` 不会自动切换代理缓存。

## 路由配置

```yaml
site: example.com
/api/list:
  name: cached-list
  proxy: 127.0.0.1:8080
  cache:
    ttl: 30s
```

`cache: true` 默认缓存 10 秒；映射支持 `enabled`、`ttl`、`key`。TTL 接受正整数秒或整秒时长。底层 action 字段对应 `proxy_cache`、`proxy_cache_ttl`、`proxy_cache_key`。

`X-LiteGate-Cache` 表示 `MISS`、`HIT`、`STALE`，绕过缓存时可能没有该响应头。命中时更新 `Age`。

默认 Key 包含 Host、路由和完整 URI（含查询串），GET 与 HEAD 共用，不包含方法。存储层额外隔离命名空间、Host、路由和路由配置版本，自定义 Key 不会取消这些边界。

## 全局配置

以下内容放在网关 `config.yaml`，不放在站点 YAML：

```yaml
cache:
  redis:
    enabled: true
    address: 127.0.0.1:6379
  proxy_cache:
    backend: redis                  # local | redis；默认 local
    namespace: production          # 默认 default；不同环境必须区分
    max_object_bytes: 262144        # 默认 256KB；超限正常透传但不缓存
    redis_timeout: 200ms            # 每次 Redis 操作的超时
    stale_while_revalidate: 0s      # Redis 默认关闭；显式开启允许旧内容
  proxy_cache_max_entries: 10000    # 本地 LRU 条目上限
```

Redis 连接优先复用 `cache.redis`，其次使用全局 `redis`。都未启用时不能选择 Redis 后端。支持现有 Redis Cluster 配置，缓存 Lua 脚本均只操作一个 Key。Redis 模式直接读取共享存储，没有本地一级缓存。

本地正文不超过 64KB 时走内存，较大正文使用进程独占磁盘目录；默认内存预算 128MB、磁盘预算 10GB。淘汰及每 30 秒的维护任务清理过期内容和辅助索引，正常退出回收缓存正文。重启不恢复本地缓存；异常终止遗留的独占目录由系统临时目录维护策略或运维清理，其他进程不会在启动时删除它。

Redis 原子保存正文、响应元数据和变体。每个基础 Key 最多保存 100 个变体，写入时回收过期变体。`proxy_cache_max_entries` 不限制 Redis 总容量，应为 Redis 单独配置容量和淘汰策略。空闲失效版本元数据一天后过期，重新创建使用新令牌，避免旧缓存重新可见。

## 身份与 HTTP 行为

Key 支持 `{host}`、`{uri}`、`{path}`、`{method}`、`{header.X}`。占位符不能为空、带空格或使用未知名称，加载时拒绝无效模板。URI 含查询串，path 不含。

带 Authorization、Cookie、API Key 或启用认证的请求，必须配置非空身份 Key 才允许缓存，例如 `key: "{host}:{uri}:{header.Authorization}"`。也可使用认证层注入的 X-Auth-Subject 等头，但认证层必须覆盖客户端提供的同名头。未明确隔离身份的个性化接口应关闭缓存。

只有 GET 填充；HEAD 可以命中已有 GET 缓存，未命中回源。仅缓存 200、203、300、301。命中支持条件请求和范围请求，上游 206 不缓存。

Set-Cookie、private、no-store、no-cache、不支持的 Vary 响应不缓存。Vary 仅支持 Origin 和 Accept-Encoding。WebSocket、gRPC、SSE、流式刷新、不完整响应绕过缓存。上游压缩正文可作为独立变体缓存，不保证正文始终未压缩。

TTL 取路由配置与上游有效时长的较短值，并扣除已有 Age。请求 no-cache/max-age=0 强制刷新，no-store 绕过。上游 stale-while-revalidate 允许先返回旧内容、随后后台刷新；全局同名设置仅限制窗口，不会自行增加窗口。Redis 默认上限为零，本地未配置时保留上游窗口。

## 清理接口

`POST /api/proxy-cache/purge` 沿用 dashboard 的 API Key 或会话鉴权；会话写操作需要 Origin/Referer 通过 CSRF 检查。配置 dashboard 路径前缀时，也需加上该前缀。

```json
{"scope":"route","site":"example.com","route":"cached-list"}
```

| scope | 必需字段 | 范围 |
| --- | --- | --- |
| all | 无 | 当前命名空间 |
| site | site | 请求 Host 域名，忽略端口和大小写 |
| route | site、route | 该站点的命名路由 |
| key | base_key | 内部不透明基础 Key 及全部变体 |

Redis 范围清理切换版本，使旧缓存不可见；旧正文由 TTL 回收，不扫描全库。旧请求不能让失效内容重新可见。Key 清理还阻止已开始的填充提交。**本地站点或路由清理会保守清空本进程全部缓存**，立即回收存储；不影响其他进程。

## 写操作成功后失效

```yaml
site: example.com
routes:
  - name: cached-list
    match: {path: /api/items, method: [GET]}
    proxy: 127.0.0.1:8080
    cache: {ttl: 30s}
  - name: update-item
    match: {path: /api/items, method: [POST]}
    proxy: 127.0.0.1:8080
    on_success:
      invalidate_proxy_cache: [cached-list]
```

`invalidate_proxy_cache` 接受当前请求站点的路由名称列表，`["*"]` 清理该站点。仅上游 2xx 触发。原有 `invalidate_cache` 仍只清理模板 fetch_json.cache_tags，两者可同时配置。

Redis 失效失败时保留上游写入结果，响应增加 `X-LiteGate-Cache-Invalidation: failed`，记录错误并最多重试三次。重试不持久化，进程退出后不会继续。严格读后写一致性的调用方必须处理失败标记；严格实时接口应关闭缓存。异步复制故障切换下不承诺强一致性。

## 故障与观测

Redis 不可用时直接回源，不自动切换为独立本地缓存，需结合限流保护上游。分布式填充锁采用 30 秒租约、每 10 秒续租和唯一所有者令牌；等待共享填充约 200ms 后可回源，不保证所有故障都仅回源一次。

指标：`litegate_proxy_cache_requests_total`、`litegate_proxy_cache_operations_total`、`litegate_proxy_cache_redis_duration_seconds`。管理接口在 Redis 失效失败时返回 503；已经成功的上游写入不会因此伪装成上游失败。
