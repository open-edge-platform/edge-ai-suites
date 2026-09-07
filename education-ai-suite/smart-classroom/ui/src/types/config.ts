// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// Shapes returned by the Electron config IPC bridge. Kept in sync with
// electron/services/config-schema.cjs.

// autoNumber is the literal "auto" or a whole number; it renders as a text box.
export type ConfigFieldType = 'boolean' | 'enum' | 'number' | 'autoNumber' | 'string' | 'secret' | 'url' | 'path';

export type ConfigValue = string | number | boolean;

export interface ConfigField {
  path: string;
  /** 'config' (config.yaml), 'runtime' (runtime_config.yaml) or 'proxy' (.proxy-config). */
  file: string;
  group: string;
  /** Id of the ConfigGroup subgroup this field sits under; null when the group has none. */
  subgroup: string | null;
  label: string;
  type: ConfigFieldType;
  options: string[] | null;
  /** Non-binding choices offered for a free-text field. */
  suggestions: string[] | null;
  wizard: boolean;
  help: string | null;
  min: number | null;
  max: number | null;
  /** Null for secrets, which never leave the main process. */
  value: ConfigValue | null;
  /** Secrets only: whether a value is currently stored. */
  isSet?: boolean;
}

export interface ConfigGroup {
  id: string;
  label: string;
}

/** A section within a group, named after the config.yaml node it mirrors. */
export interface ConfigSubgroup {
  id: string;
  group: string;
  label: string;
  /** Dotted config.yaml path, shown under the heading. */
  node: string;
}

export interface ConfigDescription {
  groups: ConfigGroup[];
  subgroups: ConfigSubgroup[];
  fields: ConfigField[];
}

export interface ConfigChange {
  file: string;
  path: string;
  value: ConfigValue;
}

/**
 * A combination of settings the backend would reject. Reported per field, so
 * one rule spanning two fields appears twice with the same `rule` and message.
 */
export interface ConfigProblem {
  file: string;
  path: string;
  /** Rule id, stable across the fields one rule flags. */
  rule: string;
  /** Short form for a field row, where the full message would repeat per field. */
  summary: string;
  message: string;
  /**
   * False for a problem already in the file that this edit neither introduced
   * nor touched, and for a rule the backend tolerates: shown as a warning, but
   * it does not stop the save.
   */
  blocking: boolean;
  /**
   * Changes that would clear this problem, when a rule can name them
   * unambiguously. Offered as one click, and applied to the pending draft rather
   * than to disk so it stays reviewable.
   */
  fix?: ConfigChange[];
}
