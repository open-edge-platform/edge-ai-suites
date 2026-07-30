// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import assert from "node:assert/strict";
import { createServer, type Server } from "node:http";
import test from "node:test";
import { WebSocket, WebSocketServer } from "ws";
import { OpenClawChatProxy } from "../../packages/mcp-server/src/dashboard/chat-proxy.js";

function listen(server: Server): Promise<number> {
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => {
    const address = server.address();
    if (!address || typeof address === "string") throw new Error("Expected TCP address");
    resolve(address.port);
  }));
}

function closeServer(server: Server): Promise<void> {
  return new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
}

test("chat proxy replaces browser credentials and closes cleanly", async () => {
  const upstreamServer = createServer();
  const upstreamWebSockets = new WebSocketServer({ server: upstreamServer });
  const upstreamPort = await listen(upstreamServer);
  const received = new Promise<Record<string, any>>((resolve) => {
    upstreamWebSockets.once("connection", (socket) => {
      socket.once("message", (data) => resolve(JSON.parse(data.toString())));
    });
  });

  const proxyServer = createServer();
  const proxy = new OpenClawChatProxy({
    openClawGatewayUrl: new URL(`http://127.0.0.1:${upstreamPort}`),
    openClawGatewayToken: "server-only-token",
  });
  proxy.attach(proxyServer);
  const proxyPort = await listen(proxyServer);
  const browser = new WebSocket(`ws://127.0.0.1:${proxyPort}/api/chat`);
  await new Promise<void>((resolve, reject) => {
    browser.once("open", resolve);
    browser.once("error", reject);
  });
  browser.send(JSON.stringify({ type: "req", id: "1", method: "connect", params: { auth: { token: "browser-token" } } }));

  const frame = await received;
  assert.equal(frame.params.auth.token, "server-only-token");
  assert.doesNotMatch(JSON.stringify(frame), /browser-token/);

  browser.close();
  await proxy.close();
  await new Promise<void>((resolve) => upstreamWebSockets.close(() => resolve()));
  await closeServer(proxyServer);
  await closeServer(upstreamServer);
});