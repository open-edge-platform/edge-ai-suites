import { test } from "node:test";
import assert from "node:assert/strict";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { randomUUID } from "node:crypto";
import { readFile, rm } from "node:fs/promises";
import {
  SmartBuildingAdapter,
  FileCursorStore,
  type AlertSink,
  type AlertPayload,
  type CursorStore,
  type Logger,
} from "@smartbuilding-video/framework-adapter-sdk";
import { MockMcpServer } from "./fixtures/mock-mcp-server.js";

const silent: Logger = { debug() {}, info() {}, warn() {}, error() {} };
const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function waitFor(cond: () => boolean, timeoutMs = 4000, stepMs = 20): Promise<void> {
  const start = Date.now();
  while (!cond()) {
    if (Date.now() - start > timeoutMs) throw new Error("waitFor: condition not met in time");
    await delay(stepMs);
  }
}

class RecordingSink implements AlertSink {
  readonly pushed: Array<{ monitorId: string; id: number }> = [];
  private readonly failIds = new Set<number>();

  /** Make the next push of this alert id throw exactly once (simulates a transient sink failure). */
  failOnce(id: number): void {
    this.failIds.add(id);
  }

  async push({ monitorId, alert }: AlertPayload): Promise<void> {
    if (this.failIds.has(alert.id)) {
      this.failIds.delete(alert.id);
      throw new Error(`sink deliberate failure on ${alert.id}`);
    }
    this.pushed.push({ monitorId, id: alert.id });
  }

  ids(monitorId?: string): number[] {
    return this.pushed.filter((p) => !monitorId || p.monitorId === monitorId).map((p) => p.id);
  }
}

interface AdapterOpts {
  cursorStore?: CursorStore;
  pollFallbackMs?: number;
  reconnect?: { initialMs?: number; maxMs?: number; factor?: number };
}

function httpAdapter(
  url: string,
  monitorIds: string[],
  sink: AlertSink,
  extra: AdapterOpts = {},
): SmartBuildingAdapter {
  return new SmartBuildingAdapter(
    {
      transport: { kind: "http", url },
      monitorIds,
      logger: silent,
      cursorStore: extra.cursorStore,
      pollFallbackMs: extra.pollFallbackMs,
      reconnect: extra.reconnect,
    },
    sink,
  );
}

test("seeds to latest on fresh start (skips history), then delivers new alerts", async () => {
  const server = new MockMcpServer();
  const url = await server.start();
  const sink = new RecordingSink();
  const adapter = httpAdapter(url, ["cam_child"], sink);
  try {
    // Pre-existing history — must NOT be replayed after seed.
    server.addAlertSilently("cam_child");
    server.addAlertSilently("cam_child");

    await adapter.start();
    await delay(100);
    assert.deepEqual(sink.ids(), [], "history should not be replayed on fresh seed");

    const a = server.fireAlert("cam_child");
    await waitFor(() => sink.ids().length === 1);
    assert.deepEqual(sink.ids(), [a.id]);
  } finally {
    await adapter.stop();
    await server.stop();
  }
});

test("delivers a rapid burst exactly once, in ascending id order (coalescing + debounce)", async () => {
  const server = new MockMcpServer();
  const url = await server.start();
  const sink = new RecordingSink();
  const adapter = httpAdapter(url, ["cam_child"], sink);
  try {
    await adapter.start();
    const fired = Array.from({ length: 5 }, () => server.fireAlert("cam_child").id);

    await waitFor(() => sink.ids().length === 5);
    await delay(150); // let any extra (duplicate) syncs settle

    assert.deepEqual(sink.ids(), [...fired].sort((a, b) => a - b), "ascending, no dupes, no loss");
    assert.equal(new Set(sink.ids()).size, 5, "no duplicate deliveries");
  } finally {
    await adapter.stop();
    await server.stop();
  }
});

test("preserves per-monitor order and isolates across monitors", async () => {
  const server = new MockMcpServer();
  const url = await server.start();
  const sink = new RecordingSink();
  const adapter = httpAdapter(url, ["cam_a", "cam_b"], sink);
  try {
    await adapter.start();
    // Interleave alerts across two monitors.
    const a: number[] = [];
    const b: number[] = [];
    a.push(server.fireAlert("cam_a").id);
    b.push(server.fireAlert("cam_b").id);
    a.push(server.fireAlert("cam_a").id);
    b.push(server.fireAlert("cam_b").id);
    a.push(server.fireAlert("cam_a").id);
    b.push(server.fireAlert("cam_b").id);

    await waitFor(() => sink.ids().length === 6);

    assert.deepEqual(sink.ids("cam_a"), [...a].sort((x, y) => x - y), "cam_a in order");
    assert.deepEqual(sink.ids("cam_b"), [...b].sort((x, y) => x - y), "cam_b in order");
  } finally {
    await adapter.stop();
    await server.stop();
  }
});

