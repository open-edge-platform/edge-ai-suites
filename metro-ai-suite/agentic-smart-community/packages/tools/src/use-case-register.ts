import { execFile } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { promisify } from "node:util";
import { parseDocument, isMap } from "yaml";
import { SchemaManager, type SchemaExtension } from "@smartbuilding-video/db";
import type { UseCaseValidateResult } from "./use-case-validate.js";
import { useCaseValidate } from "./use-case-validate.js";

export interface UseCaseRegisterParams {
  action: "register" | "unregister";
  use_case: string;
  video_summary_task?: string;
  description?: string;
  evaluate_rules_path?: string;
  reports?: Record<string, unknown>;
  summarize?: Record<string, unknown>;
  prompt_text?: string;
  schema_extensions?: SchemaExtension[];
  overwrite?: boolean;
  /**
   * When true, mirror the mutation to `deps.configPath` on disk (comment-
   * preserving via yaml.Document). Requires deps.configPath to be set.
   * Failure writing does NOT fail the whole call — it is surfaced as a
   * warning + `steps.config_yaml: "skipped"` so the in-memory registration
   * still stands.
   */
  persist?: boolean;
}

export interface UseCaseRegisterDeps {
  useCaseDict: Record<string, any>;
  summaryServiceUrl: string;
  db: any;
  /**
   * Absolute path to the config.yaml the server was booted from. Required
   * when the caller passes `persist: true`. When undefined, persist requests
   * degrade to `steps.config_yaml: "skipped"` with a warning.
   */
  configPath?: string;
  /**
   * Root directory that holds `use-cases/<use_case>/{prompt.md,evaluate_rules.py}`.
   * When `prompt_text` / `evaluate_rules_path` are omitted, register auto-picks
   * these conventional files. Defaults to `process.cwd()` when unset.
   */
  baseDir?: string;
}

export interface UseCaseRegisterResult {
  action: "register" | "unregister";
  use_case: string;
  ok: boolean;
  steps: {
    use_case_dict?: "added" | "updated" | "removed" | "skipped";
    vlm_task?: "registered" | "updated" | "unchanged" | "deleted" | "skipped";
    schema?: {
      added: string[];
      warnings: string[];
    };
    validate?: UseCaseValidateResult;
    config_yaml?: "written" | "removed" | "skipped";
  };
  warnings: string[];
  errors: string[];
}

const TASK_NAME_RE = /^[a-z][a-z0-9_]{1,63}$/;
const VLM_BUILTIN_TASKS = new Set([
  "summary",
  "summary_zh",
]);
const execFileAsync = promisify(execFile);

