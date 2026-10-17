# Configuration Release Control

LiteGate's built-in **configuration release control** stages changes to site/stream configuration as a **draft** first; they take effect only after validation, a diff review and an explicit **publish**. Every publish is kept in history and can be rolled back in one step.

It manages configuration versions; it does not split request traffic by percentage to a new version. It also only governs changes made through the Dashboard / API / MCP — editing files on disk or KV directly bypasses drafts.

> The difference in one sentence: by default, changing a configuration file is hot-reloaded by the watcher and takes effect immediately; with release control on, Dashboard saves/deletes go into a **draft** first and only reach disk when you **publish explicitly**. This is a white-box change control layer built into the gateway, not an external CI/CD system.

---

## 1. Use cases and prerequisites

For production setups that need "validate, confirm and be able to roll back before changing configuration":

- dry-run validation (schema, port conflicts, reserved paths, security warnings) before changes take effect;
- several files changed together that should take effect **atomically**, not via intermediate hot-reload states;
- change history and **one-step rollback** to the last known good version;
- exporting/importing a whole configuration snapshot for backup or migration.

### Prerequisites (important)

Release control supports local files, Consul and LiteMesh. The configuration backend is decided by `roles.config_watch`; enabling only service discovery doesn't switch the configuration backend. In KV mode, site and stream configuration is stored in `_release.json` under the site prefix, and the complete snapshot is committed with one CAS write.

The startup log tells you the current state:

- Enabled: `Configuration release control plane successfully initialized`
- Disabled: `Configuration release control disabled.`

---

## 2. Enabling it

Turn on `release_control` under `dashboard` in the main configuration:

```yaml
dashboard:
  enabled: true
  port: 9999
  username: admin
  password: "your-strong-password"
  # enable configuration release control
  release_control:
    enabled: true
```

It is actually enabled only when all of these hold:

1. `dashboard.enabled: true` (the control plane is exposed through the Dashboard);
2. `dashboard.release_control.enabled: true`;
3. the current configuration backend is readable and writable, and the release history directory is writable.

Drafts and release history are stored locally: by default in `.litegate/releases/` next to the sites directory, or `./.litegate/releases/` when no sites directory is configured; set `dashboard.release_control.store_dir` to choose (see section 8).

---

## 3. Core concepts

| Concept | Description |
|---|---|
| **Release** | A configuration snapshot with a set of ConfigArtifacts, a validation report, a diff summary, a status and creation/publish details. |
| **ConfigArtifact** | One configuration file. Fields: `kind` (`site`/`stream`), `name` (file name such as `example.com.yaml`), `content` (YAML text), `checksum` (SHA256), `source`, `path`. |
| **Draft** | An unpublished working version. Only one "current draft" exists at a time. |
| **Active** | The version written to the configuration backend and confirmed by the current gateway's synchronous reload, tracked by the `active.txt` pointer. |
| **Previous** | The previously active version, tracked by `previous.txt`, used for "roll back to the previous version". |

### State transitions

```
draft ──validate──> validated ──publish──> active
  │                     │                    │
  │                     └──publish──> active_with_warnings (published with non-blocking warnings)
  │
  └──publish fails validation──> stays draft (report written to validation, not downgraded)
                                            │
                       rollback ──> old active marked rolled_back, a new active is created
```

Status constants: `draft`, `validated`, `publishing`, `active`, `active_with_warnings`, `failed`, `rolled_back`.

> Note: when saving or deleting while a `draft`/`validated`/`failed` working version exists, the same draft is reused and reset to `draft`; previously staged changes are **not** lost.

---

## 4. Using it in the Dashboard

With release control on, the Dashboard's existing "save configuration / delete configuration" behavior changes (MCP write operations such as `save_site_config` / `save_stream_config` also write only to the draft):

1. **Save/delete** → the change goes into the **current draft**; the API returns `requires_publish: true` and `draft_id`, and the configuration has **not yet taken effect**;
2. The UI asks "Saved as draft (ID: …). Publish now?":
   - Yes → calls the publish API; configuration is written, the watcher hot-reloads, and it takes effect immediately;
   - No → the change stays in the draft and can be validated/published later through the API.

