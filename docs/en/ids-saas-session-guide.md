# SaaS login and cluster routing with IDS

The SaaS example implements login, API, logout and refresh as business IDS
providers. Applications remain responsible for authentication and tenant database
selection. The gateway selects the tenant's application cluster and preserves the
Router's Service boundary.

## Four request paths

| Path | Evaluate | Optional OnResponse |
|---|---|---|
| login | Look up tenant cluster, generate correlation header and private State | Validate returned correlation/token and create session mapping |
| api | Read token mapping, produce Match/Meta | Not required |
| logout | Select using existing mapping, retain session key | Remove mapping after successful application logout |
| refresh | Route with old mapping and generate fresh correlation | Atomically replace old token mapping |

Providers share a private storage protocol, not necessarily one Provider instance.
The API provider does not implement OnResponse or return State.

## Correlation and trust

Login projects a random `X-IDS-Correlation` header and saves its original value,
tenant ID, cluster code and tenant generation in request-local State. The backend
must return that exact value and one `X-Access-Token` on success. Compare against
the original State, then store a token digest mapping and remove the internal
correlation response header. At least 128 bits of cryptographic randomness are
recommended. State is neither shared session storage nor an application header.

Tenant hints locate a login cluster; they are not authentication credentials.
Arbitrary client headers are not trusted tenant identities. Application token
authenticity and expiry still need validation. Trusted projection only has meaning
on a trusted gateway-to-application connection.

## Configuration and tags

Plugin configuration comes through `plugin_config.path`. The SaaS plugin owns
`providers.saas_session.stores`; each named store supplies mode, prefix and TTL.
Redis settings include address, database and a password environment reference.
Do not put passwords in route labels. Memory mode supports a bounded local store;
Redis shares authoritative state across gateways. `memory_redis` is rejected until
cross-instance invalidation and recovery are implemented. Store configuration
changes require restart; ordinary route reload does not clear session mappings.

A login Router selects `saas_login`, uses deny, enables response_hook with timeout
and max_concurrency, allows `X-IDS-Correlation` projection, and supplies store_ref,
tenant_directory_url, correlation_header, response_token_header and success_status
through options. API selects `saas_api` without a hook. Logout and refresh use their
own paths and Providers with a hook. See the runnable example's current
[site configuration](../../examples/ids-saas-session/site.yaml) and
[plugin configuration](../../examples/ids-saas-session/plugins.yaml).

Catalog Router tags support the same hook validation:

```text
litegate.http.routers.login.entrypoints=web
litegate.http.routers.login.match.hosts=saas.example.com
litegate.http.routers.login.match.path=/login
litegate.http.routers.login.ids.provider=saas_login
litegate.http.routers.login.ids.allowedheaders=X-IDS-Correlation
litegate.http.routers.login.ids.response_hook.enabled=true
litegate.http.routers.login.ids.response_hook.timeout=500ms
litegate.http.routers.login.ids.response_hook.max_concurrency=100
litegate.http.routers.login.ids.response_hook.fail_policy=deny
litegate.http.routers.login.ids.options.store_ref=saas-session
```

Compile the plugin before using its tags. Keep route labels consistent across
same-name instances; put cluster/version differences in instance metadata.
`ids.selector_merge_policy` defaults to intersect; explicit override remains
subject to the documented IDS boundary. Tags do not provision Redis storage.

## Response behavior

The original Provider and configuration snapshot handle the final backend response
once after retry completion, before client response processing. Normal application
401/403 responses enter the hook; direct IDS rejection, rate limiting, discovery
failure and transport failure without a backend response do not. Every path
releases State.

Deny prevents delivery of an unbound success token on storage errors. Callback
panic, timeout, overload and invalid header removal are controlled. Explicit allow
can permit an ordinary callback error; timeout/panic/invalid decisions still reject.
Late callbacks cannot modify responses and keep their lease/concurrency slot until
they actually exit. The first hook implementation only removes permitted business
headers: no body modification, response cache, Upgrade, gRPC or WASM response hook.

Metrics are `litegate_ids_response_duration_seconds`,
`litegate_ids_response_total{provider,result}` and `litegate_ids_response_inflight`.
Tokens, State and business keys are not metric labels.

## Session storage

The private implementation is in the example's `ids/sessionstore` package.

| Operation | Contract |
|---|---|
| Get | Read an unexpired session with valid tenant generation |
| Put | Atomically write session/index after generation check; idempotency does not extend TTL |
| Replace | Create new token and remove old valid token atomically; reject refresh replay |
| Delete | Idempotently remove session and index member |
| GroupState | Read tenant generation and disable state |
| ChangeGroup | Accept only newer authoritative generations |
| PurgeGroup | Batch-clean old/disabled mappings and index members |

Values include tenant ID, cluster code and preferred version. Keys use token
digests; Redis further hashes logical keys/groups and indexes expiry in sorted
sets. API traffic does not renew TTL. Memory defaults to 100000 entries. Values
are limited to 64 KiB; positive monotonic generations are bounded by 2^53.

Redis uses atomic Lua operations. Tenant generation state survives session TTL to
prevent old sessions from reviving. Redis server TTL is authoritative; client
ExpiresAt is informational. Gateways must share store name, prefix, Redis address
and database. This is a single Redis service implementation, not Redis Cluster HA
or performance certification. Successful commit followed by failed HTTP delivery
may leave a mapping until TTL; commit and delivery are not one transaction.

## Tenant disable and notifications

First persist tenant disable and advance its generation, then broadcast tenant ID,
version and disabled state. ChangeGroup makes old sessions immediately unreadable;
PurgeGroup removes them physically. Late login/refresh cannot commit an old
generation. Re-enabling requires a higher generation and does not restore old tokens.

Optional NotifySubscriber receives `notify.saas.tenant`. Core NATS is not durable:
initial subscription, reconnect, overflow and handler error trigger Resync. Recheck
authoritative tenant state instead of merely clearing local cache and reloading
old Redis data. The example also checks tenant state on API requests. Production
caches need explicit TTL and recovery rules; notification publication does not
guarantee instant rejection on every gateway.

The standard distribution includes NATS. Custom builds can link
`github.com/jamesleeon/LiteGate/pkg/plugins/nats`. Restrict notification publishers
to trusted business actors and do not publish raw tokens. Every relevant gateway
must receive invalidation, rather than competing for one broadcast message.

## Runnable example and verification

See [examples/ids-saas-session](../../examples/ids-saas-session/README.md).

```powershell
powershell -NoProfile -File examples/ids-saas-session/build.ps1
python examples/ids-saas-session/verify.py
python examples/ids-saas-session/verify.py --catalog-tags
```

The loopback lab starts/stops its own processes: two application clusters, tenant
directory, two gateways, NATS and a miniredis test fixture. It does not change
existing LAN services. Coverage includes cross-gateway login/API, tenant isolation,
refresh races, logout, TTL, concurrent login, invalid correlation/token headers,
application rejection, notification disable and in-flight login races. Core tests
cover timeout/panic, snapshot/lifecycle handling, final retry responses, illegal
header removal and batched reverse-index cleanup.

Evidence is saved under `artifacts/ids-saas-session`, without raw tokens.
Gateway duties remain Evaluate, request State, forwarding and optional OnResponse.
The plugin manages pools and shared storage lifetime; closing one business
Provider must not destroy storage still used by the other Providers.
