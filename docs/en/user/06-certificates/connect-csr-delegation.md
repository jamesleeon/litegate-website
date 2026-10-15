# Connect CSR certificate delegation

The Private node generates its key and CSR locally, then asks Cloud to perform DNS-01 through an authenticated Connect channel. Cloud returns only the certificate chain; the Private key stays local. Private validates the certificate against the CSR key, domains and chain before storage/use. Cloud does not need Private's storage key.

Enable auto_cert and a DNS Provider on Cloud and configure allowed_cert_domains for the Peer. Private uses a Connect client and local certificate storage. Domains must belong to that Peer's current exact claims. Wildcards, reserved names, conflicts with Cloud-local sites, mismatched CSRs and changed ownership are rejected. Cooldown and issuance budgets also apply.

auto_cert.storage_secret can protect stored private keys through a secure reference, but cannot protect a fully compromised host. Unready certificates retain pending_certificate publication state; this is not an unconditional zero-loss promise. Test first issuance, renewal, Peer revocation, domain transfer and DNS-permission failures. External CA quotas depend on the service and do not justify a fixed tenant-capacity promise.

## Related documentation and code

- [Connect configuration](../09-advanced/connect.md)
- [Certificate methods](certificate-application-guide.md)
- [Implementation](../../../../internal/connect)
