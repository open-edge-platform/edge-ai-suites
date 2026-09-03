// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// Typed bridge to the first-run setup runner in the main process.

import { useCallback, useEffect, useState } from 'react';
import type { LogLine } from '../types/services';
import type { SetupSection, SetupStep } from '../types/setup';
import { toMessage, unwrap } from './ipcResult';

export const isSetupManagerAvailable = (): boolean => !!window.electronAPI?.setup;

export const listSetup = () => unwrap(window.electronAPI?.setup?.list());
export const checkSetup = () => unwrap(window.electronAPI?.setup?.check());
export const runSetupStep = (stepId: string, actionId: string) =>
  unwrap(window.electronAPI?.setup?.run(stepId, actionId));
export const cancelSetup = () => unwrap(window.electronAPI?.setup?.cancel());
export const clearSetupLogs = () => unwrap(window.electronAPI?.setup?.clearLogs());
export const revealSetupLogs = () => unwrap(window.electronAPI?.setup?.revealLogs());
export const copyText = (text: string) => unwrap(window.electronAPI?.copyText(text));

const MAX_CLIENT_LINES = 2000;

export function useSetup() {
  const [sections, setSections] = useState<SetupSection[]>([]);
  const [steps, setSteps] = useState<SetupStep[]>([]);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    if (!isSetupManagerAvailable()) return;
    let cancelled = false;

    listSetup()
      .then((description) => {
        if (cancelled) return;
        setSections(description.sections);
        setSteps(description.steps);
      })
      .catch((e) => !cancelled && setError(toMessage(e)));

    const unsubscribe = window.electronAPI?.setup?.onChanged((snapshot) => {
      if (!cancelled) setSteps(snapshot);
    });

    return () => {
      cancelled = true;
      unsubscribe?.();
    };
  }, []);

  const check = useCallback(async () => {
    setChecking(true);
    setError('');
    try {
      setSteps(await checkSetup());
    } catch (e) {
      setError(toMessage(e));
    } finally {
      setChecking(false);
    }
  }, []);

  const run = useCallback(async (stepId: string, actionId: string) => {
    setBusyId(stepId);
    setError('');
    try {
      await runSetupStep(stepId, actionId);
      return true;
    } catch (e) {
      setError(toMessage(e));
      return false;
    } finally {
      setBusyId(null);
    }
  }, []);

  return { sections, steps, error, busyId, checking, check, run, cancel: cancelSetup, clearError: () => setError('') };
}

/** Output of the running setup step, seeded from the main-process buffer. */
export function useSetupLogs() {
  const [lines, setLines] = useState<LogLine[]>([]);

  useEffect(() => {
    if (!isSetupManagerAvailable()) return;
    let cancelled = false;

    unwrap(window.electronAPI?.setup?.logs({ limit: 1000 }))
      .then((initial) => !cancelled && setLines(initial))
      .catch(() => undefined);

    const unsubscribe = window.electronAPI?.logs?.onAppend((batch) => {
      if (cancelled || batch.id !== 'setup') return;
      setLines((previous) => [...previous, ...batch.lines].slice(-MAX_CLIENT_LINES));
    });

    return () => {
      cancelled = true;
      unsubscribe?.();
    };
  }, []);

  // Clears the main-process ring buffer too, so the pane stays empty instead of
  // refilling from it on the next visit to this screen.
  const clear = useCallback(async () => {
    await clearSetupLogs().catch(() => undefined);
    setLines([]);
  }, []);

  return { lines, clear };
}
