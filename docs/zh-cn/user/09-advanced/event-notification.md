# 事件通知：NATS + LiteGate 通知体系

适用于这些场景：异步任务处理完要通知页面、列表和角标要实时刷新、配置变更要通知到各个服务、一个服务的状态变化要提醒另一个服务、租户被关闭后网关插件要立即丢掉缓存。

一条通知可以有两类消费方：

- **客户端**：浏览器和 Go 服务通过 SSE 订阅（第 5 到 8 节）。业务后端不再需要写 SSE、维护长连接和连接注册表，只需要状态变化后**发一个 HTTP 请求**，并继续提供原有的**查询接口**。
- **网关插件**：插件声明自己关心的 subject，网关把通知直接投给它（第 9 节）。IDS 插件可以放心地缓存租户，租户关闭后秒级失效。

推送、广播、多实例、心跳、断线重连，都交给 LiteGate 和 NATS。

## 1. 自建 SSE 的常见做法和问题

很多系统是这样实现实时通知的：

```text
生产服务 ──POST /internal/events──▶ 业务后端（事件分发器）──进程内广播──▶ 浏览器 SSE 长连接
```

后端维护一张"在线连接表"，收到事件就遍历这张表往每条连接里写。前端用 `EventSource` 连上来，断线后自己重连。这种做法能跑起来，但有几个绕不开的问题：

- **广播只在本进程内有效。** 后端一旦扩成两个实例，连在 A 上的浏览器就收不到 B 上产生的事件。
- **长连接压在业务后端上。** 每个打开的页面都占一条连接，心跳、慢客户端、写超时、代理缓冲、停机时断开，全要后端自己处理。
- **每个系统都要重写一遍。** 连接注册表、事件分发器、前端重连逻辑，换一个项目又写一次，各写各的。
- **前端分不清"漏了消息"和"没有消息"。** 断线期间产生的事件丢了，页面也不知道该刷新。

## 2. 新方案

```text
                          ┌──────────────── NATS ────────────────┐
生产服务 ──HTTP POST──▶ LiteGate（发布路由）           LiteGate（订阅路由，每个节点）──SSE──▶ 浏览器 / Go 服务
                                                                                         │
                                                收到信号后 ──HTTP GET──▶ 业务后端原有接口（按权限返回数据）
                                    └──▶ 声明了该 subject 的网关插件 ──▶ 删除缓存、重新加载
```

| 角色 | 负责什么 |
|---|---|
| 生产服务 | 状态变化后 POST 一个很小的信号，不需要 NATS 客户端 |
| LiteGate 发布路由 | 校验主题白名单，把 HTTP 请求转成 NATS 消息 |
| NATS | 把消息广播给所有网关节点 |
| LiteGate 订阅路由 | 鉴权，为每个在线客户端维持 SSE 连接、心跳、背压和限额 |
| 客户端 | 连上时刷新一次；收到信号后调用业务接口拉取最新数据 |
| 业务后端 | 继续提供原来的查询接口，权限照常在这里检查 |

无论有多少个网关节点、多少个后端实例，每个节点上的订阅者都能收到广播。业务后端里不再有任何长连接。

## 3. 核心约定：只推信号，数据自己拉

这一节是整套方案能"简单又不丢状态"的原因，**生产方和客户端都必须遵守**。

**约定 1：消息只说明"什么变了"，不带业务数据。**

```json
{"type": "work_order.changed", "key": "WO-1001", "version": 7, "occurred_at": "2026-10-08T10:30:00+08:00"}
```

- `type`：什么类型的东西变了，客户端据此决定刷新哪一块。
- `key`：哪一条变了，没有可以不填（表示"整类都要刷新"）。
- `version`：可选，单调递增的版本号，客户端用来跳过旧信号。
- 不要放金额、手机号、地址这类数据。信号会广播给订阅这个主题的所有客户端，**权限只在拉取时检查**。

**约定 2：每次连上（包括重连）先刷新一次当前状态。**

断线期间漏掉的信号，都靠这一次刷新补回来。LiteGate 会先确认 NATS 订阅已经生效，才向客户端写出第一个字节，所以客户端的"连接已打开"回调一触发，之后的变更都不会漏；而之前的变更，一定会体现在这次刷新的结果里。

