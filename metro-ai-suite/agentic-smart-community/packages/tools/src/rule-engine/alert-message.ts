/**
 * Standard `alerts.description` formatter used by the built-in rule evaluator
 * and (by convention) mirrored inside each Python override so downstream
 * consumers see a stable format regardless of who produced the alert.
 *
 * Format: `[<useCase>] <alertType>: <severity> — <desc>[ (<extra>)]`
 *
 * `extra` is a free-form suffix appended verbatim inside parentheses when
 * present (e.g. `"wakeup_time=25.5"`).
 */
export interface AlertMessageParts {
  useCase: string;
  alertType: string;
  severity: string;
  desc?: string;
  extra?: string;
}

export function formatAlertMessage(parts: AlertMessageParts): string {
  const { useCase, alertType, severity, desc, extra } = parts;
  const body = `[${useCase}] ${alertType}: ${severity} — ${desc ?? ""}`;
  return extra ? `${body} (${extra})` : body;
}
