// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { spawn, type ChildProcessByStdio } from "node:child_process";
import type { Readable } from "node:stream";
import type { Request, Response } from "express";

const MAX_SESSIONS = 8;
const MAX_CLIENTS_PER_SESSION = 12;
const MAX_CLIENT_QUEUE_BYTES = 4 * 1024 * 1024;
const MAX_INIT_SEGMENT_BYTES = 2 * 1024 * 1024;
const MAX_STDERR_BYTES = 16 * 1024;
const IDLE_TIMEOUT_MS = 5_000;
const STOP_TIMEOUT_MS = 3_000;

interface StreamClient {
  response: Response;
  queue: Buffer[];
  queuedBytes: number;
  waitingForDrain: boolean;
  handleDrain: () => void;
  flush: () => void;
  detach: () => void;
}

interface StreamSession {
  monitorId: string;
  child: ChildProcessByStdio<null, Readable, Readable>;
  clients: Set<StreamClient>;
  state: "running" | "stopping" | "closed";
  initParts: Buffer[];
  initBytes: number;
  initSegment?: Buffer;
  stderr: Buffer;
  idleTimer?: NodeJS.Timeout;
  stopTimer?: NodeJS.Timeout;
  closed: Promise<void>;
  resolveClosed: () => void;
}

type StreamChild = ChildProcessByStdio<null, Readable, Readable>;

interface LiveStreamManagerOptions {
  spawnProcess?: (sourceUrl: string) => StreamChild;
  idleTimeoutMs?: number;
  stopTimeoutMs?: number;
}

export class LiveStreamManager {
  private readonly sessions = new Map<string, StreamSession>();
  private closing = false;

  constructor(private readonly options: LiveStreamManagerOptions = {}) {}

  getDiagnostics(): { sessions: number; clients: number; timers: number; bufferedBytes: number } {
    let clients = 0;
    let timers = 0;
    let bufferedBytes = 0;
    for (const session of this.sessions.values()) {
      clients += session.clients.size;
      timers += Number(Boolean(session.idleTimer)) + Number(Boolean(session.stopTimer));
      bufferedBytes += session.initBytes + (session.initSegment?.byteLength ?? 0) + session.stderr.byteLength;
    }
    return { sessions: this.sessions.size, clients, timers, bufferedBytes };
  }

  async handle(req: Request, res: Response, monitorId: string, sourceUrl: string): Promise<void> {
    if (this.closing) {
      res.status(503).json({ error: "Live streaming is shutting down" });
      return;
    }

    let parsed: URL;
    try {
      parsed = new URL(sourceUrl);
    } catch {
      res.status(422).json({ error: "Monitor source URL is invalid" });
      return;
    }
    if (parsed.protocol !== "rtsp:" && parsed.protocol !== "rtsps:") {
      res.status(422).json({ error: "Monitor source does not support RTSP live preview" });
      return;
    }

    let session = this.sessions.get(monitorId);
    if (session?.state === "stopping") {
      await session.closed;
      session = undefined;
    }
    if (!session) {
      if (this.sessions.size >= MAX_SESSIONS) {
        res.status(503).json({ error: "Live stream capacity reached" });
        return;
      }
      session = this.createSession(monitorId, sourceUrl);
    }
    if (session.clients.size >= MAX_CLIENTS_PER_SESSION) {
      res.status(429).json({ error: "Too many viewers for this monitor" });
      return;
    }

    this.attachClient(req, res, session);
  }

  async close(): Promise<void> {
    this.closing = true;
    const sessions = [...this.sessions.values()];
    for (const session of sessions) this.stopSession(session);
    await Promise.all(sessions.map((session) => session.closed));
  }

  private createSession(monitorId: string, sourceUrl: string): StreamSession {
    let resolveClosed!: () => void;
    const closed = new Promise<void>((resolve) => { resolveClosed = resolve; });
    const child = this.options.spawnProcess?.(sourceUrl) ?? spawn("ffmpeg", [
      "-hide_banner",
      "-loglevel", "warning",
      "-rtsp_transport", "tcp",
      "-i", sourceUrl,
      "-map", "0:v:0",
      "-vf", "setpts=PTS-STARTPTS",
      "-c:v", "libx264",
      "-preset", "ultrafast",
      "-tune", "zerolatency",
      "-profile:v", "baseline",
      "-level", "3.1",
      "-pix_fmt", "yuv420p",
      "-crf", "23",
      "-g", "30",
      "-keyint_min", "30",
      "-sc_threshold", "0",
      "-an",
      "-f", "mp4",
      "-movflags", "frag_every_frame+empty_moov+default_base_moof",
      "pipe:1",
    ], { shell: false, stdio: ["ignore", "pipe", "pipe"] });

    const session: StreamSession = {
      monitorId,
      child,
      clients: new Set(),
      state: "running",
      initParts: [],
      initBytes: 0,
      stderr: Buffer.alloc(0),
      closed,
      resolveClosed,
    };
    this.sessions.set(monitorId, session);

    child.stdout.on("data", (chunk: Buffer) => this.broadcast(session, chunk));
    child.stderr.on("data", (chunk: Buffer) => {
      session.stderr = Buffer.concat([session.stderr, chunk]).subarray(-MAX_STDERR_BYTES);
    });
    child.once("error", () => this.stopSession(session));
    child.once("close", () => this.finalizeSession(session));
    return session;
  }

