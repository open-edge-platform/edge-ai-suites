/**
 * MCP tool family wrapping the multilevel-video-understanding
 * `/v1/tasks` REST endpoints — list / get / delete VLM tasks
 * (both builtin and dynamic). Registration + update flow already
 * lives in `smartbuilding_use_case_register`; this tool covers the
 * remaining read + drop actions for ops visibility.
 */

export interface VideoSummaryTaskParams {
  action: "list" | "get" | "delete";
  /** Required for `get` and `delete`. Ignored by `list`. */
  task_name?: string;
}

export interface VideoSummaryTaskDeps {
  summaryServiceUrl: string;
}

export interface VideoSummaryTaskResult {
  action: "list" | "get" | "delete";
  task_name?: string;
  ok: boolean;
  tasks?: Array<{ name: string; source?: string; description?: string }>;
  task?: Record<string, unknown>;
  status?: "deleted" | "builtin_immutable" | "not_found";
  warnings: string[];
  errors: string[];
}

const REQUEST_TIMEOUT_MS = 8000;

export async function videoSummaryTask(
  params: VideoSummaryTaskParams,
  deps: VideoSummaryTaskDeps,
): Promise<VideoSummaryTaskResult> {
  const result: VideoSummaryTaskResult = {
    action: params.action,
    task_name: params.task_name,
    ok: false,
    warnings: [],
    errors: [],
  };

  if (params.action !== "list" && !params.task_name) {
    result.errors.push(`task_name is required for action=${params.action}`);
    return result;
  }

  try {
    if (params.action === "list") {
      const resp = await fetch(`${deps.summaryServiceUrl}/v1/tasks`, {
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });
      if (!resp.ok) {
        result.errors.push(`GET /v1/tasks returned HTTP ${resp.status}`);
        return result;
      }
      const body = (await resp.json()) as any;
      const tasks = Array.isArray(body?.tasks) ? body.tasks : [];
      result.tasks = tasks.map((t: any) => ({
        name: t.name,
        source: t.source,
        description: t.description,
      }));
      result.ok = true;
      return result;
    }

    if (params.action === "get") {
      const resp = await fetch(`${deps.summaryServiceUrl}/v1/tasks/${params.task_name}`, {
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });
      if (resp.status === 404) {
        result.status = "not_found";
        result.errors.push(`task "${params.task_name}" not found`);
        return result;
      }
      if (!resp.ok) {
        result.errors.push(`GET /v1/tasks/${params.task_name} returned HTTP ${resp.status}`);
        return result;
      }
      result.task = (await resp.json()) as Record<string, unknown>;
      result.ok = true;
      return result;
    }

    // action === "delete"
    const resp = await fetch(`${deps.summaryServiceUrl}/v1/tasks/${params.task_name}`, {
      method: "DELETE",
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
    if (resp.status === 403) {
      result.status = "builtin_immutable";
      result.warnings.push(`task "${params.task_name}" is a builtin — cannot delete`);
      result.ok = true;
      return result;
    }
    if (resp.status === 404) {
      result.status = "not_found";
      result.warnings.push(`task "${params.task_name}" already absent`);
      result.ok = true;
      return result;
    }
    if (!resp.ok) {
      result.errors.push(`DELETE /v1/tasks/${params.task_name} returned HTTP ${resp.status}`);
      return result;
    }
    result.status = "deleted";
    result.ok = true;
    return result;
  } catch (err: any) {
    result.errors.push(`request error: ${err.message}`);
    return result;
  }
}
