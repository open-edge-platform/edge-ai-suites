// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { ref } from "vue";
import { smartbuildingApi } from "../api/smartbuilding.js";
import type { SmartbuildingMonitor } from "../types/smartbuilding.js";

export function useMonitors() {
  const monitors = ref<SmartbuildingMonitor[]>([]); const loading = ref(false); const error = ref("");
  const refresh = async () => { loading.value = true; error.value = ""; try { monitors.value = await smartbuildingApi.monitors(); } catch (cause) { error.value = cause instanceof Error ? cause.message : "Failed to load monitors"; } finally { loading.value = false; } };
  return { monitors, loading, error, refresh };
}