**约定 3：收到信号后按需重新拉取。**

- 带了 `version` 的，本地已经是这个版本或更新，就直接跳过。
- 短时间内收到多条信号，合并成一次拉取。
- 拉取地址由客户端根据自己的配置拼出来，**不要从消息里取 URL**。否则能往这个主题发消息的人，就能把客户端引到任意地址。

正因为有约定 2 兜底，这里用 Core NATS 就够了，不需要消息持久化，也不需要逐条确认：信号丢了，下一次连接时的刷新会补上；信号重复了，拉一次也无妨。

## 4. 适用场景

| 场景 | 主题示例 | 信号示例 | 客户端收到后 |
|---|---|---|---|
| 工单有新回复 | `notify.workorder` | `{"type":"work_order.changed","key":"WO-1001"}` | 刷新未读数和提醒列表 |
| 新单据进来 | `notify.refund` | `{"type":"refund.created","key":"R-88"}` | 刷新列表第一页 |
| 异步任务完成 | `notify.task` | `{"type":"export.completed","key":"job-42"}` | 查询任务状态，提示下载 |
| 配置变更 | `notify.config` | `{"type":"config.changed","key":"store-001","version":42}` | 拉取新配置并应用 |
| 服务之间的状态提醒 | `notify.config` | 同上 | Go 服务刷新本地缓存 |
| 租户被关闭 | `notify.tenant` | `{"tenant_id":"acme","type":"tenant.disabled"}` | IDS 插件删除该租户的缓存（第 9 节） |
| 凭据被吊销 | `notify.credential` | `{"app_key":"k-1","type":"revoked"}` | 鉴权插件删除该凭据的缓存 |

主题建议按"一类信号一个主题"划分，客户端按页面需要订阅一个或几个主题。

## 5. 网关配置

### 5.1 NATS 连接

在插件配置文件中声明连接，所有网关节点连到同一个 NATS 集群：

```yaml
plugins:
  nats:
    connections:
      default:
        servers: "nats://10.0.0.20:4222"
        connect_timeout: "3s"
        reconnect_wait: "1s"
        max_reconnects: "-1"
```

生产环境请配置 NATS 凭证和 TLS，详见 [NATS 部署指南](../../nats_deployment_guide.md)。

### 5.2 站点文件

```yaml
site: app.example.com

middlewares:
  login:
    type: forward_auth
    config:
      address: 127.0.0.1:8080    # 业务后端
      uri: /api/auth/check       # 登录有效返回 2xx，否则返回 401

routes:
  # 发布：只给内网的生产服务用。POST /internal/notify/<主题>
  - match: { prefix: /internal/notify/ }
    ip_restriction:
      allow_ips: [10.0.0.0/8, 127.0.0.1/32]
    action:
      type: nats
      mode: publish
      connection: default
      subject_from: path.1                     # /internal/notify/workorder → workorder
      subject_prefix: notify                   # 最终主题 notify.workorder
      subject_allowlist: [workorder, refund, task, config, tenant]

  # 订阅：登录后才能连。每类信号一条路由
  - match: { path: /events/workorder }
    use: login
    action:
      type: nats
      mode: subscribe
      connection: default
      subject: notify.workorder
      sse:
        tenant: app              # 限额和监控分组，不是鉴权
        max_connections: 500     # 单节点上限

  # 业务接口照旧
  - match: { prefix: /api/ }
    proxy: 127.0.0.1:8080
```

几点说明：

- **发布路由只对内网开放。** 除了 `ip_restriction`，最好再给网关使用的 NATS 账号只授予 `notify.>` 的发布权限。这是 NATS 服务端强制的第二道防线。
- **`subject_allowlist` 是必需的。** 不在名单里的主题直接返回 403，生产方写错主题会马上发现。
- **订阅路由一定要鉴权。** 上面用 `forward_auth` 把请求里的 `Cookie`、`Authorization` 转给后端的 `/api/auth/check`，后端只需要写一个"检查登录是否有效"的接口；但每建立一条连接都要回调一次后端。业务系统使用 JWT 时，推荐改用下一节的方式，由网关直接验签。
- 前缀匹配必须写 `prefix`；写成 `path` 是精确匹配，`/internal/notify/workorder` 会匹配不上。

