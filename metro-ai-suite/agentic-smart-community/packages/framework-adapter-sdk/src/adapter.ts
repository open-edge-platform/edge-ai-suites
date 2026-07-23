import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import {
  ResourceUpdatedNotificationSchema,
  type ResourceUpdatedNotification,
} from "@modelcontextprotocol/sdk/types.js";
import type { Alert } from "@smartbuilding-video/db";
import { MemoryCursorStore } from "./cursor.js";
import type {
  AdapterConfig,
  AlertSink,
  CursorStore,
  Logger,
} from "./types.js";

const CLIENT_NAME = "smartbuilding-framework-adapter";
const CLIENT_VERSION = "0.1.0";

const DEFAULT_RECONNECT = { initialMs: 1000, maxMs: 30000, factor: 2 } as const;

/** `smartbuilding://monitor/<id>/alerts` — the alerts resource uri for a monitor. */
function alertsUri(monitorId: string): string {
  return `smartbuilding://monitor/${monitorId}/alerts`;
}

/** Extract the monitor id from an alerts uri, or null if it isn't one. */
function monitorIdFromUri(uri: string): string | null {
  const m = /^smartbuilding:\/\/monitor\/([^/]+)\/alerts(?:\?.*)?$/.exec(uri);
  return m ? m[1] : null;
}

/** Shape of the JSON `resources/read` returns for the alerts resource (see resources.ts). */
interface AlertsReadResult {
  latestId: number;
  alerts: Alert[];
}

/**
 * Generic MCP client that subscribes to per-monitor alert resources and drives an {@link AlertSink}.
 *
 * Guarantees, per the subscription design:
 * - **at-least-once** delivery keyed on `alert.id` (sink must be idempotent);
 * - **per-monitor ordering** — a monitor's reads + pushes are serialized through a mutex, and alerts
 *   are pushed strictly in ascending id order; cross-monitor order is not guaranteed (by design);
 * - **no history replay** on a fresh cursor — the first sync seeds the cursor to the current latest;
 * - **resume across restarts** when a persistent {@link CursorStore} is supplied — missed alerts are
 *   read and delivered on the next sync;
 * - **self-heals on id regression** — if the source db is recreated and alert ids restart lower, a
 *   persisted cursor stranded in the future is detected and reset down (so it can't swallow alerts).
 */
export class SmartBuildingAdapter {
  private readonly monitorIds: string[];
  private readonly cursorStore: CursorStore;
  private readonly pollFallbackMs: number;
  private readonly reconnectCfg: { initialMs: number; maxMs: number; factor: number };
  private readonly log: Logger;

  private client: Client | null = null;
  private stopped = false;
  /** True from the moment a disconnect is detected until a reconnect succeeds — dedupes the
   * onclose/onerror pair and prevents overlapping reconnect loops. */
  private reconnecting = false;
  /** Bumped on every (re)connect and on stop; stale transport handlers compare against it. */
  private generation = 0;
  private currentBackoff: number;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pollTimer: ReturnType<typeof setInterval> | null = null;
  /** Per-monitor serialization: monitorId → tail of its work chain. */
  private readonly locks = new Map<string, Promise<void>>();

  constructor(private readonly config: AdapterConfig, private readonly sink: AlertSink) {
    this.monitorIds = [...config.monitorIds];
    this.cursorStore = config.cursorStore ?? new MemoryCursorStore();
    this.pollFallbackMs = config.pollFallbackMs ?? 0;
    this.reconnectCfg = {
      initialMs: config.reconnect?.initialMs ?? DEFAULT_RECONNECT.initialMs,
      maxMs: config.reconnect?.maxMs ?? DEFAULT_RECONNECT.maxMs,
      factor: config.reconnect?.factor ?? DEFAULT_RECONNECT.factor,
    };
    this.currentBackoff = this.reconnectCfg.initialMs;
    this.log = config.logger ?? console;
  }

  /** Connect, subscribe to every monitor, seed/resume cursors, and start the optional poll timer. */
  async start(): Promise<void> {
    this.stopped = false;
    await this.connect();
    this.startPollTimer();
  }

