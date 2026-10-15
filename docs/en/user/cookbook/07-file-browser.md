# File browser: List, image viewer, and local SSO

This recipe provides a file browser behind built-in SSO, with List/Grid views, image previews, an in-page previous/next viewer, search, sorting, and downloads. Directory pages, original images, and downloads share the same authentication policy.

Configuration files:

- [list-config.yaml: global listener configuration](list-config.yaml)
- [list-sso.yaml: file browser and SSO site](list-sso.yaml)

## 1. Prepare the files

Use a separate working directory. Copy `list-config.yaml` to `config.yaml` and `list-sso.yaml` to `sites/list.yaml`. Create `sites`, `streams`, and `www`; place shared files and images in `www`.

```text
file-browser/
├── config.yaml
├── sites/
│   └── list.yaml
├── streams/
└── www/
    └── images/
```

Set `entrypoints.web.address` and `site` to the server's actual IP. The example uses `192.168.50.24:18091`. For local testing, use `127.0.0.1:18091` with `site: 127.0.0.1`. Set `list.root` to your shared directory; relative paths resolve from the LiteGate process working directory.

For an existing instance, merge the site configuration and select the actual entrypoint name instead of overwriting the global configuration.

## 2. Set up the account

Generate an independent session secret and a bcrypt password hash:

```sh
litegate -secret
litegate -hash 'replace-with-your-own-password'
```

Replace `auth.secret` with the generated secret and `auth.users.demo` with the hash. You may rename `demo`. Preserve the `$` characters in the hash; do not put a plaintext password in `users`. No real demo credentials or session secrets are included in these files.

This HTTP LAN demo uses `cookie_secure: false`. Use HTTPS and `cookie_secure: true` for production. Sessions last 3600 seconds. Built-in local SSO needs no external identity provider and does not provide cross-domain SSO or MFA.

## 3. Validate and start

Run from the working directory above:

```sh
litegate -t -config ./config.yaml
litegate -config ./config.yaml
```

Open `http://192.168.50.24:18091/`. Unauthenticated requests redirect to the login page. Sign in with the configured account to return to the file listing; use **Sign out** at the bottom to log out.

Switch between **List / Grid**. Click an image to open the in-page viewer. Use previous/next buttons, arrow keys, or mobile swipes; press Esc or **Close** to dismiss it. The viewer follows the current search results and sort order. Previews load original images lazily; no separate server thumbnails are generated.

`show_hidden: false` hides dot-prefixed paths and denies direct access. `list` always lists directories rather than automatically serving `index.html`. This example places both `auth` and `list` at the site root. If using `routes`, place authentication on the appropriate route and ensure it also handles the login path.

## References

- [List](../04-actions/list.md)
- [Authentication and SSO](../05-middleware/authentication.md)