### 5.3 订阅鉴权：用 JWT Cookie 保护订阅（推荐）

不加鉴权的订阅，任何人连上来都能收到信号。信号虽然不带业务数据，但仍会暴露单号、业务节奏，大量匿名连接还会耗尽连接额度。业务系统已经在用 JWT 时，只需让同一个 JWT 也出现在 Cookie 里，网关就能自己验证，不再回调后端：

```text
登录成功 ──▶ 后端照常返回 JWT，另外下发 Set-Cookie: lg_token=<同一个 JWT>; HttpOnly
new EventSource('/events/workorder') ──▶ 浏览器自动带上 Cookie ──▶ 网关验签通过才建立订阅
令牌过期 ──▶ 网关断开推送流 ──▶ 浏览器重连时带上续签后的 Cookie，重新验证
```

网关配置：

```yaml
site: app.example.com
/events/workorder:
  auth:
    type: jwt
    secret: env://APP_JWT_SECRET      # 和业务后端签发 JWT 用的是同一个密钥
    token_from: [cookie:lg_token]
    subject_claim: user_id
    tenant_claim: tenant_id
  subscribe: notify.{auth.tenant}.workorder   # 每个租户一个主题，见 5.4 节
```

业务后端要在**所有**签发或更换令牌的地方同步写这个 Cookie，并在退出时清除：

| 时机 | 后端要做的事 |
|---|---|
| 登录成功 | 写 Cookie |
| 令牌续签（例如在响应头里下发新令牌的滑动续签） | **同一个响应里**重新写 Cookie。只更新前端 localStorage 不够：业务接口还能用，订阅重连却会一直 401 |
| 退出登录 | 写一个立即过期的同名 Cookie（`Max-Age=0`）。HttpOnly Cookie 只能由服务端清除，前端脚本删不掉 |

```go
http.SetCookie(w, &http.Cookie{

```go
http.SetCookie(w, &http.Cookie{
	Name:     "lg_token",
	Value:    token,           // 与返回给前端的 JWT 相同
	Path:     "/events",       // 只在订阅路径上发送
	Expires:  expiresAt,       // 与 JWT 的 exp 一致
	HttpOnly: true,            // 页面脚本读不到，XSS 偷不走
	Secure:   true,            // 只经 HTTPS 发送
	SameSite: http.SameSiteLaxMode,
})
```

在下面两个条件都满足时，令牌的携带方式不用改，`new EventSource('/events/workorder')` 会自动带上 Cookie：页面和订阅地址同源；订阅路径落在 Cookie 的 `Path` 之内。生产环境应明确设置 `Secure`、`SameSite`，并让 `Expires` 和 JWT 的 `exp` 一致，规则见 [MDN Set-Cookie](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie)。需要注意以下几点：

- **401 要引导重新登录。** 没有 Cookie 或令牌已过期时，网关返回 401，原生 `EventSource` 收到非 200 的响应后会永久停止重连。应用应在 `onerror` 中判断登录状态，重新登录后再新建 `EventSource`。
- **令牌过期，推送就停。** 只要 JWT 验证通过，网关就会在 `max_duration` 和令牌 `exp` 中较早的时刻断开连接，断开原因记为 `auth_expired`，与是否配置 `subject_claim` 无关。没有 `exp` 的令牌没有过期边界，连接只受 `max_duration` 限制，签发方应始终写入 `exp`。
- **CSRF。** 订阅是只读的 GET 请求；离线模式的 ACK 必须是 `Content-Type: application/json`，普通表单发不出这种请求。`Path=/events` 能让这个 Cookie 只出现在订阅路径上。
- **跨域订阅。** 页面和网关不同源时，使用 `new EventSource(url, { withCredentials: true })`，Cookie 设为 `SameSite=None; Secure`，订阅路由配置允许凭证的 CORS。
- **离线进度按租户和用户区分。** 加上 `offline: auth.subscriber`，离线进度、会话租约和确认凭据都绑定"租户 + `subject_claim`"，不同租户里相同的用户 ID 互不影响，也不能互相确认消息。这个值只能包含字母、数字、`_`、`-`，最长 128 个字符。
- **离线模式需要可靠订阅客户端。** 离线模式推送的是 `{sequence, ack_token, payload}`，业务处理完成后必须 POST ACK，否则这个用户会一直停在第一条消息上。原来直接读取 `event.data` 的前端代码要换成可靠客户端 [browser-client.js](../../../../examples/nats-events/browser-client.js)（Go 用 `pkg/eventclient`）。只需在线信号时不加 `offline`，前端处理方式不变。
- **改不了登录流程时**，退回到 5.2 节的 `forward_auth`，由后端校验登录状态。

字段的完整说明见 [认证概述](../05-middleware/authentication.md#用-jwt-保护接口和订阅)。

### 5.4 多租户隔离

固定主题（如 `notify.workorder`）会被所有通过鉴权的租户共同订阅。不同租户只能收到自己的信号时，把已验证的身份写进主题：

```yaml
/publish:                                   # 内网发布方在正文里给出租户
  publish: notify.{body.tenant_id}.workorder
  offline: true
