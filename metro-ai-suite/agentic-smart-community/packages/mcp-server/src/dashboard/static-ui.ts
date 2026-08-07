// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { existsSync } from "node:fs";
import { resolve } from "node:path";
import express, { type Express } from "express";

export function mountStaticUi(app: Express): void {
  const dashboardDist = resolve(process.env.SMARTBUILDING_DASHBOARD_DIST ?? resolve(process.cwd(), "packages/dashboard/dist"));
  const indexFile = resolve(dashboardDist, "index.html");
  if (!existsSync(indexFile)) return;

  app.use(express.static(dashboardDist, { index: false, fallthrough: true }));
  app.get(/^(?!\/(?:api|mcp)(?:\/|$)).*/, (_req, res) => {
    res.set("Cache-Control", "no-store");
    res.sendFile(indexFile);
  });
}