test("resumes from a persisted cursor across restart without replay", async () => {
  const server = new MockMcpServer();
  const url = await server.start();
  const cursorPath = join(tmpdir(), `sb-cursor-${randomUUID()}.json`);
  const sink1 = new RecordingSink();
  const adapter1 = httpAdapter(url, ["cam_child"], sink1, {
    cursorStore: new FileCursorStore(cursorPath),
  });
  try {
    await adapter1.start();
    const first = [
      server.fireAlert("cam_child").id,
      server.fireAlert("cam_child").id,
      server.fireAlert("cam_child").id,
    ];
    await waitFor(() => sink1.ids().length === 3);
    await adapter1.stop();

    // Cursor file should now hold the latest delivered id.
    const persisted = JSON.parse(await readFile(cursorPath, "utf8"));
    assert.equal(persisted.cam_child, Math.max(...first));

    // An alert arrives while the adapter is down.
    const missed = server.fireAlert("cam_child").id;

    const sink2 = new RecordingSink();
    const adapter2 = httpAdapter(url, ["cam_child"], sink2, {
      cursorStore: new FileCursorStore(cursorPath),
    });
    await adapter2.start();
    await waitFor(() => sink2.ids().length === 1);

    assert.deepEqual(sink2.ids(), [missed], "only the missed alert, no replay of the first three");
    await adapter2.stop();
  } finally {
    await server.stop();
    await rm(cursorPath, { force: true });
  }
});

test("reconnects after a disconnect and delivers alerts produced during downtime", async () => {
  const server = new MockMcpServer();
  const url = await server.start();
  const sink = new RecordingSink();
  const adapter = httpAdapter(url, ["cam_child"], sink, {
    reconnect: { initialMs: 50, maxMs: 200, factor: 2 },
  });
  try {
    await adapter.start();
    const a1 = server.fireAlert("cam_child").id;
    await waitFor(() => sink.ids().length === 1);

    await server.dropConnections(); // kill the live SSE/transport
    // Alert fired while disconnected — notification is lost, must be recovered by resync-on-reconnect.
    const a2 = server.fireAlert("cam_child").id;

    await waitFor(() => sink.ids().includes(a2), 6000);
    assert.deepEqual(
      [...new Set(sink.ids())].sort((x, y) => x - y),
      [a1, a2],
      "both alerts delivered exactly once after reconnect",
    );
  } finally {
    await adapter.stop();
    await server.stop();
  }
});

test("poll fallback recovers a lost notification", async () => {
  const server = new MockMcpServer();
  const url = await server.start();
  const sink = new RecordingSink();
  const adapter = httpAdapter(url, ["cam_child"], sink, { pollFallbackMs: 120 });
  try {
    await adapter.start();
    // Alert added WITHOUT a notification — only the poll can find it.
    const a = server.addAlertSilently("cam_child").id;

    await waitFor(() => sink.ids().includes(a), 3000);
    assert.deepEqual(sink.ids(), [a]);
  } finally {
    await adapter.stop();
    await server.stop();
  }
});

test("does not advance cursor on sink failure (at-least-once replay)", async () => {
  const server = new MockMcpServer();
  const url = await server.start();
  const sink = new RecordingSink();
  const adapter = httpAdapter(url, ["cam_child"], sink);
  try {
    await adapter.start();
    const a1 = server.fireAlert("cam_child").id;
    sink.failOnce(a1); // first delivery attempt throws → cursor must not advance
    await delay(150);
    assert.deepEqual(sink.ids(), [], "failed push not recorded");

    // Next alert triggers a resync from the un-advanced cursor, replaying a1 then delivering a2.
    const a2 = server.fireAlert("cam_child").id;
    await waitFor(() => sink.ids().includes(a2));
    assert.deepEqual(
      [...new Set(sink.ids())].sort((x, y) => x - y),
      [a1, a2],
      "a1 replayed and a2 delivered after the transient failure",
    );
  } finally {
    await adapter.stop();
    await server.stop();
  }
});