/events/workorder:                          # 订阅方只能订阅自己租户的主题
  auth: { type: jwt, secret: env://APP_JWT_SECRET, token_from: [cookie:lg_token], subject_claim: user_id, tenant_claim: tenant_id }
  subscribe: notify.{auth.tenant}.workorder
  offline: auth.subscriber
```

- 订阅主题只能使用 `{auth.tenant}`、`{auth.subscriber}`，它们只来自网关验证过的身份：5.3 节 JWT 的 `tenant_claim`、`subject_claim`，或者 [IDS 身份治理](../05-middleware/ids-governance.md)。写 `{query.x}`、`{body.x}` 会在加载时被拒绝，客户端在 URL 里带 `?tenant=xxx` 也改变不了订阅范围。
- `{auth.subscriber}` 可以做"按用户的私信"，例如 `notify.user.{auth.subscriber}`。
- 发布路由是内网路由，可以从正文、请求头、查询参数里取（`{body.x}`、`{header.x}`、`{query.x}`）。
- 离线模式下，发布和订阅两边自动共用一个覆盖 `notify.*.workorder` 的 stream。
- 连接限额按站点统计。需要按租户分配限额时，用完整写法 `action: {type: nats, ...}` 的 `sse.tenants` 白名单。

只用 `forward_auth` 时不会产生租户身份。这种情况有两种做法：按租户拆成不同的路由和主题，各自挂不同的鉴权；或者坚持约定 1，信号里不带数据，靠拉取接口的权限检查兜底。

## 6. 生产方：发一个 HTTP 请求

Go 服务使用 `pkg/natspub`：

```go
import "github.com/jamesleeon/LiteGate/pkg/natspub"

var notify = natspub.New("http://10.0.0.10")   // LiteGate 内网地址

// 业务事务提交之后再发；发送失败只记日志，不要影响业务结果。
func emitWorkOrderChanged(ctx context.Context, id string, version int64) {
	_, err := notify.Publish(ctx, "/internal/notify/workorder", map[string]any{
		"type":    "work_order.changed",
		"key":     id,
		"version": version,
	})
	if err != nil {
		log.Warn().Err(err).Str("work_order", id).Msg("notify failed")
	}
}
```

其它语言直接发 HTTP 请求即可：

```bash
curl -X POST http://10.0.0.10/internal/notify/workorder -H "Content-Type: application/json" -d "{\"type\":\"work_order.changed\",\"key\":\"WO-1001\"}"
```

网关返回 `202` 表示消息已交给 NATS，**不代表已持久化，也不代表客户端收到了**。这是有意的设计：通知是尽力而为的，丢失由客户端的"连上先刷新"兜底。所以发送失败时不要回滚业务，也不需要重试队列。

## 7. Web 客户端

### 7.1 使用 Cookie 登录的页面：EventSource

```javascript
// 将仓库 examples/nats-events/notify-browser-client.js 复制到应用中。
import { subscribeSignals } from './notify-browser-client.js';

const stop = subscribeSignals({
  url: '/events/workorder',
  // 每次重新查询整个列表和角标；不同对象的信号可以安全合并。
  refreshAll,
  onError: error => console.error(error)
});
// 页面离开时调用 stop()。
```

示例在首次连接和每次重连时刷新当前状态，串行执行查询，并将短时间内不同 key 的通知合并成一次完整刷新；刷新期间的新通知会触发后续刷新，查询失败会重试。若改为按 key 查询，需累计所有变更 key，不能仅保留最后一条通知。完整实现见 [notify-browser-client.js](../../../../examples/nats-events/notify-browser-client.js)。

浏览器会按网关下发的 `retry`（2 到 8 秒的随机值）自动重连，所以不用自己写重连逻辑。注意：如果网关返回非 200（比如登录过期返回 401），`EventSource` 会**永久停止**重连，这时应该引导用户重新登录，登录后再建一个新的 `EventSource`。

### 7.2 使用 Bearer 令牌的页面：fetch 读流

原生 `EventSource` 不能设置 `Authorization` 请求头。令牌存在 localStorage 里的单页应用，可以用下面这个模块代替：

```javascript
// notify.js
export function subscribeNotify({ url, headers = {}, onOpen, onEvent, onError = console.error }) {
  let stopped = false;
  let controller;
  let failures = 0;

  async function run() {
    while (!stopped) {
      let retry = 2000 + Math.random() * 6000;
      try {
        controller = new AbortController();
        const res = await fetch(url, {
          headers: { ...headers, Accept: 'text/event-stream' },
          credentials: 'include',
          signal: controller.signal,
        });
        if (res.status === 401 || res.status === 403) {
          onError(new Error(`unauthorized: ${res.status}`));
          return; // let the app re-login, then subscribe again
        }
        if (!res.ok || !res.body) throw new Error(`subscribe failed: ${res.status}`);
        failures = 0;
        await onOpen?.(); // resync: reload current state on every (re)connect
        let buffer = '';
        let data = [];
        const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += value;
          let nl;
          while ((nl = buffer.indexOf('\n')) >= 0) {
            const line = buffer.slice(0, nl).replace(/\r$/, '');
            buffer = buffer.slice(nl + 1);
            if (line === '') {
              if (data.length) await onEvent?.(data.join('\n'));
              data = [];
            } else if (line.startsWith('data:')) {
              data.push(line.slice(5).replace(/^ /, ''));
            } else if (line.startsWith('retry:')) {
              const ms = Number(line.slice(6));
              if (ms >= 1000 && ms <= 60000) retry = ms;
            } // ':' comments (heartbeats) and 'event:' lines need no handling
          }
        }
      } catch (err) {
        if (stopped) return;
        onError(err);
        failures++;
      }
      if (stopped) return;
      // Server-chosen jitter first; back off further while the gateway keeps failing.
      await new Promise(r => setTimeout(r, Math.min(retry * 2 ** Math.min(failures, 3), 30000)));
    }
  }
  run();
  return () => { stopped = true; controller?.abort(); };
}
```

使用方式：

```javascript
import { subscribeNotify } from './notify.js';

