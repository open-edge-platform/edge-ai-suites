// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import type { IpcResult } from '../types/services';

/** Unwraps the { ok, data } | { ok, error } envelope used by every Electron IPC handler. */
export async function unwrap<T>(call: Promise<IpcResult<T>> | undefined): Promise<T> {
  if (!call) throw new Error('This feature is only available in the desktop app.');
  const result = await call;
  if (!result?.ok) throw new Error(result?.error || 'Unknown error.');
  return result.data;
}

export const toMessage = (error: unknown): string =>
  error instanceof Error ? error.message : String(error);
