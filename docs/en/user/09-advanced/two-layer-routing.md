# Selecting upstreams and rewriting paths

Separate route selection from URL adaptation: the original request matches a Site/Route and selects its Action/Service; rewrite then changes the path/query sent to that upstream. Rewriting does not select another route.

For example, select tenant-a using Host, Path, Header or Query, then change /legacy/orders to /api/orders. When routing depends on business identity, let an IDS Provider return a Selector. Meta expresses a version preference within the isolated pool.

Debug in order: original request, matched route, Service/Selector, rewrite result and actual destination. Do not use rewriting to simulate route jumps; use redirect when the browser should change its URL.

## Related documentation and code

- [Rewrite](../03-configuration/rewrite.md)
- [IDS](../05-middleware/ids-governance.md)
- [Routing priority](../02-concepts/routing-priority.md)
