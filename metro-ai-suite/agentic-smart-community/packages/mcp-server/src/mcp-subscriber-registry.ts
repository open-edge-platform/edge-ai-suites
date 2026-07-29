import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import type { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";

/**
 * Tracks per-MCP-session subscription state so `onAlert(monitorId)` can broadcast
 * `notifications/resources/updated` to every session that subscribed to the relevant uri.
 *
 * "Session" here means an MCP protocol session (client↔server connection with a stateful
 * sessionId), NOT an OpenClaw agent chat session. The name uses "Subscriber" to sidestep
 * that ambiguity.
 *
 * Stateful HTTP transport allocates a fresh sessionId per client; stdio has a single
 * long-lived server which we register with a fixed sessionId ("stdio") so the broadcast
 * loop is uniform across both transports.
 */
export interface SubscriberEntry {
  server: McpServer;
  transport: StreamableHTTPServerTransport | null;   // null for stdio
  subscriptions: Set<string>;                        // uris this session subscribed to
  lastSeen: number;                                  // ms epoch of the last HTTP request for this session
  openSseCount: number;                              // number of currently-open GET SSE streams
}

export class McpSubscriberRegistry {
  private sessions = new Map<string, SubscriberEntry>();

  register(sessionId: string, entry: SubscriberEntry): void {
    this.sessions.set(sessionId, entry);
  }

  unregister(sessionId: string): void {
    this.sessions.delete(sessionId);
  }

  get(sessionId: string): SubscriberEntry | undefined {
    return this.sessions.get(sessionId);
  }

  addSubscription(sessionId: string, uri: string): void {
    const entry = this.sessions.get(sessionId);
    if (!entry) return;
    entry.subscriptions.add(uri);
  }

  removeSubscription(sessionId: string, uri: string): void {
    const entry = this.sessions.get(sessionId);
    if (!entry) return;
    entry.subscriptions.delete(uri);
  }

  /** All sessions subscribed to `uri`. Empty array when nobody's listening. */
  findSubscribers(uri: string): SubscriberEntry[] {
    const out: SubscriberEntry[] = [];
    for (const entry of this.sessions.values()) {
      if (entry.subscriptions.has(uri)) out.push(entry);
    }
    return out;
  }

  /** Mark that a request arrived for this session (refreshes the idle clock). */
  touch(sessionId: string): void {
    const entry = this.sessions.get(sessionId);
    if (entry) entry.lastSeen = Date.now();
  }

  /** A GET SSE stream opened for this session — it's now active regardless of request cadence. */
  sseOpened(sessionId: string): void {
    const entry = this.sessions.get(sessionId);
    if (!entry) return;
    entry.openSseCount++;
    entry.lastSeen = Date.now();
  }

  /** A GET SSE stream closed for this session. */
  sseClosed(sessionId: string): void {
    const entry = this.sessions.get(sessionId);
    if (!entry) return;
    entry.openSseCount = Math.max(0, entry.openSseCount - 1);
    entry.lastSeen = Date.now();
  }

  /**
   * Sessions eligible for idle eviction: an HTTP session (transport !== null) with NO open SSE
   * stream that has been idle longer than `ttlMs`. stdio (transport === null) is always exempt —
   * it's the process-resident singleton and must never be swept.
   */
  findIdle(now: number, ttlMs: number): { sessionId: string; entry: SubscriberEntry }[] {
    const out: { sessionId: string; entry: SubscriberEntry }[] = [];
    for (const [sessionId, entry] of this.sessions) {
      if (entry.transport === null) continue;   // stdio: never sweep
      if (entry.openSseCount > 0) continue;      // active SSE: exempt
      if (now - entry.lastSeen > ttlMs) out.push({ sessionId, entry });
    }
    return out;
  }

  size(): number {
    return this.sessions.size;
  }
}
