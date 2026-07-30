// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

export interface SmartbuildingMonitor { id: string; name: string; status: "online" | "offline" | "error"; useCase: string; videoSummaryTask: string; createdAt: string }
export interface SmartbuildingTask { id: number; monitorId: string; summaryText?: string; summaryClipInput?: string; status: string; createdAt: string; [key: string]: unknown }
export interface SmartbuildingActivity { task: SmartbuildingTask; event?: { id: number; motionType: string; startTime: string }; alert?: { id: number; description?: string; notified: boolean; createdAt: string } }
export interface SmartbuildingReport { id: number; monitorId: string; reportText?: string; status: string; reportType: string; periodStart: string; periodEnd: string; createdAt: string }
export interface SmartbuildingStats { promptTokens: number; imageTokens: number; completionTokens: number; totalTokens: number; activities: number; alerts: number }
export interface SmartbuildingConfig { router: "configured" | "unconfigured"; chat: "configured" | "unconfigured"; media: { mode: "live-stream"; snapshotFallback: boolean } }
export interface RouterStats { status: "configured" | "not_configured" | "unavailable"; data?: unknown }