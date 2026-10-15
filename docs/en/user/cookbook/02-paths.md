# Paths: matching and rewriting

Routes select a branch from the original path before rewrite. Rewriting neither reroutes nor changes the browser URL; redirects produce client-visible moves.

Use Go expressions and explicit captures to adapt backend paths; query fields handle query parameters separately. Configure prefixes, exact paths, wildcard conditions and precedence through the V2 guide rather than relying only on file order.

## Related documentation and code

- [Rewrite example](../03-configuration/rewrite.md)
- [Matchers](06-matchers.md)
- [Priority](../02-concepts/routing-priority.md)