export async function useCaseRegister(
  params: UseCaseRegisterParams,
  deps: UseCaseRegisterDeps,
): Promise<UseCaseRegisterResult> {
  const result: UseCaseRegisterResult = {
    action: params.action,
    use_case: params.use_case,
    ok: false,
    steps: {},
    warnings: [],
    errors: [],
  };

  if (!params.use_case || !TASK_NAME_RE.test(params.use_case)) {
    result.errors.push(`use_case "${params.use_case}" must match ${TASK_NAME_RE}`);
    return result;
  }

  if (params.action === "unregister") {
    return await unregister(params, deps, result);
  }

  const taskName = params.video_summary_task ?? `${params.use_case}_monitor`;
  if (!TASK_NAME_RE.test(taskName)) {
    result.errors.push(`video_summary_task "${taskName}" must match ${TASK_NAME_RE}`);
    return result;
  }
  if (VLM_BUILTIN_TASKS.has(taskName)) {
    result.errors.push(
      `video_summary_task "${taskName}" is a VLM builtin (immutable); pick a different name`,
    );
    return result;
  }

  const alreadyExists = params.use_case in deps.useCaseDict;
  if (alreadyExists && !params.overwrite) {
    result.errors.push(
      `use_case "${params.use_case}" already exists in use_case_dict; pass overwrite=true to replace`,
    );
    return result;
  }

  if (params.schema_extensions && params.schema_extensions.length > 0) {
    try {
      // ALTER the shared video_summary_tasks table (idempotent). The fields
      // belong to THIS use case only — they are carried on the use_case_dict
      // entry (entry.schema) below, never merged into any global schema.
      const schemaMgr = new SchemaManager(deps.db);
      const applied = schemaMgr.applySchema({
        video_summary_tasks: { extensions: params.schema_extensions },
      });
      result.steps.schema = { added: applied.added, warnings: applied.warnings };
    } catch (err: any) {
      result.errors.push(`schema apply failed: ${err.message}`);
      return result;
    }
  }

  // prompt_text resolution — convention over configuration. When the caller
  // doesn't pass prompt_text explicitly, auto-read the conventional prompt file
  // use-cases/<use_case>/prompt.md so agents only need to drop the file (via the
  // video-summary-prompt-studio skill) rather than re-cat it into the call.
  const baseDir = deps.baseDir ?? process.cwd();
  let promptText = params.prompt_text;
  let promptSource = "param";
  if (!promptText) {
    const conv = join(baseDir, "use-cases", params.use_case, "prompt.md");
    if (existsSync(conv)) {
      promptText = readFileSync(conv, "utf-8");
      promptSource = conv;
    }
  }

  if (promptText) {
    try {
      const vlmStep = await registerVlmTask(
        deps.summaryServiceUrl,
        taskName,
        promptText,
        params.description ?? `Dynamically registered use_case ${params.use_case}`,
      );
      result.steps.vlm_task = vlmStep;
      if (promptSource !== "param") {
        result.warnings.push(`prompt_text auto-read from ${promptSource}`);
      }
    } catch (err: any) {
      result.errors.push(`VLM task registration failed: ${err.message}`);
      return result;
    }
  } else {
    // No prompt anywhere → the VLM task can't be registered, so the use case
    // would be unusable (task-poller would hit HTTP 400). Fail loudly instead of
    // persisting a half-baked entry.
    result.errors.push(
      `prompt_text not provided and no use-cases/${params.use_case}/prompt.md found — ` +
      `generate the prompt first (video-summary-prompt-studio skill) or pass prompt_text.`,
    );
    return result;
  }

  // evaluate_rules_path resolution — same convention: auto-pick
  // use-cases/<use_case>/evaluate_rules.py when present and not passed explicitly.
  let evaluateRulesPath = params.evaluate_rules_path;
  if (!evaluateRulesPath) {
    const conv = join(baseDir, "use-cases", params.use_case, "evaluate_rules.py");
    if (existsSync(conv)) evaluateRulesPath = conv;
  }
  if (evaluateRulesPath) {
    const error = await validateEvaluateRulesOverride(
      params.use_case,
      evaluateRulesPath,
      params.schema_extensions ?? [],
    );
    if (error) {
      result.errors.push(error);
      return result;
    }
  }

  // Fill defaults for optional config so a minimal (name + description) register
  // still persists a complete entry, consistent with the other built-in UCs.
  const entry: any = {
    video_summary_task: taskName,
  };
  entry.description = params.description ?? `${params.use_case} use case`;
  if (evaluateRulesPath !== undefined) entry.evaluate_rules_path = evaluateRulesPath;
  entry.reports = params.reports ?? { data_source: "alerts", default_type: "daily", filter: {} };
  entry.summarize = params.summarize ?? {
    method: "SIMPLE",
    processor_kwargs: { levels: 1, level_sizes: [-1], process_fps: 2 },
  };
  // Schema is owned by THIS use case: carry the declared extension columns on the
  // entry (persisted with it). No global shared schema — each use case's pipeline
  // parses only the fields it declares here.
  if (params.schema_extensions && params.schema_extensions.length > 0) {
    entry.schema = {
      video_summary_tasks: { extensions: params.schema_extensions },
      custom_tables: [],
    };
  }

  deps.useCaseDict[params.use_case] = entry;
  result.steps.use_case_dict = alreadyExists ? "updated" : "added";

  if (params.persist) {
    result.steps.config_yaml = persistUseCaseDictEntry(
      deps.configPath,
      params.use_case,
      entry,
      result.warnings,
    );
  }

  try {
    result.steps.validate = await useCaseValidate(
      { use_case: params.use_case },
      {
        useCaseDict: deps.useCaseDict,
        summaryServiceUrl: deps.summaryServiceUrl,
      },
    );
    if (!result.steps.validate.valid) {
      result.warnings.push(
        `post-register validate failed: ${result.steps.validate.error ?? result.steps.validate.suggestion ?? "unknown"}`,
      );
    }
  } catch (err: any) {
    result.warnings.push(`post-register validate error: ${err.message}`);
  }

  result.ok = result.errors.length === 0;
  return result;
}