  /** Stop the poll + reconnect timers, unsubscribe, and close the transport. Best-effort, idempotent. */
  async stop(): Promise<void> {
    this.stopped = true;
    this.reconnecting = false;
    this.generation++; // invalidate any in-flight transport handlers
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
    const client = this.client;
    this.client = null;
    if (client) {
      for (const monitorId of this.monitorIds) {
        try {
          await client.unsubscribeResource({ uri: alertsUri(monitorId) });
        } catch {
          /* best effort — the transport may already be gone */
        }
      }
      try {
        await client.close();
      } catch {
        /* best effort */
      }
    }
  }

  // ── connection ───────────────────────────────────────────────────────────

  private createTransport() {
    const t = this.config.transport;
    if (t.kind === "http") {
      const opts = t.headers ? { requestInit: { headers: t.headers } } : undefined;
      return new StreamableHTTPClientTransport(new URL(t.url), opts);
    }
    return new StdioClientTransport({ command: t.command, args: t.args });
  }

  private async connect(): Promise<void> {
    const transport = this.createTransport();
    const client = new Client({ name: CLIENT_NAME, version: CLIENT_VERSION }, { capabilities: {} });
    const gen = ++this.generation;

    client.setNotificationHandler(ResourceUpdatedNotificationSchema, (n) => this.onNotification(n));
    client.onclose = () => {
      if (gen === this.generation) this.handleDisconnect("closed");
    };
    client.onerror = (err) => {
      if (gen !== this.generation) return;
      // The transport surfaces fatal errors here (e.g. "Maximum reconnection attempts exceeded"
      // once its own SSE retries are spent). Treat any transport-level error as a disconnect and
      // rebuild the session — connect + resubscribe + cursor-based resync is idempotent.
      this.log.warn(`[adapter] client error: ${err.message}`);
      this.handleDisconnect("error");
    };

    await client.connect(transport);
    this.client = client;
    this.reconnecting = false;
    this.currentBackoff = this.reconnectCfg.initialMs; // reset backoff after a good connect

    // Subscribe BEFORE the first read so a notification produced during startup is not lost —
    // the cursor dedups any overlap between the subscription and the seed read.
    for (const monitorId of this.monitorIds) {
      await client.subscribeResource({ uri: alertsUri(monitorId) });
    }
    for (const monitorId of this.monitorIds) {
      await this.runExclusive(monitorId, () => this.syncMonitor(monitorId)).catch((err) =>
        this.log.warn(`[adapter] initial sync ${monitorId} failed: ${err.message}`),
      );
    }
    this.log.info(`[adapter] connected, subscribed to ${this.monitorIds.length} monitor(s)`);
  }

  private handleDisconnect(reason: string): void {
    if (this.stopped || this.reconnecting) return;
    this.reconnecting = true;
    this.client = null;
    this.log.warn(`[adapter] transport ${reason}; reconnecting in ${this.currentBackoff}ms`);
    this.scheduleReconnect();
  }

