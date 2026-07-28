import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { existsSync } from "node:fs";
import { parseSummaryFields, normalizeSummaryTextBySchema } from "./summary-parser.js";
import { formatAlertMessage } from "./alert-message.js";

export { parseSummaryFields } from "./summary-parser.js";
export { normalizeSummaryTextBySchema } from "./summary-parser.js";
export type { ParsedSummary } from "./summary-parser.js";
export { formatAlertMessage } from "./alert-message.js";
export type { AlertMessageParts } from "./alert-message.js";

const execFileAsync = promisify(execFile);

/** Severity ordinals used by defaultRuleEvaluator for threshold comparison. */
const SEVERITY_ORDER: Record<string, number> = {
  info: 0,
  warn: 1,
  critical: 2,
};

export interface RuleContext {
  monitorId: string;
  useCase: string;
  taskId: number;
  /** Full VLM summary text — kept for Python overrides that want raw access. */
  summaryText: string;
  /**
   * Parsed schema fields injected by task-poller (already extracted via parseSummaryFields).
   * Caller-provided so rule engine doesn't re-parse.
   *
   * Use-case specific rules are not part of the core payload. Custom alert
   * decisions belong in an `evaluate_rules.py` override.
   */
  payload: {
    fields?: Record<string, string>;
  } & Record<string, unknown>;
}

export interface RuleResult {
  shouldAlert: boolean;
  /** Human-readable alert text. Stored in alerts.description (no separate alert_type column). */
  alertMessage?: string;
}

export type RuleEvaluator = (context: RuleContext) => Promise<RuleResult>;

interface AlertOutcome {
  alertType?: string;
  severity?: string;
  description?: string;
}

/**
 * Default rule: alert when the parsed `severity` field is warn or critical.
 *
 * Complex use-case logic (time comparisons, multi-event joint decisions,
 * external service calls) still needs a Python override — see
 * `evaluateWithOverride`. `elder_wakeup` is a canonical example.
 */
export async function defaultRuleEvaluator(context: RuleContext): Promise<RuleResult> {
  const fields = context.payload?.fields ?? {};

  const severity = (fields["severity"] ?? "").toLowerCase();
  const severityLevel = SEVERITY_ORDER[severity];
  if (severityLevel === undefined) return { shouldAlert: false };

  const thresholdLevel = SEVERITY_ORDER["warn"];
  if (severityLevel < thresholdLevel) return { shouldAlert: false };

  const eventField = fields["event"] ?? "alert";
  const desc = fields["desc"] ?? fields["description"] ?? "";
  return {
    shouldAlert: true,
    alertMessage: formatAlertMessage({
      useCase: context.useCase,
      alertType: eventField,
      severity,
      desc,
    }),
  };
}

function alertOutcomeToRuleResult(useCase: string, outcome: AlertOutcome | null | undefined): RuleResult {
  if (!outcome) return { shouldAlert: false };
  const alertType = outcome.alertType ?? "alert";
  const severity = (outcome.severity ?? "warn").toLowerCase();
  const desc = outcome.description ?? "";
  return {
    shouldAlert: true,
    alertMessage: formatAlertMessage({
      useCase,
      alertType,
      severity,
      desc,
    }),
  };
}

/**
 * Run a Python rule override at the given path, falling back to defaultRuleEvaluator
 * only when overridePath is null.
 *
 * The override script receives parsed fields as JSON on argv[1]. It prints an
 * AlertOutcome JSON object or null.
 *
 * Path is supplied by the caller (typically derived from config.useCaseDict[useCase].evaluate_rules_path)
 * rather than hard-coded — use case adapters live anywhere on disk.
 */
export async function evaluateWithOverride(
  context: RuleContext,
  overridePath: string | null,
): Promise<RuleResult> {
  if (!overridePath) {
    return defaultRuleEvaluator(context);
  }

  if (!existsSync(overridePath)) {
    throw new Error(`Configured Python rule override does not exist: ${overridePath}`);
  }

  try {
    const { stdout } = await execFileAsync("python3", [
      "-S",
      overridePath,
      JSON.stringify(context.payload?.fields ?? {}),
    ], { timeout: 10_000 });
    const text = stdout.trim();
    const result = text ? JSON.parse(text) : null;
    return alertOutcomeToRuleResult(context.useCase, result);
  } catch (err: any) {
    throw new Error(`[rule-engine] Python override failed for ${context.useCase}: ${err.message}`);
  }
}

