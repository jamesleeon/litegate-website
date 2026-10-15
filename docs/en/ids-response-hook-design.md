# IDS request and response correlation design

Status: design baseline. Request State, optional response hooks, plugin-owned
memory/Redis storage and the SaaS example are implemented. The current API,
configuration and limits are described in the [SaaS guide](ids-saas-session-guide.md).
`memory_redis` remains unavailable. Proposed examples in the original design are
not a replacement for the implemented configuration reference.

## Business boundary

The Router selects a Service. IDS constrains that Service's instances through
Match and Meta: Match is a hard boundary; an unmatched Meta preference falls back
inside the same Match pool. The application manages tenant authentication and
database selection. The gateway only selects the appropriate application cluster.

Login looks up the tenant's cluster before a token exists. Its response hook binds
the returned token to that request's tenant/cluster information. API requests
recover the mapping; logout deletes it; refresh atomically replaces it. Tenant
disable events invalidate mappings and prevent late login from recreating them.

## Optional interface and request lifetime

`IDSProvider.Evaluate(context.Context, IDSInput)` remains the request interface.
Providers can optionally implement `IDSResponseHandler.OnResponse`. API-only
providers need neither response State nor a hook. Response inputs expose immutable
request/response views, the original options/configuration snapshot, copied State
and final endpoint identity. Providers cannot retain a mutable HTTP response.

State is request-local, has a host-enforced size limit, and is not sent downstream
or written to shared storage. It is released on hook completion or request
termination. Returning State when the hook is disabled is a configuration error.
The same Provider instance stays leased until its real callback exits, including
callbacks that ignore cancellation. Hot replacement does not close a Provider
still serving a request or hook.

## Correlation and final response

Generate a cryptographically random correlation key with at least 128 bits of
entropy. Project it through an explicitly allowed request header. Save its exact
original value plus tenant/cluster/version data in State. A successful login must
return the same correlation header and one token header. Check exact equality with
this request's State; merely finding the key in a cache does not prove correlation.

The hook runs once on the final backend HTTP response after retries. Intermediate
retry responses, mirror requests, direct IDS rejection, rate limiting, discovery
failure and transport failures without a final backend response do not create
bindings. Normal application 401/403 responses still reach the hook, which can
allow them without requiring a success token. Remove internal correlation response
headers before delivery.

The first implementation allows validated business-header removal, not response
body modification or removal of transport fields such as Content-Length. Hooks
support ordinary HTTP proxying, exclude response cache, and reject Upgrade/gRPC.
WASM request providers remain compatible; WASM response hooks are unavailable.

## Failure and concurrency protection

Callbacks execute before response headers are delivered. Login binding should use
deny: storage failure must not expose a successful token whose mapping was not
committed. Errors, panics, timeout, concurrency rejection and invalid decisions are
controlled; ordinary errors can follow an explicit allow policy, while panic,
timeout and invalid decisions remain rejected. Callback errors are not backend
instance failures and do not automatically retry application login.

Timeout cannot forcibly stop Go code that ignores context. Keep its concurrency
slot and Provider lease until it exits; discard late response changes. Storage
operations must honor deadlines. A timeout does not prove that Redis failed to
commit. Storage commit and HTTP delivery cannot be one distributed transaction:
allow orphaned bindings to expire by TTL instead of deleting a token that may
already have reached the client. Idempotent writes must not extend expiry.

## Plugin-owned storage and invalidation

Memory is an authoritative bounded single-process store and loses state on restart.
Redis is authoritative shared storage for multiple gateways. Connection pools,
session schema, TTL, tenant indexes, atomic writes and cleanup belong to the
business plugin, not the gateway SDK. The example supports one Redis service;
Redis Cluster multi-key indexing requires a separate slot/partition design.

Session lookup distinguishes miss/expiry (401), disabled tenant (403), and storage
failure (503). Do not treat an outage as a miss or fall back to an unconstrained
pool. Remove forged trust headers before projecting trusted values.

Disable a tenant in authoritative state first, advance its monotonic version, then
invalidate mappings and publish notification. Login/refresh commit checks that
version atomically; old or duplicated events cannot overwrite newer state. Core
NATS notifications are signals, not durable replay. Startup, reconnect, overflow
and handler failure require Resync against authoritative tenant state. A local
cache must have an explicit invalidation/recovery/TTL policy before a hybrid mode
can be offered.

## Acceptance requirements

- Bind login response to the correct request and preserve tenant cluster isolation.
- Reject missing/duplicate token headers and swapped correlation headers.
- Distinguish Redis failures from misses; never publish State/tokens in logs.
- Invoke the hook once after final retry and release State on every early exit.
- Preserve Provider/configuration snapshots during hot replacement.
- Bound callback timeout/panic/concurrency and reject late modifications.
- Share sessions across gateways; test logout, TTL and atomic refresh races.
- Prevent late login after tenant disable and recover after notification disconnect.

Implementation locations include `pkg/plugin/ids.go`, loader validation, IDS
governance/guard middleware, final proxy response processing and the
[SaaS example](../../examples/ids-saas-session/README.md). Existing request-only
providers and configurations without a hook retain their behavior.
