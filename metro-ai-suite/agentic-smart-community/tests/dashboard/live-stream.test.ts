// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { PassThrough } from "node:stream";
import test from "node:test";
import type { ChildProcessByStdio } from "node:child_process";
import type { Readable } from "node:stream";
import type { Request, Response } from "express";
import { LiveStreamManager } from "../../packages/mcp-server/src/dashboard/live-stream.js";

class FakeResponse extends EventEmitter {
  destroyed = false;
  headersSent = false;
  statusCode = 200;
  status(code: number) { this.statusCode = code; return this; }
  set() { return this; }
  json() { this.headersSent = true; return this; }
  flushHeaders() { this.headersSent = true; }
  write() { return true; }
  end() { this.emit("close"); return this; }
  destroy() { this.destroyed = true; this.emit("close"); return this; }
}

function fakeRequest(): Request {
  return new EventEmitter() as Request;
}

test("multiple viewers share one process and repeated disconnects release all resources", async () => {
  let spawnCount = 0;
  const manager = new LiveStreamManager({
    idleTimeoutMs: 1,
    stopTimeoutMs: 10,
    spawnProcess: () => {
      spawnCount += 1;
      const child = new EventEmitter() as ChildProcessByStdio<null, Readable, Readable>;
      child.stdout = new PassThrough();
      child.stderr = new PassThrough();
      child.kill = (() => {
        queueMicrotask(() => child.emit("close", 0, "SIGTERM"));
        return true;
      }) as typeof child.kill;
      return child;
    },
  });

  for (let round = 0; round < 25; round += 1) {
    const first = new FakeResponse();
    const second = new FakeResponse();
    await manager.handle(fakeRequest(), first as unknown as Response, "cam-1", "rtsp://localhost/live");
    await manager.handle(fakeRequest(), second as unknown as Response, "cam-1", "rtsp://localhost/live");
    assert.equal(manager.getDiagnostics().sessions, 1);
    assert.equal(manager.getDiagnostics().clients, 2);
    assert.equal(spawnCount, round + 1);
    first.emit("close");
    second.emit("close");
    await new Promise((resolve) => setTimeout(resolve, 5));
    assert.deepEqual(manager.getDiagnostics(), { sessions: 0, clients: 0, timers: 0, bufferedBytes: 0 });
  }

  await manager.close();
});