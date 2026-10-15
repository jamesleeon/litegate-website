# Configuration release control

When release control is enabled, Dashboard saves/deletes create a draft. Validate and inspect the diff before explicit publication; retained history supports rollback. This manages configuration versions, not percentage-based request canaries.

Enable both dashboard.enabled and dashboard.release_control.enabled and provide writable configuration/history storage. Local files, Consul and LiteMesh are supported. roles.config_watch determines the configuration backend; enabling discovery alone does not switch storage. KV mode commits snapshots through CAS on _release.json under the site prefix.

States progress from draft → validated → publishing → active/active_with_warnings or failed. Rollback creates a new active version while preserving history. Editing an existing working draft resets it to draft. Review errors, warnings and differences before publication, then verify runtime state. On failure, inspect logs and file/KV permissions. Direct external file changes do not necessarily pass through Dashboard drafts.

```yaml
dashboard:
  enabled: true
  port: 9999
  username: admin
  password: REPLACE_WITH_STRONG_PASSWORD
  release_control:
    enabled: true
```

## Related documentation and code

- [Implementation](../../internal/release)
- [Dashboard](user/08-observability/dashboard.md)
