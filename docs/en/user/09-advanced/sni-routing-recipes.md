# SNI routing recipes

SNI selects an L4 path during the TLS handshake and cannot inspect HTTP paths. Path/Header/Query routing requires TLS termination followed by L7 routing. Use attached streams for shared-port 443 recipes.

In passthrough mode the upstream owns certificates, ALPN and HTTPS. With termination, LiteGate owns certificates and forwards decrypted bytes to a protocol-compatible backend. Do not treat a TLS upstream as a plaintext service. Database/custom TCP clients must be able to send the expected SNI.

During migration, verify SNI matching, non-TLS/missing-SNI policy, upstream TLS, PROXY Protocol and idle timeouts individually. Validate exact/wildcard domains and conflicts through the current loader; do not infer LiteGate ordering from another project's configuration.

## Related documentation and code

- [Shared 443 example](shared-443-l4-stream.md)
- [L4 configuration](../03-configuration/l4-guide.md)
- [Entrypoints](../03-configuration/entrypoints.md)
