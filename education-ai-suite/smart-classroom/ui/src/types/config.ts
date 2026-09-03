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
