// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { existsSync } from "node:fs";
import { resolve } from "node:path";
import express, { type Express } from "express";

export function mountStaticUi(app: Express): void {
  const uiDist = resolve(process.env.SMARTBUILDING_UI_DIST ?? resolve(process.cwd(), "packages/ui/dist"));
  const indexFile = resolve(uiDist, "index.html");
  if (!existsSync(indexFile)) return;

  app.use(express.static(uiDist, { index: false, fallthrough: true }));
  app.get(/^(?!\/(?:api|mcp)(?:\/|$)).*/, (_req, res) => {
    res.set("Cache-Control", "no-store");
    res.sendFile(indexFile);
  });
}