  private scheduleReconnect(): void {
    if (this.stopped) {
      this.reconnecting = false;
      return;
    }
    if (this.reconnectTimer) return;
    const delay = this.currentBackoff;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      // connect() clears `reconnecting` and resets backoff on success.
      this.connect().catch((err) => {
        this.log.warn(`[adapter] reconnect failed: ${err.message}`);
        this.currentBackoff = Math.min(
          this.currentBackoff * this.reconnectCfg.factor,
          this.reconnectCfg.maxMs,
        );
        this.scheduleReconnect();
      });
    }, delay);
    if (typeof this.reconnectTimer.unref === "function") this.reconnectTimer.unref();
  }

  // ── notification + poll → sync ─────────────────────────────────────────────

  private onNotification(n: ResourceUpdatedNotification): void {
    const uri = n.params.uri;
    const monitorId = monitorIdFromUri(uri);
    if (!monitorId || !this.monitorIds.includes(monitorId)) {
      this.log.debug(`[adapter] ignoring notification for unsubscribed uri=${uri}`);
      return;
    }
    void this.runExclusive(monitorId, () => this.syncMonitor(monitorId)).catch((err) =>
      this.log.warn(`[adapter] sync ${monitorId} failed: ${err.message}`),
    );
  }

  private startPollTimer(): void {
    if (this.pollFallbackMs <= 0 || this.pollTimer) return;
    this.pollTimer = setInterval(() => {
      if (!this.client) return; // don't poll while disconnected
      for (const monitorId of this.monitorIds) {
        void this.runExclusive(monitorId, () => this.syncMonitor(monitorId)).catch((err) =>
          this.log.warn(`[adapter] poll sync ${monitorId} failed: ${err.message}`),
        );
      }
    }, this.pollFallbackMs);
    if (typeof this.pollTimer.unref === "function") this.pollTimer.unref();
  }

  // ── the one delivery path (seed / resume / incremental) ────────────────────

  /**
   * Read new alerts for a monitor and push them. Runs under the monitor's mutex.
   *
   * - cursor === null (never seeded, no persisted value): seed to the current latest and push
   *   nothing — this is a fresh start, we skip history.
   * - cursor !== null: check for id regression, then read `?since=cursor`, push each alert with
   *   id > cursor in ascending order, and advance the cursor to latestId only after every push
   *   resolves (atomic advance; a mid-batch failure leaves the cursor put so the whole batch
   *   replays next time).
   *
   * Id-regression guard (matters mainly for a persistent {@link FileCursorStore}): the true current
   * max id comes from a base read — the `?since` endpoint echoes `since` back when there's no delta,
   * so it can't reveal that the source ids reset. If the true latest is *below* our cursor, the
   * source db was recreated and our cursor is stranded in the future (it would silently swallow every
   * new alert); we reset the cursor down to the new latest and warn.
   */
  private async syncMonitor(monitorId: string): Promise<void> {
    if (!this.client) return;
    const cursor = await this.cursorStore.get(monitorId);

    if (cursor === null) {
      const { latestId } = await this.readAlerts(monitorId);
      await this.cursorStore.set(monitorId, latestId);
      this.log.debug(`[adapter] ${monitorId} seeded cursor at ${latestId}`);
      return;
    }

    // Ground-truth max id (base read — see the id-regression note above).
    const { latestId: trueLatest } = await this.readAlerts(monitorId);

    if (trueLatest < cursor) {
      this.log.warn(
        `[adapter] ${monitorId} latest alert id ${trueLatest} < cursor ${cursor} — id regression ` +
          `(source db reset?); resetting cursor to ${trueLatest}`,
      );
      await this.cursorStore.set(monitorId, trueLatest);
      return;
    }
    if (trueLatest === cursor) return; // nothing new — skip the delta read

    const { latestId, alerts } = await this.readAlerts(monitorId, cursor);
    const fresh = alerts.filter((a) => a.id > cursor).sort((a, b) => a.id - b.id);
    for (const alert of fresh) {
      await this.sink.push({ monitorId, alert });
    }
    if (latestId > cursor) {
      await this.cursorStore.set(monitorId, latestId);
    }
    if (fresh.length > 0) {
      this.log.debug(`[adapter] ${monitorId} delivered ${fresh.length} alert(s), cursor → ${latestId}`);
    }
  }

  private async readAlerts(monitorId: string, since?: number): Promise<AlertsReadResult> {
    const uri = since === undefined ? alertsUri(monitorId) : `${alertsUri(monitorId)}?since=${since}`;
    const res = await this.client!.readResource({ uri });
    const first = res.contents?.[0] as { text?: string } | undefined;
    const parsed = JSON.parse(first?.text ?? "{}") as Partial<AlertsReadResult>;
    return {
      latestId: parsed.latestId ?? since ?? 0,
      alerts: parsed.alerts ?? [],
    };
  }

  // ── per-monitor mutex ──────────────────────────────────────────────────────

  /** Chain `fn` behind any pending work for this monitor so same-monitor syncs never overlap. */
  private runExclusive(monitorId: string, fn: () => Promise<void>): Promise<void> {
    const prev = this.locks.get(monitorId) ?? Promise.resolve();
    const next = prev.then(fn, fn); // run regardless of whether the previous task rejected
    // Keep the chain alive even if `next` rejects, but let the caller observe the rejection.
    this.locks.set(monitorId, next.then(
      () => undefined,
      () => undefined,
    ));
    return next;
  }
}
