import type { Logger } from "@smartbuilding-video/framework-adapter-sdk";

/**
 * Shared contract between the two session-append implementations (`session-inject.ts`,
 * `session-append.ts`) and their caller (`sink.ts`). Dependency-free so nothing couples to
 * `openclaw` or to the other impl.
 */

export interface AppendResult {
  ok: boolean;
  sessionKey: string;
  sessionId?: string;
  reason?: string;
}

export interface InjectParams {
  agentId: string;
  /** Defaults to `agent:<agentId>:main`. */
  sessionKey?: string;
  /** Short one-line user separator (breaks ControlUI same-role grouping). */
  separatorText: string;
  /** Raw alert body, appended as the assistant turn. */
  assistantText: string;
  /**
   * Stable per-alert key (e.g. `sb-alert:<monitorId>:<alert.id>`) for transcript idempotency, so an
   * at-least-once replay does not double-append. Used by session-inject.ts; ignored by session-append.ts.
   */
  idempotencyKey?: string;
  model?: string;
  logger: Logger;
}

/** One alert turn → one session. Implemented by both the new and legacy appenders. */
export type SessionAppender = (params: InjectParams) => Promise<AppendResult>;
