// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import assert from "node:assert/strict";
import test from "node:test";
import { WebSocketChatService } from "../../packages/ui/src/views/home/components/WebSocketChatService.js";

test("selecting the same chat session twice publishes only once", () => {
  const originalWebSocket = globalThis.WebSocket;
  let sessionPublishCount = 0;

  class FakeWebSocket {
    static readonly OPEN = 1;
    readyState = 0;
    onopen: (() => void) | null = null;
    onmessage: (() => void) | null = null;
    onerror: (() => void) | null = null;
    onclose: (() => void) | null = null;

    close() {}
  }

  Object.defineProperty(globalThis, "WebSocket", {
    configurable: true,
    value: FakeWebSocket,
  });

  try {
    const service = new WebSocketChatService({
      url: "ws://localhost/api/chat",
      authToken: "",
      onMessagesChange: () => undefined,
      onSessionsChange: () => {
        sessionPublishCount += 1;
      },
    });

    service.selectSession("agent:main:main");
    service.selectSession("agent:main:main");

    assert.equal(sessionPublishCount, 1);
    service.disconnect();
  } finally {
    Object.defineProperty(globalThis, "WebSocket", {
      configurable: true,
      value: originalWebSocket,
    });
  }
});
