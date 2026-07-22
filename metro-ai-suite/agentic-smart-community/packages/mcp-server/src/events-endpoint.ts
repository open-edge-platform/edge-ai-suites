import { createServer, type IncomingMessage, type ServerResponse, type Server } from "node:http";
import type { SmartBuildingDB } from "@smartbuilding-video/db";
import { logger } from "./logger.js";

export interface VideoEvent {
  sourceId: string;
  type: "motion" | "static" | "recording";
  timestamp: string;
  payload: Record<string, unknown>;
}

export type EventCallback = (event: VideoEvent) => void;

export interface EventsEndpointOptions {
  /** Max accepted request body size, in bytes. Default 1 MiB. */
  maxBodyBytes?: number;
}

const DEFAULT_MAX_BODY_BYTES = 1024 * 1024;
const KNOWN_TYPES = new Set<VideoEvent["type"]>(["motion", "static", "recording"]);

type DispatchOutcome =
  | { kind: "ok"; body: Record<string, unknown> }
  | { kind: "missing_required_fields"; missing: string[] }
  | { kind: "unknown_event_type"; type: string };

/**
 * HTTP webhook receiver for events pushed by any upstream video-analytics client.
 * Listens on a dedicated port for POST /events.
 *
 * Response contract is documented in docs/apis/mcp_webhook_event_api.md.
 * Summary:
 *   200 — DB write succeeded; body carries inserted row ids
 *   400 — body not JSON, or envelope shape invalid (transport / framing error)
 *   404 — unknown path
 *   405 — wrong method on known path; sets Allow header
 *   413 — body exceeds maxBodyBytes
 *   415 — Content-Type is not application/json
 *   422 — envelope OK but unprocessable: unknown event type, or required payload fields missing
 *   500 — DB INSERT threw an unexpected exception
 */
export class EventsEndpoint {
  private server: Server | null = null;
  private db: SmartBuildingDB;
  private onEvent?: EventCallback;
  private maxBodyBytes: number;

  /**
   * @param db DB the handler writes events / video_summary_tasks / recordings into.
   * @param onEvent Optional hook fired after every successfully handled webhook.
   * @param options Optional behavior knobs (max body size, …).
   */
  constructor(db: SmartBuildingDB, onEvent?: EventCallback, options?: EventsEndpointOptions) {
    this.db = db;
    this.onEvent = onEvent;
    this.maxBodyBytes = options?.maxBodyBytes ?? DEFAULT_MAX_BODY_BYTES;
  }

  start(port: number = 3101): Promise<void> {
    return new Promise((resolve, reject) => {
      this.server = createServer((req, res) => this.route(req, res));

      this.server.on("error", (err: NodeJS.ErrnoException) => {
        if (err.code === "EADDRINUSE") {
          logger.warn(`[events-endpoint] Port ${port} in use, skipping events endpoint`);
          this.server = null;
          resolve();
        } else {
          reject(err);
        }
      });

      this.server.listen(port, () => {
        logger.info(`[events-endpoint] Listening on port ${port}`);
        resolve();
      });
    });
  }

  /**
   * Close the HTTP listener. Existing in-flight requests finish on their own;
   * this does not await them. Safe to call multiple times.
   */
  stop(): void {
    this.server?.close();
    this.server = null;
  }

  private route(req: IncomingMessage, res: ServerResponse): void {
    if (req.url === "/events") {
      if (req.method !== "POST") {
        return sendStatus(res, 405, { Allow: "POST" });
      }
      this.handlePost(req, res);
      return;
    }
    if (req.url === "/health") {
      if (req.method !== "GET") {
        return sendStatus(res, 405, { Allow: "GET" });
      }
      return sendJson(res, 200, { status: "healthy" });
    }
    sendStatus(res, 404);
  }

