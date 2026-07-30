// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import type { IncomingMessage, Server } from "node:http";
import type { Duplex } from "node:stream";
import { WebSocket, WebSocketServer, type RawData } from "ws";
import type { ChatCredentialStore, ChatCredentials } from "./chat-credentials.js";

const MAX_CONNECTIONS = 20;
const MAX_BROWSER_MESSAGE_BYTES = 64 * 1024;
const MAX_UPSTREAM_MESSAGE_BYTES = 25 * 1024 * 1024;
const MAX_BUFFERED_BYTES = 1024 * 1024;

interface SocketPair { browser: WebSocket; upstream: WebSocket }

function rawDataBytes(data: RawData): number {
  if (data instanceof ArrayBuffer) return data.byteLength;
  if (Array.isArray(data)) return data.reduce((total, part) => total + part.byteLength, 0);
  return data.byteLength;
}

export class OpenClawChatProxy {
  private readonly webSocketServer = new WebSocketServer({ noServer: true, maxPayload: MAX_BROWSER_MESSAGE_BYTES });
  private readonly pairs = new Set<SocketPair>();
  private server?: Server;
  private upgradeHandler?: (request: IncomingMessage, socket: Duplex, head: Buffer) => void;

  constructor(private readonly credentials: ChatCredentialStore) {}

  attach(server: Server): void {
    this.server = server;
    this.upgradeHandler = (request, socket, head) => {
      const pathname = new URL(request.url ?? "/", "http://localhost").pathname;
      if (pathname !== "/api/chat") {
        socket.destroy();
        return;
      }
      const credentials = this.credentials.resolve(request);
      if (!credentials) {
        socket.end("HTTP/1.1 503 Service Unavailable\r\nConnection: close\r\n\r\n");
        return;
      }
      if (this.pairs.size >= MAX_CONNECTIONS) {
        socket.end("HTTP/1.1 429 Too Many Requests\r\nConnection: close\r\n\r\n");
        return;
      }
      this.webSocketServer.handleUpgrade(request, socket, head, (browser) => this.connect(browser, credentials));
    };
    server.on("upgrade", this.upgradeHandler);
  }

  async close(): Promise<void> {
    if (this.server && this.upgradeHandler) this.server.off("upgrade", this.upgradeHandler);
    for (const pair of [...this.pairs]) {
      pair.browser.close(1001, "Server shutdown");
      pair.upstream.close(1001, "Server shutdown");
    }
    this.pairs.clear();
    await new Promise<void>((resolve) => this.webSocketServer.close(() => resolve()));
  }

  private connect(browser: WebSocket, credentials: ChatCredentials): void {
    const gateway = new URL(credentials.gatewayUrl);
    gateway.protocol = gateway.protocol === "https:" ? "wss:" : "ws:";
    const upstream = new WebSocket(gateway, {
      handshakeTimeout: 5_000,
      maxPayload: MAX_UPSTREAM_MESSAGE_BYTES,
      origin: credentials.gatewayUrl.origin,
      headers: { Authorization: `Bearer ${credentials.token}` },
    });
    const pair = { browser, upstream };
    this.pairs.add(pair);
    const pending: Array<{ data: RawData; binary: boolean }> = [];
    let pendingBytes = 0;
    let closed = false;

    const cleanup = () => {
      if (closed) return;
      closed = true;
      pending.length = 0;
      pendingBytes = 0;
      this.pairs.delete(pair);
      if (browser.readyState === WebSocket.OPEN) browser.close();
      if (upstream.readyState === WebSocket.OPEN || upstream.readyState === WebSocket.CONNECTING) upstream.close();
    };
    const send = (target: WebSocket, data: RawData, binary: boolean) => {
      if (target.readyState !== WebSocket.OPEN || target.bufferedAmount > MAX_BUFFERED_BYTES) {
        cleanup();
        return;
      }
      target.send(data, { binary });
    };
    const injectToken = (data: RawData, binary: boolean): RawData => {
      if (binary) return data;
      try {
        const frame = JSON.parse(data.toString()) as { type?: string; method?: string; params?: Record<string, unknown> };
        if (frame.type === "req" && frame.method === "connect") {
          frame.params = { ...frame.params, auth: { token: credentials.token } };
          return Buffer.from(JSON.stringify(frame));
        }
      } catch { /* The upstream gateway validates malformed frames. */ }
      return data;
    };

    browser.on("message", (data, binary) => {
      const secured = injectToken(data, binary);
      if (upstream.readyState === WebSocket.CONNECTING) {
        const bytes = rawDataBytes(secured);
        if (pendingBytes + bytes > MAX_BROWSER_MESSAGE_BYTES) { cleanup(); return; }
        pending.push({ data: secured, binary });
        pendingBytes += bytes;
        return;
      }
      send(upstream, secured, binary);
    });
    upstream.on("open", () => {
      for (const frame of pending) send(upstream, frame.data, frame.binary);
      pending.length = 0;
      pendingBytes = 0;
    });
    upstream.on("message", (data, binary) => send(browser, data, binary));
    browser.on("close", cleanup);
    browser.on("error", cleanup);
    upstream.on("close", cleanup);
    upstream.on("error", cleanup);
  }
}