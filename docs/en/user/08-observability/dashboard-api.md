# Dashboard API Reference

The Dashboard pages and the management API share one port. This page lists every endpoint the current code registers, for scripts and automation.

## 1. Basics

```yaml
dashboard:
  enabled: true
  port: 9999                  # default 9999, listens on all interfaces
  username: admin
  password: REPLACE_WITH_STRONG_PASSWORD
  token: REPLACE_WITH_API_TOKEN   # for automation
  allowed_origins: []         # extra allowed Origins; empty means same-origin only
  require_secure_cookie: false    # enable when accessed over HTTPS
```

The Dashboard listens on all interfaces. In production restrict sources with a firewall or a fronting gateway; never expose it publicly.

### Authentication

Every endpoint except `/login`, `/api/login` and static assets requires authentication, checked in this order:

1. **API token**: header `X-API-Key: <dashboard.token>`. A correct value is accepted; a wrong value returns 401 immediately without falling back to the cookie.
2. **Login cookie**: `POST /api/login` sets a signed cookie valid for 24 hours. POST/PUT/DELETE requests authenticated by cookie must carry a same-origin `Origin` or `Referer`, or one matching `allowed_origins`; otherwise 403.

Without a configured `username`, cookie login is always refused. Unauthenticated page requests redirect to `/login`; JSON endpoints return 401.

`/api/scan-protection/toggle` and `/api/scan-protection/unblock` require a valid `Origin` or `Referer` regardless of the authentication method.

### Response envelope

Most management endpoints return:

```json
{"success": true, "message": "Saved successfully"}
{"success": true, "data": {}}
```

On failure `success` is `false`, `message` carries the reason, and the HTTP status reflects the error class.

### Example

```bash
curl -H "X-API-Key: $TOKEN" http://127.0.0.1:9999/status/json
```

## 2. Login

| Method | Path | Description |
|---|---|---|
| GET | `/login` | Login page |
| POST | `/api/login` | Body `{"username": "...", "password": "..."}`; sets the cookie on success |
| POST | `/api/logout` | Clears the cookie |

## 3. Status and runtime

| Method | Path | Description |
|---|---|---|
| GET | `/status` | Dashboard page |
| GET | `/status/json` | Gateway status JSON; `?service=<name>` narrows to one service |
| GET | `/overview/json` | Overview data |
| GET | `/api/runtime` | Runtime data (memory, goroutines, ...) |
| GET | `/api/upstreams` | Upstreams and health |
| GET | `/api/ddns` | DDNS and internal DNS sync status |
| GET | `/api/stream/traffic` | Live traffic (SSE) |
| GET | `/metrics` | Prometheus metrics; registered only when `metrics.enabled: true`, requires login |

## 4. Routing diagnostics

| Method | Path | Description |
|---|---|---|
| GET | `/status/routing` | Routing page |
| GET | `/api/routing` | Current routing table |
| GET | `/api/routing/explain` | Simulate matching for a request; parameters `host`, `method`, `path`, `entrypoint`, `client_ip` |
| GET | `/api/routing/pipeline` | Middleware pipeline of a route; parameters `site`, `route` |
| GET | `/status/tags` | Service tags page |
| GET | `/api/service-tags` | Parsed service tags |

## 5. Configuration

| Method | Path | Description |
|---|---|---|
| POST | `/api/config/validate` | Validate without saving. Body `{"kind": "site\|lite\|stream", "filename": "...", "content": "..."}`; `kind` is inferred from the filename when empty |
| POST | `/api/save` | Save a file. Body `{"type": "site\|stream", "filename": "app.yaml", "content": "..."}`; `content` may be a YAML string or a JSON object; filenames must end in `.yaml` |
| POST | `/api/delete` | Delete a file. Body `{"type": "site\|stream", "filename": "app.yaml"}` |

With `dashboard.release_control.enabled`, `/api/save` and `/api/delete` only change the draft and return it; publish it to take effect. Otherwise they write to the configuration store directly and trigger a reload.

## 6. Release control

These endpoints require `dashboard.release_control.enabled` and return 400 otherwise. See [Configuration release control](../../release_control_guide.md) for the workflow.

| Method | Path | Description |
|---|---|---|
| GET | `/api/releases` | List all releases, drafts included |
| POST | `/api/releases` | Create a draft from an array of configuration artifacts; an empty array is refused while active configuration exists |
| GET | `/api/releases/{id}` | Release details |
| POST | `/api/releases/{id}/validate` | Dry run |
| POST | `/api/releases/{id}/publish` | Publish |
| GET | `/api/releases/{id}/diff` | Diff of this release against the active configuration |
| POST | `/api/releases/{id}/rollback` | Roll back to this release; use `previous` as `{id}` for the previously active release |
| GET | `/api/releases/history` | Change history |
| GET | `/api/snapshot/export` | Download snapshot `litegate-snapshot.json` |
| POST | `/api/snapshot/import` | Import a snapshot as a new draft |
| GET | `/api/snapshot/resolved-sites` | Download resolved sites `resolved-sites.json` (does not need release control) |

## 7. Certificates

| Method | Path | Description |
|---|---|---|
| GET | `/api/cert/download?file=<name>` | Download certificate and key as ZIP |
| POST | `/api/cert/dry-run` | Check whether a DNS provider can complete a challenge for a domain. Body `{"provider": "...", "domain": "..."}`; 503 when auto cert is not running |

## 8. Security and cache

| Method | Path | Description |
|---|---|---|
| POST | `/api/scan-protection/toggle?enabled=true\|false` | Toggle scan protection until restart |
| POST | `/api/scan-protection/unblock?ip=<ip>` | Unblock one IP |
| POST | `/api/proxy-cache/purge` | Purge the proxy cache. Body `{"scope": "all\|site\|route\|key", "site": "...", "route": "...", "base_key": "..."}` |

## 9. Logs and docs

| Method | Path | Description |
|---|---|---|
| GET | `/status/logs` | Logs page |
| GET | `/api/logs/tail` | Recent log lines; parameters `after` (cursor), `limit` |
| GET | `/status/docs` | Built-in configuration docs page |
| GET | `/api/docs` | Built-in docs index |
| GET | `/api/docs/content?slug=<slug>&lang=<zh\|en>` | Built-in doc body |

## 10. Self-service publishing

With `self_service` enabled, `/publish`, `/publish/` and `/api/publish/` are handled by the self-service portal, which has its own account and cookie and does not use the rules above.

## Related

- [Dashboard](dashboard.md)
- [Metrics](metrics.md)
- [Configuration release control](../../release_control_guide.md)
