import type { SmartBuildingDB, SchemaDefinition } from "@smartbuilding-video/db";
import type { RuleContext, RuleResult } from "./rule-engine/index.js";
import { evaluateWithOverride } from "./rule-engine/index.js";

/**
 * Configuration slice needed by `ruleEval`. The tool looks up the monitor's use
 * case to find both its `evaluate_rules_path` and its own `schema` (extension
 * columns) — the same per-use-case data path used by TaskPoller.
 */
export interface RuleEvalDeps {
  useCaseDict: Record<
    string,
    {
      evaluate_rules_path?: string;
      /**
       * This use case's own schema. Its `video_summary_tasks.extensions` names
       * are the columns rule_eval reads back into `RuleContext.payload.fields`
       * (the built-in `rowToTask` mapper drops dynamic columns).
       */
      schema?: SchemaDefinition;
    }
  >;
}

export interface RuleEvalParams {
  monitor_id: string;
  /**
   * Task to re-evaluate. When omitted, the most recent completed task for the
   * monitor is used.
   */
  task_id?: number;
  /**
    * If true and the evaluator returns `shouldAlert`, insert a new alert row.
    * Default `false` — dry-run (no row).
   */
  create_alert?: boolean;
}

export interface RuleEvalResult {
  monitor_id: string;
  use_case: string;
  task_id: number;
  rule_result: RuleResult;
  alert_created?: boolean;
  alert_id?: number;
}

/**
 * Manual rule-engine re-evaluation for an already-completed task.
 *
 * Rebuilds the same `RuleContext` `TaskPoller` would have used (fields parsed
 * from the stored `summary_text`) and runs `evaluateWithOverride`. Useful for:
 *
 *   - Debugging why a task did or did not produce an alert.
 *   - Re-running the evaluator after editing an override script.
 *   - Producing an alert retroactively when the poller was down at the time.
 */
export async function ruleEval(
  db: SmartBuildingDB,
  deps: RuleEvalDeps,
  params: RuleEvalParams,
): Promise<RuleEvalResult> {
  const monitor = db.getMonitor(params.monitor_id);
  if (!monitor) {
    throw new Error(`Monitor not found: ${params.monitor_id}`);
  }
  const useCase = monitor.useCase ?? "";
  const useCaseCfg = deps.useCaseDict[useCase];

  // Resolve target task.
  let task: any;
  if (params.task_id !== undefined) {
    task = db.getTask(params.task_id);
    if (!task) throw new Error(`Task not found: ${params.task_id}`);
    if (task.monitorId !== params.monitor_id) {
      throw new Error(
        `Task ${params.task_id} belongs to monitor ${task.monitorId}, not ${params.monitor_id}`,
      );
    }
  } else {
    const latest = db.queryTasks({
      monitorId: params.monitor_id,
      status: "completed",
      limit: 1,
    });
    if (latest.length === 0) {
      throw new Error(`No completed tasks found for monitor ${params.monitor_id}`);
    }
    task = latest[0];
  }

  // Rebuild the RuleContext from stored extension columns. `getTask` maps
  // hard-coded core columns only; extension columns (event/severity/desc/...)
  // live in raw SQLite so we query them directly.
  const fields: Record<string, string> = {};
  const extensionNames = (useCaseCfg?.schema?.video_summary_tasks?.extensions ?? []).map((e) => e.name);
  if (extensionNames.length > 0) {
    const row = (db as any).db
      .prepare(`SELECT ${extensionNames.map((n) => `"${n}"`).join(", ")} FROM video_summary_tasks WHERE id = ?`)
      .get(task.id) as Record<string, unknown> | undefined;
    if (row) {
      for (const name of extensionNames) {
        const val = row[name];
        if (typeof val === "string") fields[name] = val;
      }
    }
  }

  const ruleCtx: RuleContext = {
    monitorId: params.monitor_id,
    useCase,
    taskId: task.id,
    summaryText: task.summaryText ?? "",
    payload: {
      fields,
    },
  };

  const overridePath = useCaseCfg?.evaluate_rules_path ?? null;
  const ruleResult = await evaluateWithOverride(ruleCtx, overridePath);

  const out: RuleEvalResult = {
    monitor_id: params.monitor_id,
    use_case: useCase,
    task_id: task.id,
    rule_result: ruleResult,
  };

  if (!ruleResult.shouldAlert || !params.create_alert) {
    return out;
  }

  const alert = db.createAlert({
    monitorId: params.monitor_id,
    taskId: task.id,
    eventId: task.eventId,
    useCase,
    description: ruleResult.alertMessage,
    notified: true,
  });
  out.alert_created = true;
  out.alert_id = alert.id;
  return out;
}
