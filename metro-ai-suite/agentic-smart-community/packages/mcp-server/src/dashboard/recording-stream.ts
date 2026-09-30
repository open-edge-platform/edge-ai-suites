// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { spawn } from "node:child_process";
import { existsSync, renameSync, statSync, unlinkSync } from "node:fs";
import { basename, dirname, extname, join } from "node:path";
import type { Response } from "express";
import { sendMp4 } from "./media.js";

const TRANSCODE_TIMEOUT_MS = 120_000;

/**
 * Recordings written before continuous_recorder switched to H.264 are MPEG-4
 * Part 2 (cv2.VideoWriter's "mp4v" fourcc), which no browser can decode. Those
 * get transcoded once into a sibling `<stem>.h264.mp4` and served from there, so
 * the route's contract stays uniform: always a seekable H.264 mp4 of the whole
 * segment. The cache file lives in the same date directory, so the recorder's
 * retention sweep removes it along with the original.
 */
const codecCache = new Map<string, string>();
const inFlight = new Map<string, Promise<string | undefined>>();

function cacheKey(file: string): string {
  const stat = statSync(file);
  return `${file}:${stat.size}:${stat.mtimeMs}`;
}

function run(command: string, args: string[], timeoutMs: number): Promise<{ code: number | null; stdout: string; stderr: string }> {
  return new Promise((resolve) => {
    const child = spawn(command, args, { shell: false, stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    const timer = setTimeout(() => child.kill("SIGKILL"), timeoutMs);
    timer.unref();
    child.stdout.on("data", (chunk: Buffer) => { stdout = (stdout + chunk.toString()).slice(-4096); });
    child.stderr.on("data", (chunk: Buffer) => { stderr = (stderr + chunk.toString()).slice(-4096); });
    child.once("error", () => { clearTimeout(timer); resolve({ code: null, stdout, stderr }); });
    child.once("close", (code) => { clearTimeout(timer); resolve({ code, stdout, stderr }); });
  });
}

async function detectVideoCodec(file: string): Promise<string> {
  const key = cacheKey(file);
  const cached = codecCache.get(key);
  if (cached) return cached;

  const { stdout } = await run("ffprobe", [
    "-v", "error",
    "-select_streams", "v:0",
    "-show_entries", "stream=codec_name",
    "-of", "default=nw=1:nk=1",
    file,
  ], 10_000);

  const codec = stdout.trim().split("\n")[0] || "unknown";
  codecCache.set(key, codec);
  return codec;
}

function h264CachePath(file: string): string {
  return join(dirname(file), `${basename(file, extname(file))}.h264.mp4`);
}

async function transcodeToH264(file: string): Promise<string | undefined> {
  const target = h264CachePath(file);
  if (existsSync(target) && statSync(target).mtimeMs >= statSync(file).mtimeMs) {
    return target;
  }

  const pending = inFlight.get(target);
  if (pending) return pending;

  const task = (async () => {
    const temp = `${target}.tmp.mp4`;
    const { code, stderr } = await run("ffmpeg", [
      "-hide_banner", "-loglevel", "error", "-y",
      "-i", file,
      "-map", "0:v:0",
      "-c:v", "libx264",
      "-preset", "veryfast",
      "-profile:v", "baseline",
      "-level", "3.1",
      "-pix_fmt", "yuv420p",
      "-crf", "26",
      "-an",
      "-movflags", "+faststart",
      temp,
    ], TRANSCODE_TIMEOUT_MS);

    if (code !== 0 || !existsSync(temp)) {
      console.error(`[recording-stream] transcode failed for ${file}: ${stderr}`);
      try { if (existsSync(temp)) unlinkSync(temp); } catch {}
      return undefined;
    }

    renameSync(temp, target);
    return target;
  })().finally(() => inFlight.delete(target));

  inFlight.set(target, task);
  return task;
}

/** Serve a recording segment as a seekable H.264 mp4, transcoding if needed. */
export async function sendRecording(
  res: Response,
  segmentsDir: string,
  monitorId: string,
  file: string,
  range?: string,
): Promise<void> {
  let playable = file;

  if (await detectVideoCodec(file) !== "h264") {
    const transcoded = await transcodeToH264(file);
    if (!transcoded) {
      res.status(415).json({ error: "Recording could not be prepared for playback" });
      return;
    }
    playable = transcoded;
  }

  sendMp4(res, segmentsDir, monitorId, playable, range);
}
