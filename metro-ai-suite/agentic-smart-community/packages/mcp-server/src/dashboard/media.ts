// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { createReadStream, existsSync, lstatSync, realpathSync, statSync } from "node:fs";
import { isAbsolute, relative, resolve, sep } from "node:path";
import type { Response } from "express";

function resolveContainedFile(root: string, candidate: string): string | undefined {
  if (!existsSync(root) || !existsSync(candidate)) return undefined;
  const lexicalRoot = resolve(root);
  const lexicalCandidate = resolve(candidate);
  const lexicalRelative = relative(lexicalRoot, lexicalCandidate);
  if (!lexicalRelative || lexicalRelative === ".." || lexicalRelative.startsWith(`..${sep}`)) return undefined;
  let current = lexicalRoot;
  if (lstatSync(current).isSymbolicLink()) return undefined;
  for (const part of lexicalRelative.split(sep)) {
    current = resolve(current, part);
    if (lstatSync(current).isSymbolicLink()) return undefined;
  }
  const realRoot = realpathSync(root);
  const realCandidate = realpathSync(candidate);
  const rel = relative(realRoot, realCandidate);
  if (rel === "" || rel === ".." || rel.startsWith(`..${sep}`) || resolve(realCandidate) === realRoot) {
    return undefined;
  }
  return realCandidate;
}

export function sendSnapshot(res: Response, segmentsDir: string, monitorId: string): void {
  const root = resolve(segmentsDir, monitorId);
  const file = resolveContainedFile(root, resolve(root, "latest.jpg"));
  if (!file) {
    res.status(404).json({ error: "Snapshot not found" });
    return;
  }
  res.set({ "Cache-Control": "no-store", "Content-Type": "image/jpeg", "X-Content-Type-Options": "nosniff" });
  createReadStream(file).pipe(res);
}

/** Resolve an mp4 under this monitor's segment dir, or undefined if it escapes. */
export function resolveMonitorMp4(segmentsDir: string, monitorId: string, clipPath: string): string | undefined {
  const root = resolve(segmentsDir, monitorId);
  const candidate = resolveContainedFile(root, isAbsolute(clipPath) ? clipPath : resolve(root, clipPath));
  if (!candidate || !candidate.toLowerCase().endsWith(".mp4")) return undefined;
  return candidate;
}

export function sendMp4(res: Response, segmentsDir: string, monitorId: string, clipPath: string, range?: string): void {
  const candidate = resolveMonitorMp4(segmentsDir, monitorId, clipPath);
  if (!candidate) {
    res.status(404).json({ error: "Clip not found" });
    return;
  }
  const size = statSync(candidate).size;
  if (!range) {
    res.set({ "Content-Type": "video/mp4", "Content-Length": String(size), "Accept-Ranges": "bytes" });
    createReadStream(candidate).pipe(res);
    return;
  }
  const match = /^bytes=(\d*)-(\d*)$/.exec(range);
  if (!match) {
    res.status(416).set("Content-Range", `bytes */${size}`).end();
    return;
  }
  const suffixLength = !match[1] && match[2] ? Number(match[2]) : undefined;
  const start = suffixLength !== undefined ? Math.max(size - suffixLength, 0) : Number(match[1]);
  const end = suffixLength !== undefined ? size - 1 : match[2] ? Number(match[2]) : size - 1;
  if (suffixLength === 0 || !Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start < 0 || end < start || end >= size) {
    res.status(416).set("Content-Range", `bytes */${size}`).end();
    return;
  }
  res.status(206).set({
    "Content-Type": "video/mp4",
    "Content-Length": String(end - start + 1),
    "Content-Range": `bytes ${start}-${end}/${size}`,
    "Accept-Ranges": "bytes",
  });
  createReadStream(candidate, { start, end }).pipe(res);
}