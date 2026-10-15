# Forward and Connect

Forward maps TCP assets reachable from Cloud to token-holding clients. Connect publishes Private/Home websites or TCP streams through a public Cloud entry. Both establish outbound TLS connections from the inner side, but application traffic flows in different directions.

| Scenario | Choice |
|---|---|
| Local database tools accessing cloud RDS/Redis/SSH | Forward client and Cloud Forward Site |
| Publishing an internal HTTPS site without a public IP | Connect Cloud and Private/Home |
| Accessing TCP assets inside Home | Combine Forward and Connect as needed |
| Whole-network connectivity or arbitrary UDP | Neither should be treated as a general VPN |

The Forward tunnel is distinct from the browser HTTP forward proxy provided by forward_proxy. See the Stream guide for single/multiple mappings, tokens, destination allowlists and transports. Connect Cloud performs SNI/L4 delivery; full Site mode terminates TLS and runs L7 middleware on Private. The simplified HTTP CLI mode has separate restrictions.

Using port 443 for a database still requires an appropriate tunnel client or TLS wrapper; do not send a raw plaintext database connection to HTTPS.

## Related documentation and code

- [Stream / Forward](../03-configuration/stream-config.md)
- [Connect](connect.md)
- [CLI HTTP](connect-cli-http.md)
- [Forward proxy](../../forward-vs-forward-proxy.md)