> Common question: **"I clicked save, why didn't the site change?"**
> Because release control is on, saving only writes the draft. Confirm the publish in the dialog, or call `POST /api/releases/{id}/publish`.

---

## 5. Workflow (recommended order)

```
Save changes (into the draft)
   └─> (optional) validate the draft  POST /api/releases/{id}/validate
        └─> review the diff           GET  /api/releases/{id}/diff
             └─> publish              POST /api/releases/{id}/publish   ← publish runs a dry-run validation again
                  └─> if something is wrong, roll back  POST /api/releases/previous/rollback
```

Key points:

- **Publishing includes dry-run validation**: even if you skip `validate` and `publish` directly, validation is enforced first; on failure publishing stops and nothing is written.
- **Publishing is atomic**: the local implementation uses "temporary files → back up originals → atomic rename → clean up", committing `sites/` and `streams/` together; any failed step rolls back all changes, leaving no half-written files or `.tmp-*/.bak-*` leftovers in the production directories.
- **Rollback is a publish too**: rollback creates a new release record (keeping the audit trail) and marks the replaced active version `rolled_back`.

---

## 6. API reference

All endpoints require Dashboard authentication (see [Authentication](#authentication)). The path prefix follows the Dashboard's reverse-proxy prefix; the root path is used below.

### 6.1 Release management: `/api/releases`

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/releases` | List all releases (newest first). |
| `POST` | `/api/releases` | Create/update the draft from the artifact list in the body. **See the full-replacement warning below.** |
| `GET` | `/api/releases/{id}` | Get one release. |
| `POST` | `/api/releases/{id}/validate` | Dry-run validate a draft and return the report. |
| `POST` | `/api/releases/{id}/publish` | Publish a release (validated automatically first). |
| `POST` | `/api/releases/{id}/rollback` | Roll back. `previous` as `{id}` rolls back to the previously active version; a release ID rolls back to that release. |
| `GET` | `/api/releases/{id}/diff` | Differences (add/modify/delete) of the release against the **currently active configuration on disk**. |

Responses are `{ "success": <bool>, "data": <object> }`.

> ⚠️ **`POST /api/releases` has declarative full-replacement semantics.**
> The draft is **the complete set** of artifacts in the request body. Publishing it deletes every `.yaml/.yml` configuration in the production directories that **isn't in the list**.
> So if you POST a single file and publish, all other site/stream configuration is removed.
> The Dashboard's "save → publish" flow is safe (it accumulates the full set from the current draft/active configuration); if you script against this raw endpoint, **always send the complete set** or you will delete configuration.

**Draft request body example:**

```json
[
  {
    "kind": "site",
    "name": "example.com.yaml",
    "content": "site: example.com\nrespond: OK\n"
  }
]
```

**Publishing example (curl with an API token):**

```bash
# 1. Validate
curl -X POST -H "X-API-Key: $TOKEN" \
  http://127.0.0.1:9999/api/releases/20260627-153411-a1b2c3d4/validate

# 2. Review the diff
curl -H "X-API-Key: $TOKEN" \
  http://127.0.0.1:9999/api/releases/20260627-153411-a1b2c3d4/diff

# 3. Publish
curl -X POST -H "X-API-Key: $TOKEN" \
  http://127.0.0.1:9999/api/releases/20260627-153411-a1b2c3d4/publish

# 4. Something is wrong: roll back to the previous version
curl -X POST -H "X-API-Key: $TOKEN" \
  http://127.0.0.1:9999/api/releases/previous/rollback
```

### 6.2 Snapshot import/export: `/api/snapshot/*`

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/snapshot/export` | Export all **currently active** configuration as snapshot JSON (with `Content-Disposition`, `exported_at` and artifacts; platform-specific absolute paths are stripped for migration). |
| `POST` | `/api/snapshot/import` | Import snapshot JSON **as a draft** (not applied directly). Body limit 10 MB; artifact file names are checked for safety. |
| `GET` | `/api/snapshot/resolved-sites` | Export the runtime **resolved** site view (including routes resolved from dynamic discovery) for troubleshooting and records. |

### Authentication

Reuses Dashboard authentication (`checkAuth`):

- **API token** (preferred for automation): header `X-API-Key: <dashboard.token>`; a match is accepted and **CSRF checks are not applied**;
- **Cookie session** (browser): after login, a signed cookie is sent; write operations (POST/DELETE/PUT) additionally check `Origin`/`Referer` (CSRF protection).

---

## 7. What validation checks

Publish/validate dry-runs the load in a **temporary directory** with a separate loader instance (it doesn't touch the live loader or read/write production paths) and checks:

- **Schema parsing**: whether site and stream configuration parses and loads;
- **Port conflicts**: duplicate `domain:port` definitions and duplicate L4 listeners on the same `port/protocol` (errors, blocking publish);
- **Reserved path conflicts**: routes that directly hit internal endpoints such as `/_litegate`, `/healthz`, `/readyz`, `/metrics`, `/pprof` (exact/prefix matches are errors; DSL rules containing the keywords produce warnings);
- **Security best practices**: proxy routes with `insecure_skip_verify: true` produce a **warning** (non-blocking; the published status becomes `active_with_warnings`).

> Errors block publishing; warnings don't, but they are recorded in the validation report and mark the release as "active with warnings".

---

## 8. Storage and limits

- **Location**: `dashboard.release_control.store_dir`, default as in section 2.
  - `revisions/{id}/manifest.json`: the full record of each version;
  - `active.txt` / `previous.txt`: pointers to the current / previous active version.
- **Release ID**: `YYYYMMDD-HHMMSS-<random hex>`, sortable by time.
- **No automatic retention/cleanup yet**: history keeps accumulating; on long-running systems clean `revisions/` yourself (for example keep the latest N).
- **Commit and rollback**: a complete backup is read first, then configuration is committed, the current gateway's reload result is checked synchronously, and finally history pointers are updated. If the reload or history commit fails, configuration is restored and reloaded again; a failed restore is returned together with the original error. A process exiting midway or unrecoverable disk failures still need manual checking.
- **KV snapshot**: after the first publish, `_release.json` becomes the authoritative source for site and stream configuration; the old per-file KV keys are kept for migration recovery but no longer loaded. Dashboard/MCP edits update the snapshot. Change configuration through the publish API or snapshots, not the old keys. CAS conflicts reject the publish or roll back compensatingly, so a newer configuration from another gateway isn't overwritten.
- **Cluster confirmation scope**: the publish response confirms the current gateway's reload result; other instances load the complete snapshot through their watchers, and there is no all-nodes confirmation barrier. Release history stays local to the current instance, so persist that directory.

---

## 9. FAQ

**Q: With release control on, the site doesn't change after saving in the Dashboard.**
A: Expected. Saving only writes the draft; confirm the publish in the dialog or call `POST /api/releases/{id}/publish`.

**Q: How do Consul/LiteMesh use release control?**
A: Just enable `dashboard.release_control.enabled`; `roles.config_watch` decides which KV backend is written. The first publish migrates existing site and stream configuration into a single complete snapshot; every gateway consuming the snapshot must run a version that supports snapshots.

**Q: I POSTed `/api/releases` from a script and published, and other sites disappeared.**
A: The endpoint is a declarative full replacement: the draft is exactly the set you send, and publishing removes configuration not in it. Send the complete set, or use the Dashboard's "save → publish" accumulating flow.

**Q: Publishing failed — is the draft still there?**
A: Yes. When validation fails before publishing, the draft isn't downgraded or deleted; the report is written to the release, and you can publish again after fixing it.

**Q: How do I roll back?**
A: `POST /api/releases/previous/rollback` rolls back to the previously active version; you can also roll back to a specific release ID. Rollback creates a new audit record and marks the old version `rolled_back`.

---

## Related docs

- [Dashboard](user/08-observability/dashboard.md)
- [Site configuration](user/03-configuration/site-config.md)
- [L4 stream configuration](user/03-configuration/stream-config.md)
- [Dashboard API reference](user/08-observability/dashboard-api.md)
