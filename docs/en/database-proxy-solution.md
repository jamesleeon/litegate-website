# Accessing database TCP assets

Cloud-private databases can use Forward Sites/Streams to provide controlled tunnels to token-holding clients, or Connect to publish streams inside Private. The gateway transports TCP; it does not parse SQL or replace database accounts/permissions.

A local client listener maps to an authorized destination and database tools connect to that local port. Restrict destination allowlists, Peers/tokens and entrypoints. Databases still need account/network policies and encryption. Do not send raw database protocols directly to HTTPS or expose unrestricted SOCKS/forward proxies.

Use the current Stream/Forward guide for multiple mappings, --target, auto/v3/v2 transport and TLS settings. Do not infer defaults/negotiation from historical single-target proposals. For RDS, verify Cloud-to-RDS networking, accounts, ports and idle timeouts.

## Related documentation and code

- [Forward configuration](user/03-configuration/stream-config.md)
- [Forward / Connect](user/09-advanced/forward-and-connect.md)
- [Connect](user/09-advanced/connect.md)
