// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// Shapes returned by the Electron setup IPC bridge. Kept in sync with
// electron/services/setup-runner.cjs.

export type SetupStatus = 'unknown' | 'ok' | 'warn' | 'missing' | 'running' | 'failed';

export interface SetupAction {
  id: string;
  label: string;
  /** Destroys existing state, so it is confirmed natively and never bulk-run. */
  destructive: boolean;
}

export interface SetupSection {
  id: string;
  label: string;
}

export interface SetupStep {
  id: string;
  label: string;
  section: string;
  optional: boolean;
  /** Ids of steps that must be OK before this one's actions can work. */
  requires: string[];
  actions: SetupAction[];
  status: SetupStatus;
  detail: string;
  /** A command or link the user can use when the app cannot fix it. */
  hint: string | null;
}

export interface SetupDescription {
  sections: SetupSection[];
  steps: SetupStep[];
}
