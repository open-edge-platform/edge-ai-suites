import { SchemaManager, type SchemaDefinition } from "@smartbuilding-video/db";

export interface UseCaseValidateParams {
  use_case: string;
}

export interface UseCaseValidateDeps {
  /**
   * Loaded use_case_dict from config.yaml. `video_summary_task` and the use
   * case's own `schema` (extension columns for required-field discovery) are
   * read here — schema is owned per use case, not globally.
   */
  useCaseDict: Record<string, { video_summary_task: string; schema?: SchemaDefinition }>;
  /** multilevel-video-understanding service base URL (e.g. http://localhost:8192). */
  summaryServiceUrl: string;
}

export interface UseCaseValidateResult {
  valid: boolean;
  use_case: string;
  video_summary_task?: string;
  checks: {
    use_case_known: boolean;
    task_registered: boolean;
    schema_consistent: boolean;
  };
  required_fields?: string[];
  optional_fields?: string[];
  missing_required_in_prompt?: string[];
  missing_optional_in_prompt?: string[];
  prompt_tail?: string;
  suggestion?: string;
  error?: string;
}

/**
 * One-stop validation of a use_case: existence, summary-service task registration,
 * and prompt ↔ schema consistency.
 *
 * Three sequential checks; the first failure short-circuits the rest.
 * Caller may rely on `valid` for a single yes/no, or read `checks` to know
 * which stage failed.
 */
export async function useCaseValidate(
  params: UseCaseValidateParams,
  deps: UseCaseValidateDeps,
): Promise<UseCaseValidateResult> {
  const checks = {
    use_case_known: false,
    task_registered: false,
    schema_consistent: false,
  };

  // 1. use_case existence
  const ucCfg = deps.useCaseDict[params.use_case];
  if (!ucCfg) {
    return {
      valid: false,
      use_case: params.use_case,
      checks,
      error: `unknown use_case "${params.use_case}". Known: [${Object.keys(deps.useCaseDict).join(", ")}]`,
    };
  }
  checks.use_case_known = true;
  const taskName = ucCfg.video_summary_task;

  // 2. summary-service connectivity + task existence
  let taskBody: any;
  try {
    const resp = await fetch(`${deps.summaryServiceUrl}/v1/tasks/${taskName}`, {
      signal: AbortSignal.timeout(8000),
    });
    if (resp.status === 404) {
      return {
        valid: false, use_case: params.use_case, video_summary_task: taskName, checks,
        error: `task "${taskName}" not registered in multilevel-video-understanding (${deps.summaryServiceUrl}). Register first: POST /v1/tasks`,
      };
    }
    if (!resp.ok) {
      return {
        valid: false, use_case: params.use_case, video_summary_task: taskName, checks,
        error: `failed to verify task "${taskName}": HTTP ${resp.status}`,
      };
    }
    taskBody = await resp.json();
  } catch (err: any) {
    return {
      valid: false, use_case: params.use_case, video_summary_task: taskName, checks,
      error: `summary service unreachable (${deps.summaryServiceUrl}): ${err.message}`,
    };
  }
  checks.task_registered = true;

  // 3. schema consistency: this use case's own required schema fields must appear
  // in LOCAL_PROMPT. Schema is owned per use case, so other use cases' fields
  // never enter this check.
  const extensions = ucCfg.schema?.video_summary_tasks?.extensions ?? [];
  const localPrompt = extractLocalPrompt(taskBody);
  const check = SchemaManager.validatePromptSchema(extensions, localPrompt);
  checks.schema_consistent = check.valid;

  const base = {
    use_case: params.use_case,
    video_summary_task: taskName,
    checks,
    required_fields: check.requiredFields,
    optional_fields: check.optionalFields,
    missing_required_in_prompt: check.missingRequired,
    missing_optional_in_prompt: check.missingOptional,
  };

  if (!checks.schema_consistent) {
    return {
      ...base,
      valid: false,
      prompt_tail: localPrompt.slice(-200),
      suggestion: `Append the following required fields to LOCAL_PROMPT of "${taskName}": ${check.missingRequired.join(", ")}`,
    };
  }

  return { ...base, valid: true };
}

/**
 * Pull LOCAL_PROMPT from the task body. The summary service may expose it under
 * several key paths depending on version; try the common ones and fall back to
 * stringifying the body so substring search still works.
 */
function extractLocalPrompt(taskBody: any): string {
  if (!taskBody || typeof taskBody !== "object") return "";
  return (
    taskBody.LOCAL_PROMPT ??
    taskBody.local_prompt ??
    taskBody.prompts?.LOCAL_PROMPT ??
    taskBody.prompts?.local_prompt ??
    JSON.stringify(taskBody)
  );
}
