import Database from "better-sqlite3";

export interface SchemaExtension {
  name: string;
  type: "text" | "integer" | "real";
  required: boolean;
}

export interface SchemaDefinition {
  video_summary_tasks?: { extensions: SchemaExtension[] };
  alerts?: { extensions: SchemaExtension[] };
  custom_tables?: Array<{ name: string; columns: SchemaExtension[] }>;
}

export class SchemaManager {
  private db: Database.Database;

  constructor(db: Database.Database) {
    this.db = db;
  }

  applySchema(schema: SchemaDefinition): { added: string[]; warnings: string[] } {
    const added: string[] = [];
    const warnings: string[] = [];

    if (schema.video_summary_tasks?.extensions) {
      for (const ext of schema.video_summary_tasks.extensions) {
        const result = this.addColumnIfMissing("video_summary_tasks", ext);
        if (result === "added") added.push(`video_summary_tasks.${ext.name}`);
        else if (result === "type_mismatch") warnings.push(`video_summary_tasks.${ext.name}: type mismatch, manual migration required`);
      }
    }

    if (schema.alerts?.extensions) {
      for (const ext of schema.alerts.extensions) {
        const result = this.addColumnIfMissing("alerts", ext);
        if (result === "added") added.push(`alerts.${ext.name}`);
        else if (result === "type_mismatch") warnings.push(`alerts.${ext.name}: type mismatch, manual migration required`);
      }
    }

    if (schema.custom_tables) {
      for (const table of schema.custom_tables) {
        this.createCustomTable(table.name, table.columns);
        added.push(`table:${table.name}`);
      }
    }

    return { added, warnings };
  }

  /**
   * Check whether a prompt contains every schema field name as a case-insensitive substring.
   * Required fields decide validity; optional fields are reported separately for completeness.
   *
   * Stateless — uses only the extensions list it's given. Static (no `this.db` access),
   * so callers can use it without instantiating SchemaManager.
   */
  static validatePromptSchema(
    extensions: SchemaExtension[],
    prompt: string,
  ): {
    valid: boolean;
    requiredFields: string[];
    optionalFields: string[];
    missingRequired: string[];
    missingOptional: string[];
  } {
    const promptLower = prompt.toLowerCase();
    const requiredFields = extensions.filter((e) => e.required).map((e) => e.name);
    const optionalFields = extensions.filter((e) => !e.required).map((e) => e.name);
    const missingRequired = requiredFields.filter((f) => !promptLower.includes(f.toLowerCase()));
    const missingOptional = optionalFields.filter((f) => !promptLower.includes(f.toLowerCase()));
    return {
      valid: missingRequired.length === 0,
      requiredFields,
      optionalFields,
      missingRequired,
      missingOptional,
    };
  }

  private getExistingColumns(table: string): Map<string, string> {
    const columns = new Map<string, string>();
    const rows = this.db.prepare(`PRAGMA table_info(${table})`).all() as any[];
    for (const row of rows) {
      columns.set(row.name, row.type.toLowerCase());
    }
    return columns;
  }

  private addColumnIfMissing(table: string, ext: SchemaExtension): "exists" | "added" | "type_mismatch" {
    const existing = this.getExistingColumns(table);
    if (existing.has(ext.name)) {
      const currentType = existing.get(ext.name)!;
      if (currentType !== ext.type) return "type_mismatch";
      return "exists";
    }
    this.db.prepare(`ALTER TABLE ${table} ADD COLUMN ${ext.name} ${ext.type.toUpperCase()}`).run();
    return "added";
  }

  private createCustomTable(name: string, columns: SchemaExtension[]): void {
    const cols = columns.map((c) => `${c.name} ${c.type.toUpperCase()}`).join(", ");
    this.db.exec(`CREATE TABLE IF NOT EXISTS ${name} (id INTEGER PRIMARY KEY AUTOINCREMENT, ${cols})`);
  }
}
