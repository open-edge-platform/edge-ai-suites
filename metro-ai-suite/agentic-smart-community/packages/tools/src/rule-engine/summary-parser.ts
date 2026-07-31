import type { SchemaExtension } from "@smartbuilding-video/db";

export interface ParsedSummary {
  /** Fields successfully extracted from the summary text, keyed by lowercased schema field name. */
  fields: Record<string, string>;
  /** Names of required fields (schema.required:true) that were NOT found in the summary. */
  missingRequired: string[];
}

function toFieldText(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value) || typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function parseJsonObject(text: string): Record<string, unknown> | null {
  const trimmed = text.trim();
  if (!trimmed) return null;
  try {
    const parsed = JSON.parse(trimmed);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
  } catch {
    // Not plain JSON; continue with fenced block parse.
  }

  const fenced = trimmed.match(/```(?:json)?\s*([\s\S]*?)\s*```/i);
  if (!fenced?.[1]) return null;
  try {
    const parsed = JSON.parse(fenced[1]);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
  } catch {
    // Ignore malformed fenced JSON.
  }
  return null;
}

function extractFromObject(
  obj: Record<string, unknown>,
  wanted: Map<string, string>,
  fields: Record<string, string>,
): void {
  for (const [rawKey, rawValue] of Object.entries(obj)) {
    const canonical = wanted.get(rawKey.toLowerCase());
    if (!canonical) continue;
    if (fields[canonical]) continue;
    const value = toFieldText(rawValue);
    if (value) fields[canonical] = value;
  }
}

/**
 * Schema-aware parser for VLM summary output.
 *
 * Uses the schema `extensions` array as the source of truth — only field names
 * declared there are parsed; lines starting with other keys are ignored.
 *
 * Matching is case-insensitive: a schema field `event` matches `EVENT:`, `Event:`, or `event:`.
 * First occurrence wins when duplicates appear.
 *
 * `requiredFields` (optional) overrides which fields count as required for the
 * `missingRequired` check — pass the current use case's effective required set so
 * one use case's required fields don't get flagged as missing on another's tasks.
 * When omitted, falls back to the global `extensions` required flags.
 */
export function parseSummaryFields(
  summaryText: string,
  extensions: SchemaExtension[],
  requiredFields?: string[],
): ParsedSummary {
  const requiredNames = requiredFields ?? extensions.filter((e) => e.required).map((e) => e.name);
  const fields: Record<string, string> = {};
  if (!summaryText || extensions.length === 0) {
    return { fields, missingRequired: [...requiredNames] };
  }

  // Build lookup: lowercased schema name → canonical (lowercased) name to store under
  const wanted = new Map<string, string>();
  for (const ext of extensions) wanted.set(ext.name.toLowerCase(), ext.name.toLowerCase());

  for (const line of summaryText.split("\n")) {
    const colon = line.indexOf(":");
    if (colon < 1) continue;
    const key = line.slice(0, colon).trim().toLowerCase();
    const canonical = wanted.get(key);
    if (!canonical) continue; // not a schema field — skip
    if (fields[canonical]) continue; // first occurrence wins
    const value = line.slice(colon + 1).trim();
    if (value) fields[canonical] = value;
  }

  // Some tasks (for example pet_safety) may return JSON; extract only schema fields.
  const jsonObj = parseJsonObject(summaryText);
  if (jsonObj) {
    extractFromObject(jsonObj, wanted, fields);
  }

  const missingRequired = requiredNames.filter((name) => !fields[name.toLowerCase()]);

  return { fields, missingRequired };
}

/**
 * Normalize raw model output to schema-owned plain text for storage.
 *
 * Output contains only configured extension fields, one `name: value` per line,
 * in schema declaration order. If no configured fields are extracted, the raw
 * summary text is preserved.
 */
export function normalizeSummaryTextBySchema(
  rawSummaryText: string,
  extensions: SchemaExtension[],
  parsedFields: Record<string, string>,
): string {
  if (!rawSummaryText || extensions.length === 0) return rawSummaryText;

  const lines: string[] = [];
  for (const ext of extensions) {
    const value = parsedFields[ext.name.toLowerCase()];
    if (!value) continue;
    lines.push(`${ext.name}: ${value}`);
  }

  if (lines.length === 0) return rawSummaryText;
  return lines.join("\n");
}
