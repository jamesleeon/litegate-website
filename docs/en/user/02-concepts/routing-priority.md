# Routing Priority

When multiple Routes are defined under a single domain name, LiteGate needs to determine which route matches the current inbound request best.

---

## 1. Core Principle: Longest Prefix First

LiteGate employs a standard **Longest Prefix Matching** strategy. This means that a route with a more specific (longer character string) path prefix has a higher priority.

### Example Scenario:
- **Route A**: `path_prefix: /`
- **Route B**: `path_prefix: /api`
- **Route C**: `path_prefix: /api/v1`

**Resolution Results**:
- A request to `/index.html` ➡️ Matches **Route A**.
- A request to `/api/status` ➡️ Matches **Route B** (which is more specific than A).
- A request to `/api/v1/user` ➡️ Matches **Route C** (which is more specific than B).

---

## 2. Order of Match Attempt (List Order)

If two routes have identical path prefixes, LiteGate attempts to match them in the **order they are declared** from top to bottom in the configuration file.

```yaml
routes:
  - name: first-match
    match: { path_prefix: "/data" }
    
  - name: second-match
    match: { path_prefix: "/data" } # This route will never match because it is intercepted above.
```

---

## 3. Multiple Filter Conflict Resolution

If a route uses multiple request filters (e.g., combining both `method` and `path_prefix`), the gateway prioritizes the route that satisfies all filter conditions.

---

## 4. Best Practice Tips

1.  **Hierarchical Definition**: Always place the most generic routes (like `/`) at the bottom of the configuration file.
2.  **Clear Actions**: Ensure the logic inside each route's Action is clear. Avoid errors caused by stripping path prefixes (`strip_prefix`).
3.  **Naming Convention**: Assign a meaningful `name` to each route. This is highly useful in observability logs and the Admin Dashboard.

---

## Next Steps
If you experience routes not taking effect as expected, please see: [Debugging Guide](../11-troubleshooting/debugging.md).