async function validateEvaluateRulesOverride(
  useCase: string,
  overridePath: string,
  schemaExtensions: SchemaExtension[],
): Promise<string | null> {
  const smokeFields = buildEvaluateRulesSmokeFields(schemaExtensions);

  try {
    const { stdout } = await execFileAsync("python3", [
      "-S",
      overridePath,
      JSON.stringify(smokeFields),
    ], { timeout: 10_000 });
    const text = stdout.trim();
    const parsed = text ? JSON.parse(text) : null;
    if (parsed === null) return null;
    if (!parsed || typeof parsed !== "object") {
      return `evaluate_rules_path "${overridePath}" must print JSON object or null`;
    }
    if (typeof parsed.alertType !== "string" || typeof parsed.severity !== "string") {
      return `evaluate_rules_path "${overridePath}" must return {alertType, severity, description?} or null`;
    }
    return null;
  } catch (err: any) {
    return `evaluate_rules_path "${overridePath}" failed smoke test: ${err.message}`;
  }
}

function buildEvaluateRulesSmokeFields(schemaExtensions: SchemaExtension[]): Record<string, string | number> {
  if (schemaExtensions.length === 0) {
    return {
      severity: "info",
      event: "no_incident",
      desc: "validation smoke",
    };
  }

  const fields: Record<string, string | number> = {};
  for (const ext of schemaExtensions) {
    if (ext.name === "severity") fields[ext.name] = "info";
    else if (ext.name === "event") fields[ext.name] = "no_incident";
    else if (ext.name === "desc" || ext.name === "description") fields[ext.name] = "validation smoke";
    else if (ext.type === "integer" || ext.type === "real") fields[ext.name] = 0;
    else fields[ext.name] = "false";
  }
  return fields;
}

async function unregister(
  params: UseCaseRegisterParams,
  deps: UseCaseRegisterDeps,
  result: UseCaseRegisterResult,
): Promise<UseCaseRegisterResult> {
  const cfg = deps.useCaseDict[params.use_case];
  if (!cfg) {
    result.errors.push(`use_case "${params.use_case}" not found in use_case_dict`);
    return result;
  }

  const taskName: string = cfg.video_summary_task;

  try {
    const resp = await fetch(`${deps.summaryServiceUrl}/v1/tasks/${taskName}`, {
      method: "DELETE",
      signal: AbortSignal.timeout(5000),
    });
    if (resp.status === 403) {
      result.warnings.push(
        `VLM task "${taskName}" is a builtin (immutable) — not deleted; use_case_dict entry still removed`,
      );
      result.steps.vlm_task = "skipped";
    } else if (resp.status === 404) {
      result.warnings.push(`VLM task "${taskName}" already absent`);
      result.steps.vlm_task = "skipped";
    } else if (!resp.ok) {
      result.warnings.push(`VLM task "${taskName}" delete returned HTTP ${resp.status}`);
      result.steps.vlm_task = "skipped";
    } else {
      result.steps.vlm_task = "deleted";
    }
  } catch (err: any) {
    result.warnings.push(`VLM task delete error: ${err.message}`);
    result.steps.vlm_task = "skipped";
  }

  delete deps.useCaseDict[params.use_case];
  result.steps.use_case_dict = "removed";

  if (params.persist) {
    result.steps.config_yaml = persistUseCaseDictEntry(
      deps.configPath,
      params.use_case,
      null,
      result.warnings,
    );
  }

  result.ok = true;
  return result;
}

/**
 * Mirror an in-memory use_case_dict mutation to `configPath` on disk.
 * Uses yaml.Document API so comments and field ordering are preserved.
 * `entry === null` → deleteIn (unregister). Non-throwing: on any error,
 * pushes to warnings and returns "skipped".
 */