  private attachClient(req: Request, res: Response, session: StreamSession): void {
    if (session.idleTimer) {
      clearTimeout(session.idleTimer);
      session.idleTimer = undefined;
    }
    res.status(200);
    res.set({
      "Content-Type": "video/mp4",
      "Cache-Control": "no-store",
      Connection: "keep-alive",
      "X-Content-Type-Options": "nosniff",
    });
    res.flushHeaders();

    let detached = false;
    const client: StreamClient = {
      response: res,
      queue: [],
      queuedBytes: 0,
      waitingForDrain: false,
      handleDrain: () => {
        client.waitingForDrain = false;
        client.flush();
      },
      flush: () => {
        if (detached || client.waitingForDrain || res.destroyed) return;
        while (client.queue.length > 0) {
          const chunk = client.queue.shift()!;
          client.queuedBytes -= chunk.length;
          if (!res.write(chunk)) {
            client.waitingForDrain = true;
            res.once("drain", client.handleDrain);
            return;
          }
        }
      },
      detach: () => {
        if (detached) return;
        detached = true;
        req.off("aborted", client.detach);
        res.off("close", client.detach);
        res.off("error", client.detach);
        res.off("drain", client.handleDrain);
        client.queue = [];
        client.queuedBytes = 0;
        session.clients.delete(client);
        if (session.clients.size === 0 && session.state === "running" && !session.idleTimer) {
          session.idleTimer = setTimeout(() => this.stopSession(session), this.options.idleTimeoutMs ?? IDLE_TIMEOUT_MS);
          session.idleTimer.unref();
        }
      },
    };
    req.once("aborted", client.detach);
    res.once("close", client.detach);
    res.once("error", client.detach);
    session.clients.add(client);

    if (session.initSegment) {
      this.enqueueClientChunk(client, session.initSegment);
    }
  }

  private broadcast(session: StreamSession, chunk: Buffer): void {
    this.captureInitSegment(session, chunk);
    for (const client of [...session.clients]) {
      this.enqueueClientChunk(client, chunk);
    }
  }

  private enqueueClientChunk(client: StreamClient, chunk: Buffer): void {
    if (client.response.destroyed || client.queuedBytes + chunk.length > MAX_CLIENT_QUEUE_BYTES) {
      client.detach();
      client.response.destroy();
      return;
    }
    client.queue.push(chunk);
    client.queuedBytes += chunk.length;
    client.flush();
  }

  private captureInitSegment(session: StreamSession, chunk: Buffer): void {
    if (session.initSegment || session.initBytes >= MAX_INIT_SEGMENT_BYTES) return;
    const remaining = MAX_INIT_SEGMENT_BYTES - session.initBytes;
    const retained = chunk.subarray(0, remaining);
    session.initParts.push(retained);
    session.initBytes += retained.length;
    const candidate = Buffer.concat(session.initParts, session.initBytes);
    const moofMarker = candidate.indexOf(Buffer.from("moof"));
    if (moofMarker >= 4) {
      session.initSegment = Buffer.from(candidate.subarray(0, moofMarker - 4));
      session.initParts = [];
      session.initBytes = 0;
    }
  }

  private stopSession(session: StreamSession): void {
    if (session.state !== "running") return;
    session.state = "stopping";
    if (session.idleTimer) {
      clearTimeout(session.idleTimer);
      session.idleTimer = undefined;
    }
    for (const client of [...session.clients]) {
      client.detach();
      client.response.end();
    }
    session.child.kill("SIGTERM");
    session.stopTimer = setTimeout(() => {
      if (session.state !== "closed") session.child.kill("SIGKILL");
    }, this.options.stopTimeoutMs ?? STOP_TIMEOUT_MS);
    session.stopTimer.unref();
  }

  private finalizeSession(session: StreamSession): void {
    if (session.state === "closed") return;
    session.state = "closed";
    if (session.idleTimer) clearTimeout(session.idleTimer);
    if (session.stopTimer) clearTimeout(session.stopTimer);
    for (const client of [...session.clients]) {
      client.detach();
      client.response.end();
    }
    session.child.stdout.removeAllListeners();
    session.child.stderr.removeAllListeners();
    session.child.removeAllListeners();
    session.initParts = [];
    session.initSegment = undefined;
    session.stderr = Buffer.alloc(0);
    session.idleTimer = undefined;
    session.stopTimer = undefined;
    if (this.sessions.get(session.monitorId) === session) this.sessions.delete(session.monitorId);
    session.resolveClosed();
  }
}