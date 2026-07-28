/**
 * Minimal, self-contained mock of the SmartBuilding MCP server for exercising the
 * framework-adapter-sdk over a real Streamable-HTTP transport.
 *
 * It reproduces exactly the wire contract the SDK depends on (see packages/mcp-server/src/
 * resources.ts + index.ts):
 *   - stateful HTTP: one McpServer + transport per `mcp-session-id`
 *   - resources `smartbuilding://monitor/{id}/alerts` and `...alerts{?since}` returning
 *     `{ monitorId, latestId, alerts }`
 *   - `resources/subscribe` / `unsubscribe` tracked per session
 *   - `sendResourceUpdated({ uri })` broadcast to subscribers
 *
 * Test hooks (not part of the real server):
 *   - fireAlert(monitorId, partial)      → append alert + broadcast notification
 *   - addAlertSilently(monitorId, partial)→ append alert WITHOUT notification (lost-notification sim)
 *   - dropConnections()                  → close all live transports (disconnect sim)
 *   - alertCount(monitorId)              → introspection for assertions
 */
import { createServer, type Server } from "node:http";
import { randomUUID } from "node:crypto";
import { AddressInfo } from "node:net";
import { McpServer, ResourceTemplate } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { createMcpExpressApp } from "@modelcontextprotocol/sdk/server/express.js";
import {
  SubscribeRequestSchema,
  UnsubscribeRequestSchema,
  isInitializeRequest,
} from "@modelcontextprotocol/sdk/types.js";

export interface MockAlert {
  id: number;
  monitorId: string;
  useCase: string;
  description?: string;
  createdAt: string;
  [key: string]: unknown;
}

interface SessionEntry {
  server: McpServer;
  transport: StreamableHTTPServerTransport;
  subscriptions: Set<string>;
}

function alertsUri(monitorId: string): string {
  return `smartbuilding://monitor/${monitorId}/alerts`;
}

export class MockMcpServer {
  private http: Server | null = null;
  private readonly sessions = new Map<string, SessionEntry>();
  /** monitorId → alerts (ascending id). */
  private readonly alerts = new Map<string, MockAlert[]>();
  private nextId = 1;
  /** Fixed timestamp source — new Date() is fine in tests (unlike workflow scripts). */
  private clock = 0;

  async start(): Promise<string> {
    const app = createMcpExpressApp();

    app.all("/mcp", async (req, res) => {
      const providedSid = req.headers["mcp-session-id"] as string | undefined;
      const entry = providedSid ? this.sessions.get(providedSid) : undefined;

      try {
        if (!entry) {
          // Unknown/expired session id, or a first request that isn't `initialize`: reject with
          // 404 (mirrors a real server after a session is dropped). This makes the client's SSE
          // auto-retry fail and surface the error once its retries are exhausted — which is what
          // drives the adapter's own reconnect path.
          if (providedSid || !isInitializeRequest(req.body)) {
            if (!res.headersSent) {
              res.status(404).json({
                jsonrpc: "2.0",
                error: { code: -32001, message: "Session not found" },
                id: null,
              });
            }
            return;
          }
          const transport = new StreamableHTTPServerTransport({
            sessionIdGenerator: () => randomUUID(),
            onsessioninitialized: (sid: string) => {
              this.sessions.set(sid, { server, transport, subscriptions: new Set() });
            },
          });
          const server = this.buildServer(() => transport.sessionId ?? "__pending__");
          transport.onclose = () => {
            const sid = transport.sessionId;
            if (sid) this.sessions.delete(sid);
          };
          await server.connect(transport);
          await transport.handleRequest(req, res, req.body);
          return;
        }
        await entry.transport.handleRequest(req, res, req.body);
      } catch (err) {
        if (!res.headersSent) {
          res.status(500).json({
            jsonrpc: "2.0",
            error: { code: -32603, message: String(err) },
            id: null,
          });
        }
      }
    });

    this.http = createServer(app);
    await new Promise<void>((resolve) => this.http!.listen(0, "127.0.0.1", resolve));
    const port = (this.http!.address() as AddressInfo).port;
    return `http://127.0.0.1:${port}/mcp`;
  }

