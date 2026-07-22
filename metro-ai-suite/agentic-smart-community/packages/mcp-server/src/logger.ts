// MCP server uses stderr for all logging — stdout is reserved for JSON-RPC.
// Set LOG_LEVEL=debug to enable debug output (default: info).

import { appendFileSync, mkdirSync, statSync } from "node:fs";
import { join } from "node:path";

type Level = "debug" | "info" | "warn" | "error";

const LEVELS: Record<Level, number> = { debug: 0, info: 1, warn: 2, error: 3 };

const configured = (process.env.LOG_LEVEL ?? "info").toLowerCase() as Level;
const minLevel = LEVELS[configured] ?? LEVELS.info;

function log(level: Level, msg: string): void {
  if (LEVELS[level] >= minLevel) {
    const tag = level.toUpperCase().padEnd(5);
    console.error(`[${tag}] ${msg}`);
  }
}

export const logger = {
  debug: (msg: string) => log("debug", msg),
  info:  (msg: string) => log("info",  msg),
  warn:  (msg: string) => log("warn",  msg),
  error: (msg: string) => log("error", msg),
};

// ─────────────────────────────────────────────────────────────
// Per-monitor file logger
// ─────────────────────────────────────────────────────────────
// Writes to $SMARTBUILDING_DATA_DIR/logs/monitors/<monitor_id>/<YYYY-MM-DD>.log
// Rotates by day; refuses to grow a single day's file past maxFileMb.

export interface MonitorLogger {
  debug(msg: string): void;
  info(msg: string): void;
  warn(msg: string): void;
  error(msg: string): void;
  /** Path of the file currently being written (may change as the day rolls over). */
  currentLogPath(): string;
}

const oversizedWarned = new Set<string>();

export function monitorLogger(monitorId: string, monitorsLogsDir: string, maxFileMb: number): MonitorLogger {
  const baseDir = join(monitorsLogsDir, monitorId);
  try { mkdirSync(baseDir, { recursive: true }); } catch { /* best-effort */ }

  const maxBytes = maxFileMb * 1024 * 1024;

  const pathFor = (date: Date) => {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, "0");
    const d = String(date.getDate()).padStart(2, "0");
    return join(baseDir, `${y}-${m}-${d}.log`);
  };

  const writeLine = (level: Level, msg: string) => {
    const now = new Date();
    const file = pathFor(now);
    const line = `${now.toISOString()} [${level.toUpperCase().padEnd(5)}] ${msg}\n`;
    try {
      let size = 0;
      try { size = statSync(file).size; } catch { /* file may not exist yet */ }
      if (size + line.length > maxBytes) {
        if (!oversizedWarned.has(file)) {
          oversizedWarned.add(file);
          logger.warn(`[monitor-logger] ${file} exceeded ${maxFileMb} MB, suppressing further writes for today`);
        }
        return;
      }
      appendFileSync(file, line);
    } catch (err) {
      // Don't let logger failure crash the caller; surface to stderr once.
      logger.error(`[monitor-logger] failed to write ${file}: ${err}`);
    }
  };

  return {
    debug: (msg) => writeLine("debug", msg),
    info:  (msg) => writeLine("info",  msg),
    warn:  (msg) => writeLine("warn",  msg),
    error: (msg) => writeLine("error", msg),
    currentLogPath: () => pathFor(new Date()),
  };
}
