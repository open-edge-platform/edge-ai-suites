import type { SmartBuildingDB } from "@smartbuilding-video/db";

export interface PlanCtlParams {
  monitor_id: string;
  action: "list" | "upsert" | "delete";
  // upsert params
  name?: string;           // unique plan name within monitor, required for upsert / delete
  plan?: Record<string, unknown>; // arbitrary JSON, structure defined by the user; required for upsert
  plan_date?: string;      // optional YYYY-MM-DD hint stored alongside the plan (not the key)
  // list params
  active_only?: boolean;   // default true
}

export function planCtl(db: SmartBuildingDB, params: PlanCtlParams): unknown {
  switch (params.action) {
    case "list":
      return db.listPlans(params.monitor_id, params.active_only ?? true);

    case "upsert": {
      if (!params.name) throw new Error("name is required for upsert");
      if (!params.plan || Object.keys(params.plan).length === 0)
        throw new Error("plan is required for upsert");
      db.upsertPlan(params.monitor_id, params.name, params.plan, params.plan_date);
      return { success: true, name: params.name };
    }

    case "delete": {
      if (!params.name) throw new Error("name is required for delete");
      db.deletePlanByName(params.monitor_id, params.name);
      return { success: true, name: params.name };
    }

    default:
      throw new Error(`Unknown action: ${(params as any).action}`);
  }
}
