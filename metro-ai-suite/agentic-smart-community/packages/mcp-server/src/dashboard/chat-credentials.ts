// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { randomUUID } from "node:crypto";
import type { IncomingMessage } from "node:http";
import type { Request, Response } from "express";
import { z } from "zod";
import type { DashboardIntegrationConfig } from "./integration-env.js";

export const ALLOWED_AGENT_FRAMEWORKS = ["openclaw"] as const;

const SESSION_COOKIE = "agentic_community_chat";
const SESSION_TTL_SECONDS = 30 * 24 * 60 * 60;
const MAX_SESSIONS = 100;

const chatConfigurationSchema = z.object({
  framework: z.enum(ALLOWED_AGENT_FRAMEWORKS),
  url: z.string().trim().max(2048),
  token: z.string().min(1).max(8192),
});

export interface ChatCredentials {
  framework: (typeof ALLOWED_AGENT_FRAMEWORKS)[number];
  gatewayUrl: URL;
  token: string;
}

interface CachedCredentials extends ChatCredentials {
  expiresAt: number;
}

function isAllowedPrivateHost(hostname: string): boolean {
  const normalized = hostname.toLowerCase().replace(/^\[|\]$/g, "");
  if (normalized === "localhost" || normalized === "::1") return true;

  const parts = normalized.split(".").map(Number);
  if (parts.length !== 4 || parts.some((part) => !Number.isInteger(part) || part < 0 || part > 255)) return false;
  return parts[0] === 127 || parts[0] === 10 || (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31) || (parts[0] === 192 && parts[1] === 168);
}

function parseGatewayUrl(value: string): URL | undefined {
  try {
    const url = new URL(value);
    if (!["http:", "https:"].includes(url.protocol)) return undefined;
    if (url.username || url.password || url.search || url.hash) return undefined;
    if (!isAllowedPrivateHost(url.hostname)) return undefined;
    return url;
  } catch {
    return undefined;
  }
}


function readCookie(request: IncomingMessage): string | undefined {
  const cookies = request.headers.cookie?.split(";") ?? [];
  for (const cookie of cookies) {
    const [name, ...valueParts] = cookie.trim().split("=");
    if (name === SESSION_COOKIE) return valueParts.join("=");
  }
  return undefined;
}

export class ChatCredentialStore {
  private readonly sessions = new Map<string, CachedCredentials>();

  constructor(private readonly integrations: DashboardIntegrationConfig) {}

  getFrameworks(): Array<{ id: string; label: string; defaultUrl: string }> {
    return [{ id: "openclaw", label: "OpenClaw", defaultUrl: "http://127.0.0.1:18789/" }];
  }

  isConfigured(request: IncomingMessage): boolean {
    return this.resolve(request) !== undefined;
  }

  resolve(request: IncomingMessage): ChatCredentials | undefined {
    if (this.integrations.openClawGatewayUrl && this.integrations.openClawGatewayToken) {
      return {
        framework: "openclaw",
        gatewayUrl: this.integrations.openClawGatewayUrl,
        token: this.integrations.openClawGatewayToken,
      };
    }

    const sessionId = readCookie(request);
    if (!sessionId) return undefined;
    const credentials = this.sessions.get(sessionId);
    if (!credentials) return undefined;
    if (credentials.expiresAt <= Date.now()) {
      this.sessions.delete(sessionId);
      return undefined;
    }
    return credentials;
  }

  configure(request: Request, response: Response): { configured: true } | { error: string } {
    const parsed = chatConfigurationSchema.safeParse(request.body);
    if (!parsed.success) return { error: "Invalid framework configuration" };
    const gatewayUrl = parseGatewayUrl(parsed.data.url);
    if (!gatewayUrl) return { error: "URL must use HTTP(S) and target localhost or a private IP address" };

    this.prune();
    if (this.sessions.size >= MAX_SESSIONS) {
      const oldestSessionId = this.sessions.keys().next().value;
      if (oldestSessionId) this.sessions.delete(oldestSessionId);
    }

    const sessionId = randomUUID();
    this.sessions.set(sessionId, {
      framework: parsed.data.framework,
      gatewayUrl,
      token: parsed.data.token,
      expiresAt: Date.now() + SESSION_TTL_SECONDS * 1000,
    });
    const secure = request.secure ? "; Secure" : "";
    response.setHeader(
      "Set-Cookie",
      `${SESSION_COOKIE}=${sessionId}; Path=/; HttpOnly; SameSite=Strict; Max-Age=${SESSION_TTL_SECONDS}${secure}`,
    );
    return { configured: true };
  }

  private prune(): void {
    const now = Date.now();
    for (const [sessionId, credentials] of this.sessions) {
      if (credentials.expiresAt <= now) this.sessions.delete(sessionId);
    }
  }
}