  private handlePost(req: IncomingMessage, res: ServerResponse): void {
    const ct = (req.headers["content-type"] ?? "").toString().toLowerCase();
    // Allow `application/json` and `application/json; charset=utf-8`, reject anything else.
    if (!ct.startsWith("application/json")) {
      return sendJson(res, 415, {
        error: "content-type must be application/json",
        code: "unsupported_media_type",
      });
    }

    const chunks: Buffer[] = [];
    let size = 0;
    let aborted = false;

    req.on("data", (chunk: Buffer) => {
      if (aborted) return;
      size += chunk.length;
      if (size > this.maxBodyBytes) {
        aborted = true;
        sendJson(res, 413, {
          error: "payload too large",
          code: "body_too_large",
          limit_bytes: this.maxBodyBytes,
        });
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });

    req.on("end", () => {
      if (aborted) return;

      let parsed: unknown;
      try {
        parsed = JSON.parse(Buffer.concat(chunks).toString("utf-8"));
      } catch (err: any) {
        return sendJson(res, 400, {
          error: `invalid JSON: ${err.message}`,
          code: "invalid_json",
        });
      }

      const envelopeError = validateEnvelope(parsed);
      if (envelopeError) {
        return sendJson(res, 400, {
          error: envelopeError,
          code: "invalid_envelope",
        });
      }
      const event = parsed as VideoEvent;

      let outcome: DispatchOutcome;
      try {
        outcome = this.dispatch(event);
      } catch (err: any) {
        logger.error(`[events-endpoint] DB write failed for ${event.sourceId}/${event.type}: ${err.message}`);
        return sendJson(res, 500, {
          error: err.message,
          code: "internal_error",
        });
      }

      switch (outcome.kind) {
        case "ok":
          if (this.onEvent) this.onEvent(event);
          return sendJson(res, 200, { status: "ok", ...outcome.body });
        case "missing_required_fields":
          logger.warn(`[events-endpoint] ${event.type} event from ${event.sourceId} missing required fields: ${outcome.missing.join(", ")}`);
          return sendJson(res, 422, {
            error: "missing required fields",
            code: "missing_required_fields",
            missing: outcome.missing,
          });
        case "unknown_event_type":
          logger.warn(`[events-endpoint] unknown event type "${outcome.type}" from ${event.sourceId}`);
          return sendJson(res, 422, {
            error: "unknown event type",
            code: "unknown_event_type",
            type: outcome.type,
          });
      }
    });
  }

  /**
   * Dispatch a structurally-valid VideoEvent into DB writes based on `event.type`.
   * Returns an outcome describing whether the row was inserted (and its id), or
   * which semantic check failed. DB exceptions propagate to the caller — they
   * are handled at the HTTP layer as 500.
   */
  private dispatch(event: VideoEvent): DispatchOutcome {
    const p = event.payload;
    const monitorId = event.sourceId;

    switch (event.type) {
      case "motion": {
        const missing = missingFields(p, ["event_file_path", "summary_clip_input", "start_time", "duration_seconds"]);
        if (missing.length) return { kind: "missing_required_fields", missing };

        const ev = this.db.createEvent({
          monitorId,
          motionType: "motion",
          startTime: String(p.start_time),
          endTime: p.end_time ? String(p.end_time) : undefined,
          durationSeconds: Number(p.duration_seconds),
          eventFilePath: String(p.event_file_path),
          prefilterPassed: p.prefilter_passed !== undefined ? Number(p.prefilter_passed) : undefined,
          prefilterClasses: p.prefilter_classes ? String(p.prefilter_classes) : undefined,
          prefilterConfidence: p.prefilter_confidence !== undefined ? Number(p.prefilter_confidence) : undefined,
          trajectoryRegion: p.trajectory_region ? String(p.trajectory_region) : undefined,
        });
        const taskStatus: "pending" | "ignored" =
          p.prefilter_passed !== undefined && Number(p.prefilter_passed) === 0 ? "ignored" : "pending";
        const task = this.db.createTask({
          monitorId,
          eventId: ev.id,
          summaryClipInput: String(p.summary_clip_input),
          status: taskStatus,
        });
        return { kind: "ok", body: { event_id: ev.id, task_id: task.id } };
      }

      case "static": {
        const missing = missingFields(p, ["start_time", "duration_seconds"]);
        if (missing.length) return { kind: "missing_required_fields", missing };

        const ev = this.db.createEvent({
          monitorId,
          motionType: "static",
          startTime: String(p.start_time),
          endTime: p.end_time ? String(p.end_time) : undefined,
          durationSeconds: Number(p.duration_seconds),
        });
        return { kind: "ok", body: { event_id: ev.id } };
      }

      case "recording": {
        const missing = missingFields(p, ["recording_path", "recording_start", "recording_end"]);
        if (missing.length) return { kind: "missing_required_fields", missing };

        const rec = this.db.createRecording({
          monitorId,
          filePath: String(p.recording_path),
          startTime: String(p.recording_start),
          endTime: String(p.recording_end),
          durationSeconds: p.duration_seconds !== undefined ? Number(p.duration_seconds) : undefined,
          fileSizeBytes: p.file_size_bytes !== undefined ? Number(p.file_size_bytes) : undefined,
        });
        return { kind: "ok", body: { recording_id: rec.id } };
      }

      default:
        return { kind: "unknown_event_type", type: String((event as any).type) };
    }
  }
}

/** @returns the first envelope problem (human-readable), or null if envelope is structurally valid. */
function validateEnvelope(parsed: unknown): string | null {
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    return "envelope must be a JSON object";
  }
  const e = parsed as Record<string, unknown>;
  if (typeof e.sourceId !== "string" || e.sourceId.length === 0) {
    return "envelope.sourceId must be a non-empty string";
  }
  if (typeof e.type !== "string" || e.type.length === 0) {
    return "envelope.type must be a non-empty string";
  }
  if (e.payload === undefined || e.payload === null || typeof e.payload !== "object" || Array.isArray(e.payload)) {
    return "envelope.payload must be an object";
  }
  // `timestamp` is required by the contract but cheap to be lenient about — if a client omits it we still
  // consider the envelope structurally valid. We keep the field in the type for upstreams that do send it.
  return null;
}

function missingFields(p: Record<string, unknown>, required: string[]): string[] {
  return required.filter((k) => p[k] === undefined || p[k] === null || p[k] === "");
}

function sendJson(res: ServerResponse, status: number, body: Record<string, unknown>): void {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(body));
}

function sendStatus(res: ServerResponse, status: number, headers?: Record<string, string>): void {
  res.writeHead(status, headers);
  res.end();
}
