# Add a DNS provider

Default LiteGate builds support Alibaba Cloud (`aliyun`), Tencent Cloud (`tencent` / `tencentcloud`), and Cloudflare (`cloudflare`). For another service, find its implementation in the [libdns provider directory](https://github.com/libdns) and compile it into your own LiteGate with `litegate build --dns`. Compatible providers require no plugin code.

Providers are downloaded and linked at build time. Editing YAML does not download a runtime plugin. Each provider is a separate module, so your choice does not grow the official binary. Some implementations depend on cloud SDKs; your binary size depends on the selected modules and their dependencies.

## 1. Choose a provider

Read the selected release's README, `Provider` fields and `go.mod`. Automatic integration requires a root package exporting a `Provider` struct targeting the **libdns v1 API**.

| Purpose | Required interfaces and record support |
|---|---|
| Certificate DNS-01 | `RecordAppender`, `RecordDeleter`, and TXT support |
| DDNS | Also `RecordGetter`, and the required A / AAAA support |
| ECH publication | Also `RecordGetter`, and HTTPS record support |

An interface does not guarantee support for every record type. Check the implementation and account permissions. The [libdns core](https://github.com/libdns/libdns) defines interfaces; you need a specific provider module. Module names can differ from LiteGate's built-in types: Alibaba Cloud's module is `alidns`, while its built-in LiteGate type is `aliyun`.

### Check requirements for your use case

**Certificate issuance and renewal alone have the fewest requirements.** With DDNS and ECH disabled, the provider only writes and cleans up DNS-01 TXT records; LiteGate's ACME client handles issuance. A, AAAA and HTTPS records are not required, and application IP addresses remain separately managed. Credentials, the authoritative zone and TXT propagation must still work. For simultaneous apex and wildcard challenges, confirm that multiple TXT values at one name are preserved. A certificate validation service is not necessarily a general DNS hosting service.

**DDNS adds A/AAAA management requirements.** The implementation must query records, append this node's IP and delete its old value precisely, while preserving other nodes' addresses. An API that only replaces a domain's single IP does not meet LiteGate's multi-node RRset contract. Repeated synchronization must be idempotent. Enable `sync_a` for IPv4 and keep `sync_aaaa: false` unless AAAA support is also confirmed.

**ECH adds HTTPS DNS record requirements.** The API, account permissions and selected libdns implementation must support HTTPS (type 65), read and write ECH parameters, and preserve unmanaged records during rotation and withdrawal. Ordinary HTTPS certificate issuance does not require these DNS records. Publication is only one part of ECH; see the [ECH guide](ech.md) for gateway, client and resolver requirements. ECH does not require DDNS: A/AAAA can be maintained manually.

A successful build, advertised plugin capabilities and a passing `-t` check do not establish that these operations work with a real account. Verify the functions you enable; TXT challenge support alone does not imply multi-node DDNS or ECH support.

## 2. Build the providers you need

The build machine needs Git, Go, and network access to the selected Go modules. Go must satisfy the requirements in LiteGate's and the providers' `go.mod` files. The deployment machine does not need Go.

```bash
# Short name resolves to github.com/libdns/huaweicloud
litegate build --dns huaweicloud -o litegate-custom

# Add multiple providers, including optional implementations using cloud SDKs
litegate build --dns huaweicloud --dns route53 -o litegate-custom

# Give the provider a custom YAML type
litegate build --dns hw=github.com/libdns/huaweicloud -o litegate-custom
```

On Windows, invoke `litegate.exe` and name the output `litegate-custom.exe`. Deploy and run the new binary.

Without a version, Go resolves the provider version. Once verified, inspect `litegate-custom plugins list` and append `@` followed by that module version to future `--dns` arguments. Rebuild selected providers when upgrading LiteGate. For local development, use `--replace <LiteGate-source-directory>`. Run `litegate build --help` for core version, replacement and other build options.

Built-in names are reserved. To include the libdns Cloudflare implementation, use `--dns libdns_cloudflare=cloudflare`; `type: cloudflare` continues to select the built-in implementation.

## 3. Configure certificates first and enable DDNS as needed

Here is a Huawei Cloud example. `type` identifies the compiled provider; `name` identifies this configuration entry for references such as ECH. If you built with `hw=...`, change `type` to `hw`.

```yaml
auto_cert:
  enabled: true
  email: admin@example.com
  dns_providers:
    - name: huawei-main
      type: huaweicloud
      enabled: true
      domains: ["example.com", "*.example.com"]
      config:
        access_key_id: "env://HW_AK"
        secret_access_key: "env://HW_SK"
        region_id: "cn-south-1"
        zone: "example.com"
        timeout: "2m"
        polling_interval: "10s"
```

Provide `HW_AK` and `HW_SK` in the running process's environment. These fields come from the [Huawei Cloud Provider](https://github.com/libdns/huaweicloud/blob/master/provider.go). Other providers require their own `Provider` JSON field names. Values are converted to the field types; complex fields accept inline JSON. Unknown fields are rejected.

The example enables certificate DNS-01 only and includes neither DDNS nor ECH. In an existing configuration, explicitly disable unwanted `ddns.enabled` and `ech.enabled` settings; removing one provider's DDNS block does not disable DDNS on other providers.

After confirming append and precise deletion support, add this block under the same provider entry, alongside `config`:

```yaml
ddns:
  enabled: true
  sync_a: true
  sync_aaaa: false
```

With DDNS enabled, `domains` matches loaded Site / Stream hosts; wildcard selectors do not create wildcard DNS records. See [DDNS](ddns.md) for synchronization behavior.

The adapter consumes `zone`, `ttl`, `timeout` and `polling_interval`. Host settings `secret_token`, `propagation_wait`, `skip_propagation_check`, `disable_complete_propagation` and `recursive_nameservers` are also kept out of provider decoding. When `zone` is omitted, SOA lookup discovers the authoritative zone. See [ECH](ech.md) for HTTPS publication, and check actual HTTPS support in your provider.

## 4. Verify and troubleshoot

```bash
./litegate-custom plugins list
./litegate-custom -config config.yaml -t
```

The provider should appear in `plugins list`. `-t` checks configuration, fields and advertised capabilities; it does not establish that remote credentials, permissions or DNS propagation work. After deployment, check certificate logs and verify TXT cleanup, A / AAAA synchronization or HTTPS publication in your DNS console.

| Problem | Check |
|---|---|
| Provider not found | Run the custom binary; match `type` to the build alias |
| libdns v0 API error | Select a provider targeting v1; upgrading core alone is insufficient |
| Unknown field | Check JSON names in the selected release; lego field names may differ |
| API authorization failure | Check credentials, region and record read/write permissions |
| Zone not found | Check the authoritative zone and set `zone` explicitly if needed |
| HTTPS operation failure | Check HTTPS support in the API and implementation |

If libdns has no implementation, write a custom DNS plugin. If only DNS-01 is needed and lego has an implementation, use the lego bridge example. See the [DNS Provider Plugin Authoring Guide](../../dns-provider-plugin-guide.md).
