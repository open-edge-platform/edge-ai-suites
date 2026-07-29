import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { randomBytes } from "node:crypto";
import type { Logger } from "@smartbuilding-video/framework-adapter-sdk";
import type { AppendResult, InjectParams } from "./inject-types.js";

/**
 * Fallback session append using plain node fs (no `openclaw` import), used when the transcript API
 * in `session-inject.ts` is unavailable.
 *
 * Writes BOTH a user line and an assistant line (neither from an LLM): ControlUI groups consecutive
 * same-role messages into one block stamped with the first message's time, so a one-line user
 * separator keeps each alert visually distinct.
 */

function openclawHome(): string {
  return process.env.OPENCLAW_HOME ?? path.join(os.homedir(), ".openclaw");
}

function sessionsJsonPath(agentId: string): string {
  return path.join(openclawHome(), "agents", agentId, "sessions", "sessions.json");
}

function sessionJsonlPath(agentId: string, sessionId: string): string {
  return path.join(openclawHome(), "agents", agentId, "sessions", `${sessionId}.jsonl`);
}

interface SessionEntry {
  sessionId?: string;
  [k: string]: unknown;
}

function readSessionsJson(filePath: string): Record<string, SessionEntry> | null {
  try {
    const parsed = JSON.parse(fs.readFileSync(filePath, "utf-8"));
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, SessionEntry>;
    }
    return null;
  } catch {
    return null;
  }
}

function writeSessionsJsonAtomic(filePath: string, data: Record<string, SessionEntry>): boolean {
  try {
    const tmp = `${filePath}.tmp.${process.pid}.${Date.now()}`;
    fs.writeFileSync(tmp, JSON.stringify(data, null, 2), "utf-8");
    fs.renameSync(tmp, filePath);
    return true;
  } catch {
    return false;
  }
}

/**
 * Resolve the sessionId for a sessionKey; if absent, mint one by cloning the agent's
 * `:main` entry (so ControlUI treats the new per-source session as fully provisioned).
 * Returns null when the agent has no `:main` entry to clone from.
 */
function resolveOrCreateSessionId(
  agentId: string,
  sessionKey: string,
  logger: Logger,
): string | null {
  const storePath = sessionsJsonPath(agentId);
  const store = readSessionsJson(storePath);
  if (!store) return null;

  const existing = store[sessionKey]?.sessionId;
  if (typeof existing === "string" && existing) return existing;

  const mainEntry = store[`agent:${agentId}:main`];
  if (!mainEntry || typeof mainEntry !== "object") {
    logger.warn(`[sb-alerts] cannot mint ${sessionKey}: agent ${agentId} has no :main entry`);
    return null;
  }

  const newSid = randomBytes(16)
    .toString("hex")
    .replace(/^(.{8})(.{4})(.{4})(.{4})(.{12}).*/, "$1-$2-$3-$4-$5");

  const newJsonl = sessionJsonlPath(agentId, newSid);
  try {
    if (!fs.existsSync(newJsonl)) fs.writeFileSync(newJsonl, "", "utf-8");
  } catch (err) {
    logger.warn(`[sb-alerts] failed to create jsonl for ${newSid}: ${err}`);
    return null;
  }

  // Clone :main for a provisioned-looking entry, but pin sessionId AND sessionFile to the new
  // session — else the clone inherits :main's sessionFile, which the transcript API would follow.
  store[sessionKey] = {
    ...(mainEntry as SessionEntry),
    sessionId: newSid,
    sessionFile: newJsonl,
    updatedAt: Date.now(),
  };
  if (!writeSessionsJsonAtomic(storePath, store)) {
    logger.warn(`[sb-alerts] failed to write sessions.json for ${sessionKey}`);
    return null;
  }
  logger.info(`[sb-alerts] minted session ${sessionKey} (sid=${newSid})`);
  return newSid;
}

function shortId(bytes = 4): string {
  return randomBytes(bytes).toString("hex");
}

/**
 * Append an alert turn (user separator + raw alert as assistant reply) to an agent's session JSONL.
 * `idempotencyKey` is accepted for signature parity with session-inject.ts but ignored here.
 */
export function appendAlertTurns(params: InjectParams): AppendResult {
  const { agentId, separatorText, assistantText, model, logger } = params;
  const sessionKey = params.sessionKey ?? `agent:${agentId}:main`;

  const sid = resolveOrCreateSessionId(agentId, sessionKey, logger);
  if (!sid) return { ok: false, sessionKey, reason: `sessionId not found / could not mint for ${sessionKey}` };

  const jsonlPath = sessionJsonlPath(agentId, sid);
  // Recreate the transcript file if missing (e.g. sid from an existing entry whose jsonl was swept)
  // instead of failing. lastId then stays null and this alert becomes the first turn.
  if (!fs.existsSync(jsonlPath)) {
    try {
      fs.writeFileSync(jsonlPath, "", "utf-8");
      logger.info(`[sb-alerts] recreated missing jsonl for ${sessionKey} (sid=${sid})`);
    } catch (err) {
      return { ok: false, sessionKey, reason: `jsonl missing and recreate failed: ${jsonlPath}: ${err}` };
    }
  }

  // parentId chains to the last message so ControlUI's tree stays connected.
  let lastId: string | null = null;
  try {
    const lines = fs.readFileSync(jsonlPath, "utf-8").split("\n").filter((l) => l.trim().length > 0);
    for (let i = lines.length - 1; i >= 0; i--) {
      try {
        const obj = JSON.parse(lines[i]);
        if (obj && typeof obj === "object" && typeof obj.id === "string") {
          lastId = obj.id;
          break;
        }
      } catch {
        /* skip malformed line */
      }
    }
  } catch (err) {
    return { ok: false, sessionKey, reason: `read jsonl failed: ${err}` };
  }

  const nowIso = new Date().toISOString();
  const nowMs = Date.now();
  const userId = shortId();
  const assistantId = shortId();

  const userLine = {
    type: "message",
    id: userId,
    parentId: lastId,
    timestamp: nowIso,
    message: { role: "user", content: [{ type: "text", text: separatorText }], timestamp: nowMs },
  };
  const assistantLine = {
    type: "message",
    id: assistantId,
    parentId: userId,
    timestamp: nowIso,
    message: {
      role: "assistant",
      content: [{ type: "text", text: assistantText }],
      api: "openai-completions",
      provider: "router",
      model: model ?? "smartbuilding-alerts-adapter",
      timestamp: nowMs,
    },
  };

  try {
    fs.appendFileSync(jsonlPath, JSON.stringify(userLine) + "\n" + JSON.stringify(assistantLine) + "\n", "utf-8");
  } catch (err) {
    return { ok: false, sessionKey, reason: `append failed: ${err}` };
  }

  // Bump updatedAt so ControlUI resorts the session list.
  try {
    const storePath = sessionsJsonPath(agentId);
    const store = readSessionsJson(storePath);
    if (store && store[sessionKey]) {
      store[sessionKey] = { ...store[sessionKey], updatedAt: nowMs };
      writeSessionsJsonAtomic(storePath, store);
    }
  } catch {
    /* non-fatal */
  }

  return { ok: true, sessionKey, sessionId: sid };
}
