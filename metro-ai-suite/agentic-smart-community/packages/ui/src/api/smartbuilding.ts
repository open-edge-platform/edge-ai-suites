// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import type { RouterStats, SmartbuildingActivity, SmartbuildingConfig, SmartbuildingMonitor, SmartbuildingReport, SmartbuildingStats } from "../types/smartbuilding.js";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { ...init, headers: { "Content-Type": "application/json", ...init?.headers } });
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json() as Promise<T>;
}

const params = (values: Record<string, string>) => new URLSearchParams(values).toString();
export const smartbuildingApi = {
  config: () => request<SmartbuildingConfig>("/api/dashboard/config"),
  monitors: () => request<SmartbuildingMonitor[]>("/api/monitors"),
  activities: (monitorId: string, date: string) => request<SmartbuildingActivity[]>(`/api/tasks?${params({ monitor_id: monitorId, date })}`),
  reports: (monitorId: string, date: string) => request<SmartbuildingReport[]>(`/api/reports?${params({ monitor_id: monitorId, date })}`),
  stats: (monitorId: string, date: string) => request<SmartbuildingStats>(`/api/stats?${params({ monitor_id: monitorId, date })}`),
  routerStats: () => request<RouterStats>("/api/router/stats"),
  generateReport: (monitorId: string) => request<unknown>("/api/reports/generate", { method: "POST", body: JSON.stringify({ monitor_id: monitorId }) }),
  liveUrl: (monitorId: string) => `/api/monitors/${encodeURIComponent(monitorId)}/live-stream`,
  snapshotUrl: (monitorId: string) => `/api/monitors/${encodeURIComponent(monitorId)}/snapshot?t=${Date.now()}`,
  clipUrl: (taskId: number, monitorId: string) => `/api/tasks/${taskId}/clip?monitor_id=${encodeURIComponent(monitorId)}`,
};