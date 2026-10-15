# Connect scenarios and deployment responsibilities

Connect publishes internal websites through Cloud: Private opens outbound connections, Cloud accepts public SNI traffic and delivers it to Private, and Private handles full Site TLS, authentication and application proxying. Use distinct Peers and explicit domain authorization for branches.

Browsers need no tunnel client. Non-HTTP assets such as databases require streams and protocol-compatible clients. Cloud authorization, Private domain claims, certificate readiness and backend reachability must all hold. CSR delegation avoids concentrating DNS credentials and Private keys on Cloud.

For availability, test connection recovery and node failure with the current configuration instead of treating historical N×M proposals as shipped guarantees. Check public DNS, port 443, Peer credentials, domain conflicts, pending certificates and the application's own authorization.

## Related documentation and code

- [Connect](connect.md)
- [CLI HTTP](connect-cli-http.md)
- [CSR delegation](../06-certificates/connect-csr-delegation.md)
