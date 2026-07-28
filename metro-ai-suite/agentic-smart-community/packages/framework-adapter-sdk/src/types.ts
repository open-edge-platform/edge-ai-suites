import type { Alert } from "@smartbuilding-video/db";

/**
 * The one alert record delivered to a sink. `alert` is the DB row exactly as the MCP server
 * returns it from `resources/read` (reused verbatim from @smartbuilding-video/db — no reshaping).
 */
export interface AlertPayload {
  monitorId: string;
  alert: Alert;
}

/**
 * The single contract a framework implementer must satisfy.
 *
 * The SDK guarantees **at-least-once** delivery per alert id: on a mid-batch failure or a restart
 * before the cursor advances, the same alert may be pushed again. Sinks MUST be idempotent — key
 * off `alert.id` (globally unique per monitor) to suppress duplicates downstream.
 */
export interface AlertSink {
  push(payload: AlertPayload): Promise<void>;
}

/**
 * Persists the last successfully-delivered alert id per monitor (the delivery cursor / L2 dedup).
 * `get` returns null when no cursor exists yet (fresh monitor → SDK seeds to current latest,
 * skipping history). Implementations live in cursor.ts.
 */
export interface CursorStore {
  get(monitorId: string): Promise<number | null>;
  set(monitorId: string, alertId: number): Promise<void>;
}

/** Minimal logger surface — compatible with console and most framework loggers (e.g. OpenClaw's). */
export interface Logger {
  debug(msg: string): void;
  info(msg: string): void;
  warn(msg: string): void;
  error(msg: string): void;
}

/** Exponential-backoff reconnect tuning. Defaults: initialMs 1000, maxMs 30000, factor 2. */
export interface ReconnectConfig {
  initialMs?: number;
  maxMs?: number;
  factor?: number;
}

export type TransportConfig =
  | { kind: "http"; url: string; headers?: Record<string, string> }
  | { kind: "stdio"; command: string; args?: string[] };

export interface AdapterConfig {
  transport: TransportConfig;
  /** Monitor ids to subscribe to. Each maps to `smartbuilding://monitor/<id>/alerts`. */
  monitorIds: string[];
  reconnect?: ReconnectConfig;
  /** Omit for in-memory cursors (a restart replays the current day from the seed point). */
  cursorStore?: CursorStore;
  /**
   * Low-frequency safety-net poll (ms) guarding against a permanently-lost notification.
   * Default 0 = disabled. Set a positive value (e.g. 60000) to re-read each uri on an interval.
   */
  pollFallbackMs?: number;
  logger?: Logger;
}