  async stop(): Promise<void> {
    for (const { transport } of this.sessions.values()) {
      try {
        await transport.close();
      } catch {
        /* ignore */
      }
    }
    this.sessions.clear();
    if (this.http) {
      await new Promise<void>((resolve) => this.http!.close(() => resolve()));
      this.http = null;
    }
  }

  private buildServer(getSessionId: () => string): McpServer {
    const server = new McpServer({ name: "mock-smartbuilding", version: "0.0.1" });

    // ?since= variant registered first (matches real resources.ts ordering).
    server.registerResource(
      "monitor-alerts-since",
      new ResourceTemplate("smartbuilding://monitor/{id}/alerts{?since}", { list: undefined }),
      { description: "alerts since cursor" },
      async (uri, variables) => {
        const id = variables.id as string;
        const since = Number(variables.since);
        const all = this.alerts.get(id) ?? [];
        const filtered = all.filter((a) => a.id > since);
        const latestId = filtered.length > 0 ? Math.max(...filtered.map((a) => a.id)) : since;
        return this.jsonContents(uri.href, id, latestId, filtered);
      },
    );

    server.registerResource(
      "monitor-alerts",
      new ResourceTemplate("smartbuilding://monitor/{id}/alerts", { list: undefined }),
      { description: "recent alerts" },
      async (uri, variables) => {
        const id = variables.id as string;
        const all = this.alerts.get(id) ?? [];
        const latestId = all.length > 0 ? all[all.length - 1].id : 0;
        return this.jsonContents(uri.href, id, latestId, all.slice(-20));
      },
    );

    // Subscribe capability + handlers wired to per-session subscription set.
    server.server.registerCapabilities({ resources: { subscribe: true } });
    server.server.setRequestHandler(SubscribeRequestSchema, async (request) => {
      const sid = getSessionId();
      this.sessions.get(sid)?.subscriptions.add(request.params.uri);
      return {};
    });
    server.server.setRequestHandler(UnsubscribeRequestSchema, async (request) => {
      const sid = getSessionId();
      this.sessions.get(sid)?.subscriptions.delete(request.params.uri);
      return {};
    });

    return server;
  }

  private jsonContents(href: string, monitorId: string, latestId: number, alerts: MockAlert[]) {
    return {
      contents: [
        {
          uri: href,
          mimeType: "application/json",
          text: JSON.stringify({ monitorId, latestId, alerts }),
        },
      ],
    };
  }

  // ── test hooks ──────────────────────────────────────────────────────────

  /** Append an alert and broadcast a resource-updated notification to subscribers. */
  fireAlert(monitorId: string, partial: Partial<MockAlert> = {}): MockAlert {
    const alert = this.append(monitorId, partial);
    this.broadcast(alertsUri(monitorId));
    return alert;
  }

  /** Append an alert but DO NOT notify — simulates a lost notification (poll-fallback test). */
  addAlertSilently(monitorId: string, partial: Partial<MockAlert> = {}): MockAlert {
    return this.append(monitorId, partial);
  }

  /** Force-close every live transport, simulating a server-side disconnect. */
  async dropConnections(): Promise<void> {
    const entries = [...this.sessions.values()];
    this.sessions.clear();
    for (const { transport } of entries) {
      try {
        await transport.close();
      } catch {
        /* ignore */
      }
    }
  }

  alertCount(monitorId: string): number {
    return (this.alerts.get(monitorId) ?? []).length;
  }

  subscriberCount(): number {
    let n = 0;
    for (const s of this.sessions.values()) n += s.subscriptions.size;
    return n;
  }

  private append(monitorId: string, partial: Partial<MockAlert>): MockAlert {
    const alert: MockAlert = {
      id: this.nextId++,
      monitorId,
      useCase: partial.useCase ?? "test",
      description: partial.description ?? `alert ${this.nextId - 1}`,
      createdAt: partial.createdAt ?? new Date(1_700_000_000_000 + this.clock++ * 1000).toISOString(),
      ...partial,
    };
    const list = this.alerts.get(monitorId) ?? [];
    list.push(alert);
    this.alerts.set(monitorId, list);
    return alert;
  }

  private broadcast(uri: string): void {
    for (const { server, subscriptions } of this.sessions.values()) {
      if (subscriptions.has(uri)) {
        server.server.sendResourceUpdated({ uri }).catch(() => {});
      }
    }
  }
}
