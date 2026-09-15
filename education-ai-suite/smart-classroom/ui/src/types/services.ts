// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// Shapes returned by the Electron service-manager IPC bridge. Kept in sync with
// electron/services/registry.cjs and electron/services/process-manager.cjs.

export type ServiceStatus = 'stopped' | 'starting' | 'healthy' | 'degraded' | 'stopping' | 'failed';

export interface ServiceSnapshot {
  id: string;
  label: string;
  port: number | null;
  /** True when this process is spawned and killed by the app itself. */
  managed: boolean;
  /** Id of the service that spawns this one, when it is not managed directly. */
  ownedBy: string | null;
  description: string;
  /** False when the corresponding feature is turned off in config.yaml. */
  enabled: boolean;
  status: ServiceStatus;
  pid: number | null;
  /** True when the process was started outside the app and is only attached to. */
  external: boolean;
  /** Managed services only: false when the Python environment is not created yet. */
  runnable: boolean;
  startedAt: number | null;
  uptimeMs: number | null;
  exitCode: number | null;
  error: string | null;
  logFile: string | null;
}

export interface LogLine {
  seq: number;
  ts: number;
  stream: 'stdout' | 'stderr' | 'manager';
  text: string;
}

export interface LogBatch {
  id: string;
  lines: LogLine[];
}

export type IpcResult<T> = { ok: true; data: T } | { ok: false; error: string };
