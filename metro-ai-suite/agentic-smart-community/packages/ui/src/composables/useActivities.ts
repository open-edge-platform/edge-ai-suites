// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { ref } from "vue"; import { smartbuildingApi } from "../api/smartbuilding.js"; import type { SmartbuildingActivity } from "../types/smartbuilding.js";
export function useActivities() { const activities = ref<SmartbuildingActivity[]>([]); const loading = ref(false); let requestId = 0; const load = async (monitorId: string, date: string) => { const id = ++requestId; loading.value = true; try { const value = await smartbuildingApi.activities(monitorId, date); if (id === requestId) activities.value = value; } finally { if (id === requestId) loading.value = false; } }; return { activities, loading, load }; }