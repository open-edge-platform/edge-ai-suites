import { readFile, writeFile, rename, mkdir } from "node:fs/promises";
import { dirname } from "node:path";
import type { CursorStore } from "./types.js";

/**
 * In-memory cursor store. No persistence — after a process restart every monitor looks "fresh"
 * (get → null), so the adapter re-seeds to the current latest alert and skips history. Fine for
 * tests and ephemeral daemons; use FileCursorStore when missed alerts across restarts matter.
 */
export class MemoryCursorStore implements CursorStore {
  private readonly cursors = new Map<string, number>();

  async get(monitorId: string): Promise<number | null> {
    return this.cursors.has(monitorId) ? this.cursors.get(monitorId)! : null;
  }

  async set(monitorId: string, alertId: number): Promise<void> {
    this.cursors.set(monitorId, alertId);
  }
}

/**
 * JSON-file cursor store: `{ "<monitorId>": <alertId>, ... }`.
 *
 * The whole map is cached in memory after the first access; every `set` rewrites the file
 * atomically (temp file + rename). Writes are serialized through a single chained promise so
 * concurrent `set` calls from different monitors can't interleave and corrupt the file — the
 * adapter's per-monitor mutex only orders same-monitor work, not cross-monitor.
 */
export class FileCursorStore implements CursorStore {
  private cache: Record<string, number> | null = null;
  private writeChain: Promise<void> = Promise.resolve();

  constructor(private readonly filePath: string) {}

  private async load(): Promise<Record<string, number>> {
    if (this.cache) return this.cache;
    try {
      const raw = await readFile(this.filePath, "utf8");
      const parsed = JSON.parse(raw) as Record<string, number>;
      this.cache = parsed && typeof parsed === "object" ? parsed : {};
    } catch (err: unknown) {
      // Missing file (first run) or unparseable content → start from an empty map.
      if ((err as NodeJS.ErrnoException)?.code !== "ENOENT") {
        // Corrupt/unreadable existing file: don't crash the adapter, just reset.
      }
      this.cache = {};
    }
    return this.cache;
  }

  async get(monitorId: string): Promise<number | null> {
    const map = await this.load();
    return Object.prototype.hasOwnProperty.call(map, monitorId) ? map[monitorId] : null;
  }

  async set(monitorId: string, alertId: number): Promise<void> {
    const map = await this.load();
    map[monitorId] = alertId;
    // Serialize the flush behind any in-flight write so cross-monitor sets don't race the file.
    const flush = this.writeChain.then(() => this.flush(map));
    // Swallow errors on the shared chain so one failed write can't poison later ones; surface
    // the error to *this* caller via the returned promise.
    this.writeChain = flush.catch(() => undefined);
    return flush;
  }

  private async flush(map: Record<string, number>): Promise<void> {
    await mkdir(dirname(this.filePath), { recursive: true });
    const tmp = `${this.filePath}.tmp`;
    await writeFile(tmp, JSON.stringify(map, null, 2), "utf8");
    await rename(tmp, this.filePath);
  }
}
