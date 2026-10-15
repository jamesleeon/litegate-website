# Shared port 443: HTTPS and L4 streams

TCP/443 can dispatch TLS ClientHello SNI to an L4 stream or ordinary HTTPS through one listener. Unmatched connections continue to HTTPS, and inspected bytes are replayed. HTTP/3 uses a separate UDP listener and does not participate in TCP SNI routing.

Attach a stream using listen: false, entrypoints and hostnames instead of binding the same port separately. Either pass TLS through unchanged or terminate it in LiteGate before reaching TCP/Unix Socket upstreams. TLS termination requires valid certificates; Unix Socket targets require static absolute paths.

Explicitly configure handling of non-TLS traffic and missing SNI. Check domain conflicts, certificate coverage, backend protocols and permissions. Test HTTPS and streams together, then verify hot updates and fallback after stream removal.

```yaml
entrypoints:
  websecure:
    address: ':443'
    tls: true
    default: http
    on_non_tls: reject
    on_no_sni: reject
```

```yaml
name: database
listen: false
entrypoints: [websecure]
hostnames: [db.example.com]
protocol: tcp
upstream: unix:///run/litegate/database.sock
enabled: true
tls:
  enabled: true
  auto_cert: true
  min_version: '1.2'
```

## Related documentation and code

- [Entrypoints](../03-configuration/entrypoints.md)
- [Stream guide](../03-configuration/stream-config.md)
