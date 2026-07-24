import { execFile } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { promisify } from "node:util";
import { parseDocument, isMap, Scalar } from "yaml";
import { SchemaManager, type SchemaExtension } from "@smartbuilding-video/db";
import type { UseCaseValidateResult } from "./use-case-validate.js";
import { useCaseValidate } from "./use-case-validate.js";

export interface UseCaseRegisterParams {
  action: "register" | "register_task" | "unregister";
  use_case: string;
  video_summary_task?: string;
  description?: string;
  evaluate_rules_path?: string;
  reports?: Record<string, unknown>;
  summarize?: Record<string, unknown>;
  prompt_text?: string;
  evaluate_rules_text?: string;
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
  action: "register" | "register_task" | "unregister";
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
    consistency?: ConsistencyReport;
    config_yaml?: "written" | "removed" | "skipped";
    artifacts?: {
      prompt_md?: "written" | "unchanged" | "skipped";
      evaluate_rules_py?: "written" | "unchanged" | "skipped";
    };
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

// video-summary (multilevel) only accepts these summarization methods. Anything
// else (notably the literal "default" some callers guess at) makes /v1/summary
// return HTTP 400 and silently fails the whole pipeline. See VLM error:
// "Unsupported summarization method: default, choices: [...]".
const VALID_SUMMARIZE_METHODS = ["SIMPLE", "USE_VLM_T-1", "USE_LLM_T-1", "USE_ALL_T-1"] as const;
const DEFAULT_PROCESSOR_KWARGS = { levels: 1, level_sizes: [-1], process_fps: 2 };

interface PromptOutputField {
  name: string;
  required: boolean;
}

/**
 * Normalize a caller-supplied `summarize` block into something the VLM will
 * accept, so a mis-guessed method (e.g. "default") can never poison the
 * use_case_dict entry. Illegal / missing method → fall back to "SIMPLE";
 * empty / missing processor_kwargs → fill the canonical defaults. Every
 * correction is surfaced as a warning. This is the deterministic backstop the
 * skill-layer guidance cannot guarantee on its own.
 */
function normalizeSummarize(
  input: Record<string, unknown> | undefined,
  warnings: string[],
): Record<string, unknown> {
  const raw = input && typeof input === "object" ? { ...input } : {};
  let method = typeof raw.method === "string" ? raw.method : undefined;
  if (!method || !(VALID_SUMMARIZE_METHODS as readonly string[]).includes(method)) {
    if (method) {
      warnings.push(
        `summarize.method "${method}" is not one of [${VALID_SUMMARIZE_METHODS.join(", ")}] — falling back to "SIMPLE"`,
      );
    }
    method = "SIMPLE";
  }
  const pk = raw.processor_kwargs;
  const processor_kwargs =
    pk && typeof pk === "object" && Object.keys(pk).length > 0 ? pk : { ...DEFAULT_PROCESSOR_KWARGS };
  return { ...raw, method, processor_kwargs };
}

/**
 * Extract the LOCAL_PROMPT output-contract fields — the UPPER_SNAKE `KEY:` lines the
 * skill mandates under `## 输出格式` (`SEVERITY:` / `EVENT:` / `PET_ZONE:` …) —
 * lowercased and deduped, with `required` inferred from a 可选/optional marker on the
 * line. It keys off the `KEY:` line shape rather than a specific heading, so it is
 * robust across authoring styles; lines like `Start time:` or `开始时间:` are not
 * all-caps ASCII and never match.
 *
 * This is the SINGLE source of truth for both the schema↔prompt consistency gate
 * (field names) and prompt-based schema inference (names + required), so an inferred
 * schema is, by construction, the same set the gate checks — letting a caller omit
 * `schema_extensions` entirely and derive the final schema from the prompt.
 */
function extractPromptOutputFields(promptText: string): PromptOutputField[] {
  const sections = parseMarkdownSections(promptText);
  const localPrompt = sections.LOCAL_PROMPT ?? promptText;
  const fields = new Map<string, PromptOutputField>();
  for (const line of localPrompt.split(/\r?\n/)) {
    const match = /^\s*([A-Z][A-Z0-9_]*)\s*:/.exec(line);
    if (!match) continue;
    const name = match[1].toLowerCase();
    if (fields.has(name)) continue;
    fields.set(name, { name, required: !/(可选|optional)/i.test(line) });
  }
  return [...fields.values()];
}

function inferSchemaExtensionsFromPrompt(promptFields: PromptOutputField[]): SchemaExtension[] {
  return promptFields.map((field) => ({
    name: field.name,
    type: "text",
    required: field.required,
  }));
}

/**
 * Result of the schema↔prompt↔rules consistency gate. `consistent` is the single
 * yes/no; the arrays are an actionable diff the caller (skill/LLM) can act on.
 */
export interface ConsistencyReport {
  consistent: boolean;
  /** UPPER `KEY:` output-contract keys found in LOCAL_PROMPT (lowercased). */
  prompt_fields: string[];
  /** Declared schema_extensions names (lowercased). */
  schema_fields: string[];
  /** schema fields absent from LOCAL_PROMPT's output contract. */
  missing_in_prompt: string[];
  /** LOCAL_PROMPT output fields not declared in the normalized final schema. */
  extra_in_prompt: string[];
  /** JSON-output requests / reserved tokens found in LOCAL_PROMPT. */
  format_violations: string[];
  /** default-rule path: severity/event/desc missing from schema. */
  default_path_missing_fields: string[];
  /** custom-rule path: fields evaluate_rules.py reads that aren't in schema. */
  rule_fields_not_in_schema: string[];
}

/** Fields defaultRuleEvaluator needs to fire (see rule-engine/index.ts). */
const DEFAULT_ALERT_FIELDS = ["severity", "event", "desc"];
const DEFAULT_ALERT_SCHEMA_EXTENSIONS: SchemaExtension[] = [
  { name: "severity", type: "text", required: false },
  { name: "event", type: "text", required: true },
  { name: "desc", type: "text", required: true },
];
/** Legacy field aliases evaluate_rules.py may read interchangeably. */
const RULE_FIELD_ALIASES: Record<string, string> = { description: "desc" };

function normalizeFinalSchemaExtensions(schemaExtensions: SchemaExtension[]): SchemaExtension[] {
  if (schemaExtensions.length === 0) return [];

  const byName = new Map<string, SchemaExtension>();
  for (const ext of DEFAULT_ALERT_SCHEMA_EXTENSIONS) {
    byName.set(ext.name, ext);
  }
  for (const ext of schemaExtensions) {
    const name = ext.name.toLowerCase();
    byName.set(name, { ...ext, name });
  }
  return [...byName.values()];
}

/**
 * Static-scan an evaluate_rules.py source for the parsed-field keys it reads via
 * `fields.get("x")` — the idiom the skill template and every bundled adapter use.
 * Keys are constrained to lowercase snake_case (schema convention), and `.get`
 * preceded by `environ` is excluded so `os.environ.get(...)` config reads (e.g.
 * elder_wakeup) are not mistaken for schema fields. Bracket access (`d["x"]`) is
 * deliberately NOT scanned: in Python it also indexes constant dicts (e.g.
 * `SEVERITY_ORDER["warn"]`), so scanning it would false-flag non-field literals.
 */
function scanRuleFieldKeys(src: string): string[] {
  const keys = new Set<string>();
  const getRe = /(?<!environ)\.get\(\s*["']([a-z][a-z0-9_]*)["']/g;
  let m: RegExpExecArray | null;
  while ((m = getRe.exec(src))) keys.add(m[1]);
  return [...keys];
}

/**
 * Schema-agnostic format gate for LOCAL_PROMPT. Flags (a) requests to emit JSON
 * and (b) reserved tokens the VLM `POST /v1/tasks` rejects (```` ``` ````, `<<<`).
 * JSON detection is **prohibition-aware**: a compliant prompt's `##禁止事项`
 * legitimately says "不要输出JSON格式", so a line that also carries a negation
 * (不要 / 禁止 / no / don't …) is NOT flagged. Square brackets are deliberately
 * allowed — the T_MINUS_1 envelope uses `[ ]`.
 */
function detectFormatViolations(promptText: string): string[] {
  const violations: string[] = [];
  const content = buildPromptContent(promptText);
  for (const token of ["```", "<<<"]) {
    if (content.includes(token)) {
      violations.push(`reserved token ${JSON.stringify(token)} (VLM POST /v1/tasks returns 422)`);
    }
  }
  const sections = parseMarkdownSections(promptText);
  const local = sections.LOCAL_PROMPT ?? promptText;
  const NEG = /不要|禁止|勿|别|不得|no\b|not\b|never|don'?t|avoid/i;
  const JSON_REQUEST =
    /(返回|输出|生成|以).{0,6}json|json\s*格式|\bas\s+json\b|\bin\s+json\b|\bjson\s+(object|format|output|array)\b|respond[^\n]{0,20}json/i;
  for (const line of local.split(/\r?\n/)) {
    if (JSON_REQUEST.test(line) && !NEG.test(line)) {
      violations.push("LOCAL_PROMPT asks for JSON output; use plain `KEY: value` lines instead");
      break;
    }
  }
  if (/\{\s*["'][A-Za-z0-9_]+["']\s*:/.test(local)) {
    violations.push("LOCAL_PROMPT contains a JSON object literal; emit one `KEY: value` line per schema field");
  }
  return violations;
}

/**
 * The schema↔prompt↔rules consistency gate. The normalized final schema is the
 * source of truth; the prompt's UPPER `KEY:` output contract must be the exact
 * same set, the prompt must not request JSON / reserved tokens, and the alert-rule
 * path must be coherent (default path needs severity/event/desc in schema; custom
 * rule may only read declared fields). Pure/stateless — no I/O — so register calls
 * it before any side effect and tests can exercise it directly.
 */
export function checkUseCaseConsistency(input: {
  promptText: string;
  schemaExtensions: SchemaExtension[];
  evaluateRulesText?: string;
}): ConsistencyReport {
  const { promptText, schemaExtensions, evaluateRulesText } = input;
  const schema_fields = schemaExtensions.map((e) => e.name.toLowerCase());
  const schemaSet = new Set(schema_fields);
  const prompt_fields = extractPromptOutputFields(promptText).map((f) => f.name);
  const promptSet = new Set(prompt_fields);
  const format_violations = detectFormatViolations(promptText);

  // G1 — report-only: an empty schema is legal only when the prompt declares no
  // output KEY lines (fridge). A prompt that emits fields but declares no schema
  // would silently drop them, so that is reported as extra_in_prompt.
  if (schemaExtensions.length === 0) {
    return {
      consistent: format_violations.length === 0 && prompt_fields.length === 0,
      prompt_fields,
      schema_fields,
      missing_in_prompt: [],
      extra_in_prompt: prompt_fields,
      format_violations,
      default_path_missing_fields: [],
      rule_fields_not_in_schema: [],
    };
  }

  // G2 + G2b — exact set equality between schema and the prompt output contract.
  const missing_in_prompt = schema_fields.filter((f) => !promptSet.has(f));
  const extra_in_prompt = prompt_fields.filter((f) => !schemaSet.has(f));

  // G4 — alert-rule path.
  let default_path_missing_fields: string[] = [];
  let rule_fields_not_in_schema: string[] = [];
  if (evaluateRulesText === undefined) {
    default_path_missing_fields = DEFAULT_ALERT_FIELDS.filter((f) => !schemaSet.has(f));
  } else {
    rule_fields_not_in_schema = scanRuleFieldKeys(evaluateRulesText).filter((k) => {
      const canonical = RULE_FIELD_ALIASES[k] ?? k;
      return !schemaSet.has(canonical) && !schemaSet.has(k);
    });
  }

  const consistent =
    missing_in_prompt.length === 0 &&
    extra_in_prompt.length === 0 &&
    format_violations.length === 0 &&
    default_path_missing_fields.length === 0 &&
    rule_fields_not_in_schema.length === 0;

  return {
    consistent,
    prompt_fields,
    schema_fields,
    missing_in_prompt,
    extra_in_prompt,
    format_violations,
    default_path_missing_fields,
    rule_fields_not_in_schema,
  };
}

/** Render a failing ConsistencyReport into actionable error strings for the caller. */
function consistencyErrors(r: ConsistencyReport): string[] {
  const errs: string[] = [];
  if (r.format_violations.length > 0) {
    errs.push(`prompt format violation(s): ${r.format_violations.join("; ")}.`);
  }
  if (r.missing_in_prompt.length > 0 || r.extra_in_prompt.length > 0) {
    errs.push(
      `schema↔prompt mismatch: LOCAL_PROMPT output fields [${r.prompt_fields.join(", ") || "none"}] ` +
      `must exactly match final schema [${r.schema_fields.join(", ") || "none"}]. ` +
      `Missing in prompt: [${r.missing_in_prompt.join(", ") || "none"}]. ` +
      `Extra in prompt: [${r.extra_in_prompt.join(", ") || "none"}].`,
    );
  }
  if (r.default_path_missing_fields.length > 0) {
    errs.push(
      `default rule path needs schema field(s) [${r.default_path_missing_fields.join(", ")}] ` +
      `— with no evaluate_rules.py, defaultRuleEvaluator requires severity/event/desc.`,
    );
  }
  if (r.rule_fields_not_in_schema.length > 0) {
    errs.push(
      `evaluate_rules.py reads field(s) [${r.rule_fields_not_in_schema.join(", ")}] not declared in final schema.`,
    );
  }
  if (errs.length > 0) errs.push("No changes were applied.");
  return errs;
}

function ensureArtifactsStep(result: UseCaseRegisterResult): NonNullable<UseCaseRegisterResult["steps"]["artifacts"]> {
  if (!result.steps.artifacts) result.steps.artifacts = {};
  return result.steps.artifacts;
}

function writeTextArtifact(
  path: string,
  content: string | undefined,
  overwrite: boolean | undefined,
  warnings: string[],
): "written" | "unchanged" | "skipped" {
  if (content === undefined) return "skipped";
  if (existsSync(path)) {
    const current = readFileSync(path, "utf-8");
    if (current === content) return "unchanged";
    if (!overwrite) {
      throw new Error(`${path} already exists; pass overwrite=true to replace it`);
    }
  }
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, content.endsWith("\n") ? content : `${content}\n`, "utf-8");
  warnings.push(`artifact written: ${path}`);
  return "written";
}

function validateTextArtifactWritable(
  path: string,
  content: string | undefined,
  overwrite: boolean | undefined,
): string | null {
  if (content === undefined || !existsSync(path)) return null;
  const current = readFileSync(path, "utf-8");
  if (current === content) return null;
  if (overwrite) return null;
  return `${path} already exists; pass overwrite=true to replace it`;
}

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

  if (params.action === "register_task") {
    return await registerTaskOnly(params, deps, result);
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

  // prompt_text resolution — convention over configuration. When the caller
  // doesn't pass prompt_text explicitly, auto-read the conventional prompt file
  // use-cases/<use_case>/prompt.md so agents only need to drop the file (via the
  // video-summary-prompt-studio skill) rather than re-cat it into the call.
  //
  // Resolved up-front, BEFORE any side effect (ALTER / VLM POST / config write),
  // so both the "no prompt" and the "schema↔prompt mismatch" gates below can
  // reject with zero changes applied.
  const baseDir = deps.baseDir ?? process.cwd();
  const useCaseDir = join(baseDir, "use-cases", params.use_case);
  const promptPath = join(useCaseDir, "prompt.md");
  const evaluateRulesTextPath = join(useCaseDir, "evaluate_rules.py");
  let promptText = params.prompt_text;
  let promptSource = "param";
  if (!promptText) {
    const conv = join(baseDir, "use-cases", params.use_case, "prompt.md");
    if (existsSync(conv)) {
      promptText = readFileSync(conv, "utf-8");
      promptSource = conv;
    }
  }
  if (!promptText) {
    // No prompt anywhere → the VLM task can't be registered, so the use case
    // would be unusable (task-poller would hit HTTP 400). Fail loudly instead of
    // persisting a half-baked entry.
    result.errors.push(
      `prompt_text not provided and no use-cases/${params.use_case}/prompt.md found — ` +
      `do NOT retry register with the same empty args. Call action="register_task" first ` +
      `(it registers the VLM task and writes use-cases/${params.use_case}/prompt.md to disk), ` +
      `then retry action="register" (prompt_text may then be omitted; it is auto-read from disk). ` +
      `Alternatively pass prompt_text directly.`,
    );
    return result;
  }

  // Resolve the evaluate_rules source up-front (before any side effect) so the
  // consistency gate below can static-scan the rule's field access (G4), and so the
  // wiring step later reuses the same resolved path instead of re-deriving it.
  let evaluateRulesPath = params.evaluate_rules_path;
  if (!evaluateRulesPath && params.evaluate_rules_text !== undefined) {
    evaluateRulesPath = evaluateRulesTextPath;
  }
  if (!evaluateRulesPath && existsSync(evaluateRulesTextPath)) {
    evaluateRulesPath = evaluateRulesTextPath;
  }
  let evaluateRulesText = params.evaluate_rules_text;
  if (evaluateRulesText === undefined && evaluateRulesPath && existsSync(evaluateRulesPath)) {
    evaluateRulesText = readFileSync(evaluateRulesPath, "utf-8");
  }

  if (params.persist) {
    const artifactErrors = [
      validateTextArtifactWritable(promptPath, params.prompt_text, params.overwrite),
      validateTextArtifactWritable(evaluateRulesTextPath, params.evaluate_rules_text, params.overwrite),
    ].filter((err): err is string => Boolean(err));
    if (artifactErrors.length > 0) {
      result.errors.push(`artifact persist failed: ${artifactErrors.join("; ")}`);
      return result;
    }
  }

  const suppliedSchemaExtensions = params.schema_extensions && params.schema_extensions.length > 0
    ? params.schema_extensions
    : inferSchemaExtensionsFromPrompt(extractPromptOutputFields(promptText));
  const schemaExtensions = normalizeFinalSchemaExtensions(suppliedSchemaExtensions);
  if ((!params.schema_extensions || params.schema_extensions.length === 0) && schemaExtensions.length > 0) {
    result.warnings.push(
      `schema_extensions auto-derived from LOCAL_PROMPT output fields: ${schemaExtensions.map((e) => e.name).join(", ")}`,
    );
  }
  const suppliedNames = new Set(suppliedSchemaExtensions.map((e) => e.name.toLowerCase()));
  const normalizedBaseFields = DEFAULT_ALERT_FIELDS.filter((name) => schemaExtensions.some((e) => e.name === name) && !suppliedNames.has(name));
  if (params.schema_extensions && params.schema_extensions.length > 0 && normalizedBaseFields.length > 0) {
    result.warnings.push(
      `schema_extensions treated as extra fields; added default alert field(s): ${normalizedBaseFields.join(", ")}`,
    );
  }

  // Pre-flight schema↔prompt↔rules consistency — the HARD gate, runs BEFORE any
  // side effect (no ALTER, no VLM POST, no config write). The normalized final
  // schema is the source of truth: LOCAL_PROMPT's UPPER `KEY:` output contract
  // must be the exact same set, the prompt must not request JSON / reserved tokens,
  // and the alert-rule path must be coherent. An inconsistent use case is rejected
  // here with an actionable diff instead of silently never alerting.
  const consistency = checkUseCaseConsistency({ promptText, schemaExtensions, evaluateRulesText });
  result.steps.consistency = consistency;
  if (!consistency.consistent) {
    result.errors.push(...consistencyErrors(consistency));
    return result;
  }

  if (schemaExtensions.length > 0) {
    try {
      // ALTER the shared video_summary_tasks table (idempotent). The fields
      // belong to THIS use case only — they are carried on the use_case_dict
      // entry (entry.schema) below, never merged into any global schema.
      const schemaMgr = new SchemaManager(deps.db);
      const applied = schemaMgr.applySchema({
        video_summary_tasks: { extensions: schemaExtensions },
      });
      result.steps.schema = { added: applied.added, warnings: applied.warnings };
    } catch (err: any) {
      result.errors.push(`schema apply failed: ${err.message}`);
      return result;
    }
  }

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

  if (params.persist && (params.prompt_text !== undefined || params.evaluate_rules_text !== undefined)) {
    try {
      const artifacts = ensureArtifactsStep(result);
      artifacts.prompt_md = writeTextArtifact(
        promptPath,
        params.prompt_text,
        params.overwrite,
        result.warnings,
      );
      artifacts.evaluate_rules_py = writeTextArtifact(
        evaluateRulesTextPath,
        params.evaluate_rules_text,
        params.overwrite,
        result.warnings,
      );
    } catch (err: any) {
      result.errors.push(`artifact persist failed: ${err.message}`);
      return result;
    }
  }

  // evaluate_rules smoke test — the path/source were resolved up-front (before the
  // consistency gate); here we execute the script once to confirm it runs and
  // returns a well-formed AlertOutcome / null.
  if (evaluateRulesPath) {
    const error = await validateEvaluateRulesOverride(
      params.use_case,
      evaluateRulesPath,
      schemaExtensions,
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
  // Never trust the caller's method verbatim — normalize so an illegal value
  // (e.g. "default") can't get persisted and later 400 every summary request.
  entry.summarize = normalizeSummarize(params.summarize, result.warnings);
  // Schema is owned by THIS use case: carry the declared extension columns on the
  // entry (persisted with it). No global shared schema — each use case's pipeline
  // parses only the fields it declares here.
  if (schemaExtensions.length > 0) {
    entry.schema = {
      video_summary_tasks: { extensions: schemaExtensions },
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

/**
 * Phase 1 of the two-step registration flow: register the VLM summary task from an
 * inline `prompt_text`, and — only after the task registers successfully — persist
 * `prompt.md` (+ `evaluate_rules.py`) to `use-cases/<uc>/`. It does NOT touch the DB
 * schema, `use_case_dict`, or `config.yaml`; those are phase 2 (`action="register"`,
 * which can then omit `prompt_text` and auto-read the files this step wrote).
 *
 * Splitting registration this way confines the large `prompt_text` argument to a
 * single call: once phase 1 lands the files on disk, phase 2 and every later tool
 * read from disk, so an agent that intermittently fails to inline the big prompt no
 * longer bounces `register` forever (see the phase-2 "no prompt" error in
 * useCaseRegister).
 */
async function registerTaskOnly(
  params: UseCaseRegisterParams,
  deps: UseCaseRegisterDeps,
  result: UseCaseRegisterResult,
): Promise<UseCaseRegisterResult> {
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

  // prompt_text is mandatory here — register_task is the one place the full prompt is
  // supplied. It deliberately does NOT auto-read use-cases/<uc>/prompt.md (that is
  // phase 2's job); a missing prompt is a terminal error, not a silent bounce.
  const promptText = params.prompt_text;
  if (!promptText) {
    result.errors.push(
      `action="register_task" requires prompt_text (the full 4-section prompt) — it does ` +
      `not auto-read from disk. Pass prompt_text; on success it is POSTed to the VLM ` +
      `service and written to use-cases/${params.use_case}/prompt.md.`,
    );
    return result;
  }

  const baseDir = deps.baseDir ?? process.cwd();
  const useCaseDir = join(baseDir, "use-cases", params.use_case);
  const promptPath = join(useCaseDir, "prompt.md");
  const evaluateRulesTextPath = join(useCaseDir, "evaluate_rules.py");

  // Normalize the final schema (base severity/event/desc + caller extras) and run the
  // same schema↔prompt↔rules consistency gate register uses — BEFORE the VLM POST — so
  // an inconsistent prompt cannot register an orphan VLM task with no matching use case.
  const suppliedSchemaExtensions = params.schema_extensions && params.schema_extensions.length > 0
    ? params.schema_extensions
    : inferSchemaExtensionsFromPrompt(extractPromptOutputFields(promptText));
  const schemaExtensions = normalizeFinalSchemaExtensions(suppliedSchemaExtensions);
  if ((!params.schema_extensions || params.schema_extensions.length === 0) && schemaExtensions.length > 0) {
    result.warnings.push(
      `schema_extensions auto-derived from LOCAL_PROMPT output fields: ${schemaExtensions.map((e) => e.name).join(", ")}`,
    );
  }
  const suppliedNames = new Set(suppliedSchemaExtensions.map((e) => e.name.toLowerCase()));
  const normalizedBaseFields = DEFAULT_ALERT_FIELDS.filter(
    (name) => schemaExtensions.some((e) => e.name === name) && !suppliedNames.has(name),
  );
  if (params.schema_extensions && params.schema_extensions.length > 0 && normalizedBaseFields.length > 0) {
    result.warnings.push(
      `schema_extensions treated as extra fields; added default alert field(s): ${normalizedBaseFields.join(", ")}`,
    );
  }

  const consistency = checkUseCaseConsistency({
    promptText,
    schemaExtensions,
    evaluateRulesText: params.evaluate_rules_text,
  });
  result.steps.consistency = consistency;
  if (!consistency.consistent) {
    result.errors.push(...consistencyErrors(consistency));
    return result;
  }

  // Register the VLM task. On failure, stop BEFORE writing any file — artifacts are
  // only persisted once the task is known-good ("注册成功后落盘").
  try {
    result.steps.vlm_task = await registerVlmTask(
      deps.summaryServiceUrl,
      taskName,
      promptText,
      params.description ?? `Dynamically registered use_case ${params.use_case}`,
    );
  } catch (err: any) {
    result.errors.push(`VLM task registration failed: ${err.message}`);
    return result;
  }

  // 落盘: persisting the artifacts is the whole point of this action, so it is
  // unconditional (not gated on persist). overwrite is honored by writeTextArtifact;
  // a same-content re-run returns "unchanged".
  try {
    const artifacts = ensureArtifactsStep(result);
    artifacts.prompt_md = writeTextArtifact(promptPath, params.prompt_text, params.overwrite, result.warnings);
    artifacts.evaluate_rules_py = writeTextArtifact(
      evaluateRulesTextPath,
      params.evaluate_rules_text,
      params.overwrite,
      result.warnings,
    );
  } catch (err: any) {
    result.errors.push(`artifact persist failed: ${err.message}`);
    return result;
  }

  // Smoke-test the just-written evaluate_rules.py so a broken override is caught here
  // rather than silently failing at runtime. Runs whenever rules text was supplied
  // (covers both freshly "written" and identical "unchanged" files on disk).
  if (params.evaluate_rules_text !== undefined) {
    const error = await validateEvaluateRulesOverride(params.use_case, evaluateRulesTextPath, schemaExtensions);
    if (error) {
      result.errors.push(error);
      return result;
    }
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
      // Emit `description` double-quoted to match the built-in use_case_dict entries.
      let node: Record<string, unknown> = entry;
      if (typeof entry.description === "string") {
        const s = new Scalar(entry.description);
        s.type = Scalar.QUOTE_DOUBLE;
        node = { ...entry, description: s };
      }
      doc.setIn(["use_case_dict", useCase], node);
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