const stop = subscribeNotify({
  url: '/events/workorder',
  headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
  onOpen: () => refreshAll(),
  onEvent: data => refreshFor(JSON.parse(data)),
  onError: err => console.warn('notify:', err.message),
});
// 退出登录或离开页面时：stop();
```

收到 401 或 403 时模块会停止，不会反复重试。应用刷新令牌后重新调用 `subscribeNotify` 即可。

## 8. Go 客户端

服务之间的通知（比如配置变更后刷新本地缓存）可以使用下面这个客户端。它只依赖标准库：

```go
package notify

import (
	"bufio"
	"context"
	"errors"
	"fmt"
	"math/rand/v2"
	"net/http"
	"strconv"
	"strings"
	"time"
)

// Subscriber consumes a LiteGate `mode: subscribe` event stream.
// Messages are signals: OnOpen reloads state after every (re)connect, so
// anything missed while disconnected is recovered by that reload.
type Subscriber struct {
	URL     string
	Header  http.Header  // e.g. Authorization; sent on every connect
	Client  *http.Client // must not set Client.Timeout (the stream is long-lived)
	OnOpen  func(ctx context.Context) error
	OnEvent func(ctx context.Context, data []byte) error
	OnError func(err error)
}

var ErrUnauthorized = errors.New("notify: unauthorized")

