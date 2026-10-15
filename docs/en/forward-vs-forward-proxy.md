# Forward tunnels and HTTP forward proxies

Forward is a tunnel for LiteGate clients to reach authorized TCP assets. HTTP forward_proxy is an ingress plugin for browsers/tools accessing HTTP/HTTPS destinations through a proxy. Their protocols and authorization differ.

Forward destinations are constrained by server mappings and allowlists, fitting databases/SSH. HTTP forward proxies handle absolute URLs or CONNECT and use standard client proxy settings. Both require authentication, destination constraints and logging; similar names do not imply shared configuration.

HTTP forward proxies are not general UDP VPNs, and browser proxy settings do not replace a dedicated Forward tunnel client. Follow the separate guides and test rejection of unauthorized targets.

## Related documentation and code

- [Forward tunnel](user/03-configuration/stream-config.md)
- [Forward proxy example](../../examples/plugins/ingress/forwardproxy/README.md)
- [Ingress plugin](ingress-plugin-guide.md)
