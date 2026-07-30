// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { ref } from "vue"; import { smartbuildingApi } from "../api/smartbuilding.js"; import type { RouterStats, SmartbuildingConfig } from "../types/smartbuilding.js";
export function useIntegrationStatus() { const config = ref<SmartbuildingConfig>(); const router = ref<RouterStats>({ status: "not_configured" }); const load = async () => { config.value = await smartbuildingApi.config(); router.value = config.value.router === "configured" ? await smartbuildingApi.routerStats().catch(() => ({ status: "unavailable" as const })) : { status: "not_configured" }; }; return { config, router, load }; }