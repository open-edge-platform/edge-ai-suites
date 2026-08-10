import { randomUUID } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import type { Logger } from "@smart-community-video/framework-adapter-sdk";
import type { AppendResult, InjectParams, SessionAppender } from "./inject-types.js";

function openclawHome(): string {
  return process.env.OPENCLAW_HOME ?? path.join(os.homedir(), ".openclaw");
}

/**
 * Canonical transcript path for a session id. Mirrors the runtime's own scheme
 * (`agents/<agentId>/sessions/<sessionId>.jsonl`) for the non-threaded sessions this adapter
 * uses — alert sessions never carry a threadId, so no `#thread` suffix applies.
 */
function canonicalSessionFile(agentId: string, sessionId: string): string {
  return path.join(openclawHome(), "agents", agentId, "sessions", `${sessionId}.jsonl`);
}

// Live alert transcript rotates to a fresh sessionId past this size (old file kept as archive;
// full history stays in the MCP DB). Override via SB_ALERTS_MAX_TRANSCRIPT_BYTES; default 1024 KiB.
const ALERTS_MAX_TRANSCRIPT_BYTES = ((): number => {
  const raw = Number(process.env.SB_ALERTS_MAX_TRANSCRIPT_BYTES);
  return Number.isFinite(raw) && raw > 0 ? raw : 1024 * 1024;
})();

/**
 * Session append via OpenClaw's first-class transcript API. The SDK owns header creation,
 * parentId/leaf linking, the write lock, and idempotency — we resolve the target session and hand
 * it the two messages.
 *
 * The plugin-sdk subpaths are reached via dynamic import in try/catch: if unavailable,
 * `createTranscriptInjector` returns null and the caller falls back to `session-append.ts`.
 * `openclaw` is provided by the gateway at load time, not a repo dependency.
 */
export async function createTranscriptInjector(deps: {
  /** `api.config` (OpenClawConfig) — used by the SDK for redaction + transcript header metadata. */
  config?: unknown;
  env?: NodeJS.ProcessEnv;
  logger: Logger;
}): Promise<SessionAppender | null> {
  let transcriptRt: any;
  let storeRt: any;
  try {
    // @ts-expect-error openclaw is provided by the gateway at load time, not a repo dependency
    transcriptRt = await import("openclaw/plugin-sdk/session-transcript-runtime");
    // @ts-expect-error openclaw is provided by the gateway at load time, not a repo dependency
    storeRt = await import("openclaw/plugin-sdk/session-store-runtime");
  } catch (err) {
    deps.logger.info(
      `[sb-alerts] transcript API unavailable — falling back to FS-append: ${err}`,
    );
    return null;
  }

  const { withSessionTranscriptWriteLock } = transcriptRt;
  const { getSessionEntry, patchSessionEntry } = storeRt;
  const { config, env } = deps;

  const injector: SessionAppender = async (params: InjectParams): Promise<AppendResult> => {
    const { agentId, separatorText, assistantText, idempotencyKey, model, logger } = params;
    const sessionKey = params.sessionKey ?? `agent:${agentId}:main`;

    // Resolve (or mint) the session id, then pin the store entry's `sessionFile` to the canonical
    // path for THIS sessionId. The transcript API writes to whatever `sessionFile` the entry holds,
    // even if it disagrees with sessionId, so a stale sessionFile would misroute the alert. Patch
    // only when something is off; systemSent:true keeps ControlUI from sweeping the session.
    let entry: { sessionId?: string; sessionFile?: string } | undefined;
    try {
      entry = getSessionEntry({ agentId, sessionKey, env }) as typeof entry;
    } catch (err) {
      return { ok: false, sessionKey, reason: `getSessionEntry failed: ${err}` };
    }
    let sessionId = entry?.sessionId ?? randomUUID();
    let sessionFile = canonicalSessionFile(agentId, sessionId);

    // Rotate to a fresh sessionId once the live transcript crosses the size cap.
    if (entry?.sessionId) {
      let size = 0;
      try {
        size = fs.statSync(sessionFile).size;
      } catch {
        size = 0;
      }
      if (size >= ALERTS_MAX_TRANSCRIPT_BYTES) {
        sessionId = randomUUID();
        sessionFile = canonicalSessionFile(agentId, sessionId);
        logger.info(`[sb-alerts] rotated ${sessionKey} (${size}B) → new sid ${sessionId}`);
      }
    }

    if (!entry || entry.sessionId !== sessionId || entry.sessionFile !== sessionFile) {
      try {
        // `update` is a patch CALLBACK (its return is merged into the existing entry), not a
        // plain object; `fallbackEntry` seeds a brand-new entry when none exists yet.
        await patchSessionEntry({
          agentId,
          sessionKey,
          env,
          update: () => ({ sessionId, sessionFile, systemSent: true }),
          fallbackEntry: { sessionId, sessionFile, systemSent: true },
        });
        logger.info(
          `[sb-alerts] ${entry ? "repaired" : "minted"} session ${sessionKey} ` +
            `(sid=${sessionId}, file=${path.basename(sessionFile)})`,
        );
      } catch (err) {
        return { ok: false, sessionKey, reason: `ensure session entry failed: ${err}` };
      }
    }

    // Append separator + assistant turn under one write lock, then publish one UI update.
    // Two lines because ControlUI merges consecutive same-role messages into one block stamped with
    // the first message's time — a short user separator keeps each alert visually distinct.
    // Distinct idempotency keys per line so the "scan" dedupe doesn't treat the body as a duplicate.
    const nowMs = Date.now();
    const userMsg: Record<string, unknown> = {
      role: "user",
      content: [{ type: "text", text: separatorText }],
      timestamp: nowMs,
      ...(idempotencyKey ? { idempotencyKey: `${idempotencyKey}:sep` } : {}),
    };
    const assistantMsg: Record<string, unknown> = {
      role: "assistant",
      content: [{ type: "text", text: assistantText }],
      api: "openai-completions",
      provider: "router",
      model: model ?? "smart-community-alerts-adapter",
      timestamp: nowMs,
      ...(idempotencyKey ? { idempotencyKey: `${idempotencyKey}:body` } : {}),
    };
    const idempotencyLookup = idempotencyKey ? "scan" : undefined;

    try {
      await withSessionTranscriptWriteLock(
        { agentId, sessionKey, sessionId, config, env },
        async (ctx: any) => {
          await ctx.appendMessage({ message: userMsg, idempotencyLookup });
          await ctx.appendMessage({ message: assistantMsg, idempotencyLookup });
          await ctx.publishUpdate();
        },
      );
    } catch (err) {
      return { ok: false, sessionKey, sessionId, reason: `transcript append failed: ${err}` };
    }

    // Bump `updatedAt` so this session sorts as most-recently-active (the dashboard
    // and ControlUI order sessions by it). The transcript API's publishUpdate does
    // not touch the store entry's `updatedAt`, so without this the session that
    // actually receives alerts stays frozen at its last settings change while an
    // idle `:main` outranks it. Mirrors the FS-append fallback. Non-fatal.
    try {
      await patchSessionEntry({
        agentId,
        sessionKey,
        env,
        update: () => ({ updatedAt: nowMs }),
        fallbackEntry: { sessionId, sessionFile, systemSent: true, updatedAt: nowMs },
      });
    } catch (err) {
      logger.warn(`[sb-alerts] updatedAt bump failed for ${sessionKey}: ${err}`);
    }

    return { ok: true, sessionKey, sessionId };
  };

  return injector;
}