func (s *Subscriber) Run(ctx context.Context) error {
	client := s.Client
	if client == nil {
		client = &http.Client{}
	}
	failures := 0
	for {
		retry, err := s.session(ctx, client)
		if ctx.Err() != nil {
			return ctx.Err()
		}
		if errors.Is(err, ErrUnauthorized) {
			return err
		}
		if err == nil {
			failures = 0 // the stream ended normally (max_duration, reload)
		} else {
			failures++
			if s.OnError != nil {
				s.OnError(err)
			}
		}
		wait := min(retry<<min(failures, 3), 30*time.Second)
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(wait):
		}
	}
}

// session runs one connection and returns the reconnect delay to use next.
func (s *Subscriber) session(ctx context.Context, client *http.Client) (time.Duration, error) {
	retry := time.Duration(2000+rand.IntN(6001)) * time.Millisecond
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, s.URL, nil)
	if err != nil {
		return retry, err
	}
	for k, v := range s.Header {
		req.Header[k] = v
	}
	req.Header.Set("Accept", "text/event-stream")
	resp, err := client.Do(req)
	if err != nil {
		return retry, err
	}
	defer resp.Body.Close()
	switch {
	case resp.StatusCode == http.StatusUnauthorized || resp.StatusCode == http.StatusForbidden:
		return retry, ErrUnauthorized
	case resp.StatusCode != http.StatusOK:
		return retry, fmt.Errorf("notify: subscribe status %d", resp.StatusCode)
	}
	if s.OnOpen != nil {
		if err := s.OnOpen(ctx); err != nil {
			return retry, fmt.Errorf("notify: resync: %w", err)
		}
	}
	scanner := bufio.NewScanner(resp.Body)
	scanner.Buffer(make([]byte, 64*1024), 1024*1024)
	var data []string
	for scanner.Scan() {
		line := scanner.Text()
		switch {
		case line == "":
			if len(data) > 0 && s.OnEvent != nil {
				if err := s.OnEvent(ctx, []byte(strings.Join(data, "\n"))); err != nil {
					return retry, err // reconnect; OnOpen will resync
				}
			}
			data = data[:0]
		case strings.HasPrefix(line, "data:"):
			data = append(data, strings.TrimPrefix(strings.TrimPrefix(line, "data:"), " "))
		case strings.HasPrefix(line, "retry:"):
			if ms, err := strconv.Atoi(strings.TrimSpace(line[6:])); err == nil && ms >= 1000 && ms <= 60000 {
				retry = time.Duration(ms) * time.Millisecond
			}
		} // ':' heartbeats and 'event:' lines need no handling
	}
	return retry, scanner.Err()
}
```

使用方式（需要 Go 1.21 及以上）：

```go
sub := &notify.Subscriber{
	URL:    "http://10.0.0.10/events/config",
	Header: http.Header{"Authorization": {"Bearer " + serviceToken}},
	OnOpen: func(ctx context.Context) error {
		return cache.ReloadAll(ctx) // 约定 2：连上就全量刷新
	},
	OnEvent: func(ctx context.Context, data []byte) error {
		var sig struct {
			Key     string `json:"key"`
			Version int64  `json:"version"`
		}
		if err := json.Unmarshal(data, &sig); err != nil {
			return nil // 不认识的信号直接忽略
		}
		if cache.Version(sig.Key) >= sig.Version {
			return nil // 约定 3：旧信号跳过
		}
		return cache.Reload(ctx, sig.Key)
	},
	OnError: func(err error) { log.Warn().Err(err).Msg("notify reconnecting") },
}
go sub.Run(ctx) // 返回 ErrUnauthorized 时说明凭证失效，需要排查配置
```

`OnEvent` 返回错误时，客户端会断开并重连，重连后 `OnOpen` 会再全量刷新一次，所以处理失败也不会留下不一致的状态。

## 9. 插件订阅通知：插件自己定义 subject

前面几节的消费方是浏览器和 Go 服务。网关里的**插件**同样可以消费通知，典型例子是 IDS：插件为了性能把租户、凭据缓存在进程内，租户在租户系统里被关闭后，网关缓存里还是旧状态，请求照样能通过，直到缓存过期。

LiteGate 不假设插件有没有缓存、缓存了什么。它提供的是一条**可选的通知通道**：插件声明自己关心的 subject，外部系统往这个 subject 发信号，网关把信号投递给这个插件。

```text
租户系统关闭租户 ──POST /internal/notify/tenant──▶ LiteGate ──▶ NATS: notify.tenant
                                                                   │
                     每个网关节点上声明了 notify.tenant 的插件 ◀──────┘ → 删除自己的缓存
