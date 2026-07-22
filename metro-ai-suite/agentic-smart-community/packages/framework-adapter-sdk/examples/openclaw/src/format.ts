import type { AlertPayload } from "@smartbuilding-video/framework-adapter-sdk";

type Alert = AlertPayload["alert"];

/** Read an optional field as a trimmed string, or undefined if absent/blank.
 *  severity/event/alert_type are optional schema extensions, so probe defensively. */
function str(alert: Alert, key: string): string | undefined {
  const v = (alert as unknown as Record<string, unknown>)[key];
  return typeof v === "string" && v.trim() ? v.trim() : undefined;
}

const USE_CASE_EMOJI: Record<string, string> = {
  fridge: "🧊",
  child_safety: "🛡️",
  elder_wakeup: "🌅",
};

function emoji(alert: Alert): string {
  return USE_CASE_EMOJI[alert.useCase] ?? "🔔";
}

/**
 * One-line user "separator" shown above each alert. Breaks ControlUI's same-role grouping so each
 * alert keeps its own timestamp. e.g. `🔔 [CRITICAL] climb — <time> cam_child`
 */
export function formatSeparator(alert: Alert): string {
  const sev = str(alert, "severity");
  const event = str(alert, "event") ?? str(alert, "alert_type") ?? alert.useCase;
  const sevTag = sev ? `[${sev.toUpperCase()}] ` : "";
  return `🔔 ${sevTag}${event} — ${alert.createdAt} ${alert.monitorId}`;
}

/** The alert body delivered into the session — raw, no persona polish. */
export function formatAlert(alert: Alert): string {
  const desc = alert.description?.trim() || "(no description)";
  return `${emoji(alert)} ${desc}`;
}
