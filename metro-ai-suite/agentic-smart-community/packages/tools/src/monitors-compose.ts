import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { parse as parseYaml } from "yaml";

export type ComposeAction = "validate" | "up" | "down" | "restart" | "ps";

export interface MonitorDeclaration {
  enabled?: boolean;
  name?: string;
  source_url?: string;
  /** References a key in config.yaml's use_case_dict. */
  use_case?: string;
  pipeline_config?: Record<string, unknown>;
}

export interface ValidationError {
  monitor_id: string;
  field: string;
  reason: string;
}

export interface ComposeResult {
  monitor_id: string;
  status: "ok" | "already_running" | "skipped" | "failed";
  reason?: string;
  /** Only populated by `ps` action — current runtime state of this monitor. */
  state?: {
    db: { exists: boolean; status?: string };
    analytics: { reachable: boolean; status?: unknown; error?: string };
    worker: { running: boolean };
  };
}

export interface ComposeOutput {
  action: ComposeAction;
  file: string;                  // resolved absolute path
  valid: boolean;
  errors: ValidationError[];
  results: ComposeResult[];
}

// ---------------------------------------------------------------------------
// YAML loading + validation (pure functions, no side effects)
// ---------------------------------------------------------------------------

export function loadMonitorsFromYaml(filePath: string): {
  resolvedPath: string;
  monitors: Record<string, MonitorDeclaration>;
} {
  const resolved = resolve(filePath);
  const raw = readFileSync(resolved, "utf-8");
  const parsed = parseYaml(raw);
  if (!parsed || typeof parsed !== "object" || !parsed.monitors) {
    throw new Error(`monitors file ${resolved} must contain a top-level \`monitors:\` block`);
  }
  return { resolvedPath: resolved, monitors: expandEnvVars(parsed.monitors) as Record<string, MonitorDeclaration> };
}

export function validateMonitors(
  monitors: Record<string, MonitorDeclaration>,
  knownUseCases?: string[],
): ValidationError[] {
  const errors: ValidationError[] = [];
  for (const [id, cfg] of Object.entries(monitors)) {
    if (!cfg.source_url) errors.push({ monitor_id: id, field: "source_url", reason: "missing" });
    if (!cfg.use_case) {
      errors.push({ monitor_id: id, field: "use_case", reason: "missing" });
    } else if (knownUseCases && !knownUseCases.includes(cfg.use_case)) {
      errors.push({
        monitor_id: id,
        field: "use_case",
        reason: `unknown use_case "${cfg.use_case}". Known: [${knownUseCases.join(", ")}]`,
      });
    }
  }
  return errors;
}

function expandEnvVars(value: unknown): unknown {
  if (typeof value === "string") {
    return value.replace(/\$\{([A-Z_][A-Z0-9_]*)\}/gi, (_m, name) => process.env[name] ?? "");
  }
  if (Array.isArray(value)) return value.map(expandEnvVars);
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value)) out[k] = expandEnvVars(v);
    return out;
  }
  return value;
}