```

subject 就是插件和外部系统之间的约定：插件定义它，外部系统往它发信号，只有声明了它的插件会收到。插件不需要在代码里判断"这条是不是给我的"。

### 9.1 插件要写什么

仅需要通知的插件才实现可选接口 `plugin.NotifySubscriber`。IDS 本身不要求缓存，也不要求订阅 notify；例如只做 MD5 验签的插件可以只实现 `Evaluate`。未实现此接口或返回空 subject 列表的插件不建立订阅，无需配置 `shared.notify`。

接口如下：

```go
type NotifySubscriber interface {
	NotifySubjects() []string
	HandleNotify(ctx context.Context, n plugin.Notification) error
}
```

下面仅以使用本地缓存、需要主动失效的 IDS Provider 为例：

```go
func (p *Provider) NotifySubjects() []string { return []string{"notify.tenant"} }

func (p *Provider) HandleNotify(ctx context.Context, n plugin.Notification) error {
	if n.Resync { // 可能漏了消息：清掉全部
		p.tenants.InvalidateAll()
		return nil
	}
	var signal struct {
		TenantID string `json:"tenant_id"`
	}
	if json.Unmarshal(n.Data, &signal) == nil && signal.TenantID != "" {
		p.tenants.Invalidate(signal.TenantID)
	}
	return nil
}
```

`p.tenants` 是 `idskit.IdentityLoader`。`InvalidateAll` 除了清空缓存，还会隔离正在进行的回源，旧结果不会被写回。

subject 支持通配符：`notify.tenant.*` 匹配一级，`notify.config.>` 匹配剩余所有层级。`_INBOX`、`$SYS`、`$JS` 开头的 subject 会被拒绝；写错的 subject 会让插件创建失败，而不是悄悄收不到消息。

### 9.2 网关保证什么

| 保证 | 说明 |
|---|---|
| 生命周期 | 仅声明非空 subject 的 Provider 在创建时订阅，退役或关闭前退订 |
| 串行 | 同一个实例的 `HandleNotify` 串行调用，可能与 `Evaluate` 并发，插件维护的状态要线程安全 |
| 隔离 | 每个插件有独立的订阅和队列，一个插件处理慢或出错不影响其他插件 |
| `Resync` | 消息不持久化、不重投。以下情况网关都会下发一次 `Resync`：订阅刚生效；断线重连；NATS 丢了消息；队列积压溢出；上一次 `HandleNotify` 返回错误或 panic（退避 1 到 30 秒后） |

收到 `Resync` 表示可能漏过通知，插件应重新校准自己依赖的状态：有缓存可以失效缓存，持有本地快照可以重新加载，没有本地状态可以直接成功返回。恢复正确性依赖插件能够重新读取当前状态，通知不会补发历史消息。

### 9.3 外部系统要发什么

和第 6 节完全一样，只是换一个主题。在第 5.2 节发布路由的 `subject_allowlist` 里加上 `tenant`，租户系统在关闭租户的事务**提交之后**发信号：

```bash
curl -X POST http://10.0.0.10/internal/notify/tenant -H "Content-Type: application/json" -d "{\"tenant_id\":\"acme\",\"type\":\"tenant.disabled\"}"
```

消息格式由插件和发布方约定，网关不解析。

### 9.4 开启通知总线

插件订阅默认关闭，在插件配置里指定使用哪个 NATS 连接即可开启：

```yaml
plugins:
  nats:
    connections:
      default:
        servers: "nats://10.0.0.20:4222"
shared:
  notify:
    connection: default
