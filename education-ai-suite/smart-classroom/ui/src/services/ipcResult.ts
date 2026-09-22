// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import type { IpcResult } from '../types/services';

/** Unwraps the { ok, data } | { ok, error } envelope used by every Electron IPC handler. */
export async function unwrap<T>(call: Promise<IpcResult<T>> | undefined): Promise<T> {
  if (!call) throw new Error('This feature is only available in the desktop app.');
  const result = await call;
  // The code rides along on the Error so a `catch` gets both without the caller
  // having to unwrap the envelope itself.
  if (!result?.ok) throw Object.assign(new Error(result?.error || 'Unknown error.'), { code: result?.code });
  return result.data;
}

export const toMessage = (error: unknown): string =>
  error instanceof Error ? error.message : String(error);

/** The main process's code for this failure, when it named one. */
export const toCode = (error: unknown): string | null => {
  const code = (error as { code?: unknown } | null | undefined)?.code;
  return typeof code === 'string' ? code : null;
};
