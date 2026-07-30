// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { ref } from "vue"; import { smartbuildingApi } from "../api/smartbuilding.js"; import type { SmartbuildingReport } from "../types/smartbuilding.js";
export function useReports() { const reports = ref<SmartbuildingReport[]>([]); const generating = ref(false); const load = async (monitorId: string, date: string) => { reports.value = await smartbuildingApi.reports(monitorId, date); }; const generate = async (monitorId: string, date: string) => { generating.value = true; try { await smartbuildingApi.generateReport(monitorId); await load(monitorId, date); } finally { generating.value = false; } }; return { reports, generating, load, generate }; }