function persistUseCaseDictEntry(
  configPath: string | undefined,
  useCase: string,
  entry: Record<string, unknown> | null,
  warnings: string[],
): "written" | "removed" | "skipped" {
  if (!configPath) {
    warnings.push("persist requested but configPath is unset (server booted without --config?); skipped");
    return "skipped";
  }
  try {
    const raw = readFileSync(configPath, "utf-8");
    const doc = parseDocument(raw);
    // Ensure `use_case_dict:` top-level key exists as a mapping.
    const existing = doc.get("use_case_dict");
    if (!existing || !isMap(existing)) {
      doc.set("use_case_dict", doc.createNode({}));
    }
    if (entry === null) {
      doc.deleteIn(["use_case_dict", useCase]);
    } else {
      doc.setIn(["use_case_dict", useCase], entry);
    }
    writeFileSync(configPath, doc.toString(), "utf-8");
    return entry === null ? "removed" : "written";
  } catch (err: any) {
    warnings.push(`persist to ${configPath} failed: ${err.message}`);
    return "skipped";
  }
}

async function registerVlmTask(
  baseUrl: string,
  taskName: string,
  promptText: string,
  description: string,
): Promise<"registered" | "updated" | "unchanged"> {
  const content = { text: buildPromptContent(promptText) };
  const body = {
    task_name: taskName,
    mode: "full",
    description,
    content,
  };

  const postResp = await fetch(`${baseUrl}/v1/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(10000),
  });

  if (postResp.status === 201 || postResp.status === 200) {
    return "registered";
  }

  if (postResp.status === 409) {
    const patchResp = await fetch(`${baseUrl}/v1/tasks/${taskName}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: "full", description, content }),
      signal: AbortSignal.timeout(10000),
    });
    if (!patchResp.ok) {
      let detail: string;
      try { detail = JSON.stringify(await patchResp.json()); }
      catch { detail = patchResp.statusText; }
      throw new Error(`PATCH /v1/tasks/${taskName} HTTP ${patchResp.status}: ${detail.slice(0, 300)}`);
    }
    return "updated";
  }

  let detail: string;
  try { detail = JSON.stringify(await postResp.json()); }
  catch { detail = postResp.statusText; }
  throw new Error(`POST /v1/tasks HTTP ${postResp.status}: ${detail.slice(0, 300)}`);
}

function buildPromptContent(raw: string): string {
  if (/GLOBAL_PROMPT\s*=|LOCAL_PROMPT\s*=/.test(raw)) {
    return raw;
  }
  const sections = parseMarkdownSections(raw);
  const local = sections.LOCAL_PROMPT ?? "";
  const global = sections.GLOBAL_PROMPT ?? local;
  const macro = sections.MACRO_CHUNK_PROMPT ??
    "Merge sub-chunks into a window narrative. Start time: {st_tm}s, End time: {end_tm}s. User question: {question}";
  const tminus = sections.T_MINUS_1_PROMPT ??
    "Previous {dur}s summary below; do not copy. Start time: {st_tm}s, End time: {end_tm}s. {past_summary}";

  const q = "'''";
  return (
    `GLOBAL_PROMPT = ${q}${global}${q}\n\n` +
    `MACRO_CHUNK_PROMPT = ${q}${macro}${q}\n\n` +
    `LOCAL_PROMPT = ${q}${local}${q}\n\n` +
    `T_MINUS_1_PROMPT = ${q}${tminus}${q}\n`
  );
}

function parseMarkdownSections(md: string): Record<string, string> {
  const out: Record<string, string> = {};
  let current: string | null = null;
  let buf: string[] = [];
  for (const line of md.split(/\r?\n/)) {
    const m = /^##\s+([A-Z0-9_]+)\s*$/.exec(line);
    if (m) {
      if (current) out[current] = buf.join("\n").trim();
      current = m[1];
      buf = [];
    } else if (current !== null) {
      buf.push(line);
    }
  }
  if (current) out[current] = buf.join("\n").trim();
  return out;
}
