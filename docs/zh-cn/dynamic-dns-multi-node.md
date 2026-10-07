# 内网 DNS 自动发布 - 多节点网关支持

## 🎯 设计目标

**内网客户端访问网关域名时，直接解析到 LiteGate 的内网 IP；多个 LiteGate 节点同时在线时自动组成多条 A 记录，节点下线自动剔除。**

外网解析由 DDNS 负责（公网 IP → 域名服务商），内网解析由本机制负责：

```text
LiteGate 站点 a.b.com
  ├─ 公网 IP → DDNS → 域名服务商          外网用户
  └─ 内网 IP → LiteMesh KV → LiteDNS      内网用户
```

---

## 🔥 核心设计：按域名写入 LiteMesh KV + TTL 心跳

每个 LiteGate 节点为每个域名写一个独立的 key：

```text
litedns/v1/records/{domain}/{node_id}
```

```text
LiteGate 节点 1 (192.168.1.100)
    ↓ 每 30 秒刷新
litedns/v1/records/api.example.com/gw-1 → 192.168.1.100

LiteGate 节点 2 (192.168.1.101)
    ↓ 每 30 秒刷新
litedns/v1/records/api.example.com/gw-2 → 192.168.1.101

LiteDNS：
- 监听 litedns/v1/records/ 前缀
- 按域名聚合，返回两条 A 记录
- key 过期后自动移除对应 IP
```

Value 格式（与 LiteDNS `DNSRecordSet` 一致）：

```json
{
  "name": "api.example.com",
  "type": "A",
  "values": ["192.168.1.100"],
  "ttl": 30,
  "owner": "gw-1"
}
```

---

## 📋 工作流程

### 1. 节点启动与域名注册
LiteGate 启动或加载新站点时，域名加入 `DNSUpdater` 的维护列表，并立即写入 KV。站点移除时立即删除对应 key。

### 2. 心跳续期
`internal/certmanager/dns_update.go` 中的后台 Goroutine：
- 间隔：`heartbeat_interval`，默认 30 秒；
- 行为：重新写入所有维护中的 key，并刷新 KV TTL；
- KV TTL 为心跳间隔的 3 倍，允许连续丢失两次心跳。

### 3. 故障剔除
节点宕机后心跳停止，LiteMesh 在 KV TTL 到期后删除 key，LiteDNS 在下一次全量校准（默认 15 秒）时移除该 IP。

### 4. 优雅注销
网关正常关闭时主动删除自己发布的所有 key，LiteDNS 收到 KV 事件后立即移除。

---

## 🏗️ 多节点部署示例

每个节点都需要启用 litemesh，并使用相同的 `key_prefix`：

```yaml
auto_cert:
  dns_update:
    enabled: true
    auto_service_host_sync: true
    ip: ""                             # 留空则自动检测出口网卡 IP
    key_prefix: "litedns/v1/records/"  # 与 LiteDNS litemesh.dns_record_prefix 一致
    node_id: ""                        # 留空使用主机名
    record_ttl: 30
    heartbeat_interval: 30s
```

`node_id` 默认取主机名，重启后覆盖自己原来的 key，不会留下重复记录。同一台主机上运行多个 LiteGate 时，需要显式配置不同的 `node_id`。

---

## 💪 核心优势

### 1. 故障自愈
节点宕机 → 心跳停止 → KV 过期 → LiteDNS 剔除，无需人工干预。

### 2. 动态扩容
新节点启动即自动加入该域名的 A 记录。

### 3. 无额外依赖
不再需要单独的 DNS 管理 API 和 API Key；LiteGate 与 LiteDNS 只通过 LiteMesh KV 交互，LiteDNS 可部署多个实例。
