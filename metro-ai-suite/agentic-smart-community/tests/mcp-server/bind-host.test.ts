// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// Guards the hardcoded loopback bind. The MCP/dashboard listener and the events
// webhook are both unauthenticated, so binding anything wider hands every MCP
// tool and a direct DB write path to whoever can reach the interface. Off-host
// access is expected to go through `ssh -N -L <port>:127.0.0.1:<port>`.

import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { networkInterfaces, tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { SmartCommunityDB } from "@smart-community-video/db";
import { BIND_HOST, loadConfig } from "../../packages/mcp-server/src/config.js";
import { EventsEndpoint } from "../../packages/mcp-server/src/events-endpoint.js";

test("the bind host is loopback", () => {
  assert.equal(BIND_HOST, "127.0.0.1");
});

// config.yaml must not be able to widen the bind: `host:` keys are no longer read.
test("a host: key in config.yaml is ignored", async () => {
  const dir = await mkdtemp(join(tmpdir(), "bind-host-test-"));
  const path = join(dir, "config.yaml");
  await writeFile(path, 'mcp:\n  port: 3100\n  host: "0.0.0.0"\nevents_webhook:\n  port: 3101\n  host: "0.0.0.0"\n', "utf-8");
  try {
    const config = loadConfig(path);
    assert.equal((config.mcp as Record<string, unknown>).host, undefined);
    assert.equal((config.eventsWebhook as Record<string, unknown>).host, undefined);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test("the events endpoint listens on loopback and refuses the LAN address", async (t) => {
  const dir = await mkdtemp(join(tmpdir(), "bind-host-db-"));
  const db = new SmartCommunityDB(join(dir, "test.db"));
  const endpoint = new EventsEndpoint(db);
  // Port 0 asks the kernel for a free port, so the test never collides with a
  // running server; read back what it actually got.
  await endpoint.start(0);
  const server = (endpoint as unknown as { server: { address(): { port: number } } }).server;
  const { port } = server.address();
  try {
    const local = await fetch(`http://127.0.0.1:${port}/health`);
    assert.equal(local.status, 200);
    assert.deepEqual(await local.json(), { status: "healthy" });

    const lanIp = Object.values(networkInterfaces())
      .flat()
      .find((i) => i && i.family === "IPv4" && !i.internal)?.address;
    if (!lanIp) {
      t.diagnostic("no non-loopback IPv4 address available; skipped the LAN half");
      return;
    }
    await assert.rejects(
      fetch(`http://${lanIp}:${port}/health`),
      "the webhook must not be reachable on a non-loopback address",
    );
  } finally {
    endpoint.stop();
    db.close?.();
    await rm(dir, { recursive: true, force: true });
  }
});