```

没有配置时，声明了 subject 的插件照常工作，只是收不到通知，启动日志里会有提示。订阅权限被 NATS 拒绝时，监听会报错并重试，在线指标为 0；Flush 成功不会被当作已授权。修改连接配置会等待旧回调退出，再重建订阅并先处理 `Resync`；与通知无关的配置变更、站点热重载都不会打断它。

### 9.5 注意事项

- **共享缓存（Redis）由发布方删除。** 插件只删自己进程内的缓存。Redis 这类多个网关共用的缓存，建议由租户系统在发信号**之前**删掉。如果让每个网关都去删，可能有网关正在用旧数据回源，删完之后又把旧值写回去。另一种做法是缓存值里带版本号，旧版本拒绝写入。
- **使用缓存时应保留 TTL。** 通知把失效延迟从"等 TTL 过期"缩短到秒级；万一通知总线长时间不可用，TTL 是最坏情况下的上限。
- **拒绝要在 `Evaluate` 里做。** 缓存失效只负责让插件尽快读到新状态；租户已关闭时，`Evaluate` 仍需返回明确的 401 或 403。
- **已经建立的连接不会被撤回。** 通知生效后，新请求会走新状态；已经在执行的请求和已经建立的长连接不受影响。

可以从这些指标观察插件订阅，`subscriber` 标签形如 `ids:<provider 名称>`：

- `litegate_notify_subscription_live`：订阅是否在线（1 为在线）。
- `litegate_notify_messages_total`：成功处理的通知数。
- `litegate_notify_resyncs_total`：下发 `Resync` 的次数。
- `litegate_notify_errors_total`：失败次数，`stage` 区分 subscribe、handler、overflow。

目前由框架自动接入的是 IDS Provider；其它类型的插件需要同样能力时，也会使用同一个接口。

## 10. 运行特性和边界

| 项目 | 行为 |
|---|---|
| 心跳 | 默认每 15 秒一次注释心跳。前置代理的空闲超时要大于心跳间隔，并关闭响应缓冲 |
| 连接时长 | 默认 15 分钟（`max_duration`）后断开，客户端随即重连；重连时会重新鉴权 |
| 配置热重载 | 大约 15 秒后会断开所有流，客户端在 2 到 8 秒的随机时间后重连并刷新，不会同时涌入 |
| 慢客户端 | 缓冲满了就断开这一条连接，不影响其他人；重连后由"刷新"补齐 |
| NATS 掉线 | 网关检测到重连后会断开流，让客户端重连并刷新 |
| 限额 | `max_connections` 按单节点、单个 `tenant` 分组计算 |
| 压缩 | LiteGate 对 SSE 自动关闭压缩。不要给事件路由配置响应缓存 |

可以从这些指标观察运行状态：

- `litegate_nats_sse_connections`：当前连接数。
- `litegate_nats_sse_messages_total`：推送出去的信号数。
- `litegate_nats_sse_disconnects_total`：断开次数，`reason` 区分限额、慢客户端、写错误、NATS 不可用、到达最长时长和停机。
- `litegate_nats_sse_dropped_events_total`：因格式错误或超大而丢弃的消息。

**这套方案不保证的事：** 消息不持久化、不重放，也不知道客户端是否处理了某条信号。这些都由第 3 节的约定兜底，所以只适合"信号 + 拉取"的模式。如果一条消息本身就是数据，必须逐条送达并由应用确认，请使用 [可靠事件通知](../04-actions/nats-events.md)。它的成本高得多：每个订阅者对应一个 JetStream 持久消费者。

## 11. 从自建 SSE 迁移

JWT、Cookie 续签、多租户隔离、可靠 ACK、租户停用及 MCP 操作的配置与限制，集中见 [Notify 与业务 JWT 接入](./notify-jwt-integration.md)。

1. 部署 NATS，按第 5 节配置发布路由和订阅路由。
2. 业务后端写一个"检查登录"接口给 `forward_auth` 用，通常复用现有的鉴权逻辑。
3. 生产方把"POST 到后端的内部事件接口"改成"POST 到 `/internal/notify/<主题>`"，消息体按约定 1 精简为信号。
4. 前端把 `EventSource` 的地址改到 `/events/<主题>`，确认 `onopen` 里会刷新、`onmessage` 里只做"按信号拉取"。如果原来的消息里带了业务数据，改成收到信号后调用接口查询。
5. 观察一段时间指标，确认没问题后，删除后端的 SSE 接口、连接注册表和内部事件分发器。

迁移完成后，业务后端就是一个普通的无状态 HTTP 服务，可以随意扩成多个实例，不用再考虑广播。
