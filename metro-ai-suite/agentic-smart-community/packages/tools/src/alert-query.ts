import type { SmartBuildingDB } from "@smartbuilding-video/db";

export interface AlertQueryParams {
  monitor_id: string;
  action: "latest" | "by_date" | "ack" | "stats";
  // latest action parameters
  limit?: number;
  // by_date action parameters
  start_date?: string; // YYYY-MM-DD
  end_date?: string; // YYYY-MM-DD
  // ack action parameters
  alert_id?: number;
  ack_by?: string;
}

export async function alertQuery(
  db: SmartBuildingDB,
  params: AlertQueryParams
): Promise<unknown> {
  switch (params.action) {
    case "latest": {
      const alerts = db.queryAlertsWithDetails({
        monitorId: params.monitor_id,
        limit: params.limit ?? 20,
      });
      return { alerts };
    }

    case "by_date": {
      if (!params.start_date) {
        throw new Error("start_date is required for by_date action");
      }
      if (!params.end_date) {
        throw new Error("end_date is required for by_date action");
      }
      const alerts = db.queryAlertsWithDetails({
        monitorId: params.monitor_id,
        startDate: params.start_date,
        endDate: params.end_date,
      });
      return { alerts };
    }

    case "stats": {
      const stats = db.getAlertStats(
        params.monitor_id,
        params.start_date,
        params.end_date
      );
      return stats;
    }

    case "ack": {
      if (!params.alert_id) {
        throw new Error("alert_id is required for ack action");
      }
      if (!params.ack_by) {
        throw new Error("ack_by is required for ack action");
      }
      db.ackAlertWithUser(params.alert_id, params.ack_by);
      return { success: true, alert_id: params.alert_id };
    }

    default:
      throw new Error(`Unknown action: ${(params as any).action}`);
  }
}
