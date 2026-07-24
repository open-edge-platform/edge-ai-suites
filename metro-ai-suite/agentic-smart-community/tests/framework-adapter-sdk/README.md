# framework-adapter-sdk tests

Unit tests for `@smartbuilding-video/framework-adapter-sdk` (`packages/framework-adapter-sdk`).

They run the real `SmartBuildingAdapter` against a **mock MCP server over a real Streamable-HTTP
transport** (`fixtures/mock-mcp-server.ts`), so the actual subscribe → SSE-notification → cursor-read
delivery path is exercised end-to-end — not a stubbed client.

## Run

```bash
npm -w @smartbuilding-video/framework-adapter-sdk run build   # tests import the built dist
npm run test:sdk                                              # node --import tsx --test
```

`test:sdk` uses Node's built-in test runner via `tsx` (no extra test-framework dependency).

## Coverage

| Test | Asserts |
|------|---------|
| seeds to latest on fresh start | history is **not** replayed; only post-seed alerts deliver |
| rapid burst (coalescing + debounce) | 5 rapid alerts → exactly 5 pushes, ascending id, no dupes |
| per-monitor order + isolation | interleaved cam_a/cam_b alerts stay ordered within each monitor |
| cursor persistence across restart | `FileCursorStore` resumes; no replay; alert missed while down is delivered |
| reconnect after disconnect | server drops connections → adapter reconnects/resubscribes → missed alert delivered |
| poll fallback | a silently-added alert (no notification) is recovered by `pollFallbackMs` |
| at-least-once on sink failure | a throwing push leaves the cursor un-advanced → the alert is replayed |

## Fixture hooks (`MockMcpServer`)

- `fireAlert(monitorId, partial?)` — append an alert **and** broadcast `notifications/resources/updated`
- `addAlertSilently(monitorId, partial?)` — append **without** notifying (lost-notification simulation)
- `dropConnections()` — force-close live transports (disconnect simulation)
- `alertCount(id)` / `subscriberCount()` — introspection for assertions
