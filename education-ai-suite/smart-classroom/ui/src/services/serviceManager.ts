// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// Typed wrapper around the Electron service-manager bridge (electron/services/).
// Every export is a no-op-with-error in the plain web app, so callers must
// feature-detect with isServiceManagerAvailable() before rendering UI.

import { useCallback, useEffect, useRef, useState } from 'react';
import type { LogLine, ServiceSnapshot } from '../types/services';
import { toMessage, unwrap } from './ipcResult';

export const isServiceManagerAvailable = (): boolean => !!window.electronAPI?.services;

export const listServices = () => unwrap(window.electronAPI?.services?.list());
export const startService = (id: string) => unwrap(window.electronAPI?.services?.start(id));
export const stopService = (id: string) => unwrap(window.electronAPI?.services?.stop(id));
export const restartService = (id: string) => unwrap(window.electronAPI?.services?.restart(id));
export const readLogs = (id: string, limit = 1000) => unwrap(window.electronAPI?.logs?.read(id, { limit }));
export const clearLogs = (id: string) => unwrap(window.electronAPI?.logs?.clear(id));
export const revealLogs = (id: string) => unwrap(window.electronAPI?.logs?.reveal(id));

/** Live service list. State is owned by the main process and pushed on change. */
export function useServices() {
  const [services, setServices] = useState<ServiceSnapshot[]>([]);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    if (!isServiceManagerAvailable()) return;
    let cancelled = false;

    listServices()
      .then((snapshot) => !cancelled && setServices(snapshot))
      .catch((e) => !cancelled && setError(toMessage(e)));

    const unsubscribe = window.electronAPI?.services?.onChanged((snapshot) => {
      if (!cancelled) setServices(snapshot);
    });

    return () => {
      cancelled = true;
      unsubscribe?.();
    };
  }, []);

  const run = useCallback(async (id: string, action: (id: string) => Promise<unknown>) => {
    setBusyId(id);
    setError('');
    try {
      await action(id);
    } catch (e) {
      setError(toMessage(e));
    } finally {
      setBusyId(null);
    }
  }, []);

  return {
    services,
    error,
    busyId,
    clearError: () => setError(''),
    start: (id: string) => run(id, startService),
    stop: (id: string) => run(id, stopService),
    restart: (id: string) => run(id, restartService),
  };
}

/**
 * Reload the window once a *new* backend process is healthy.
 *
 * The backend holds the session in memory, so restarting it invalidates
 * everything the renderer is showing: sessionId, the recording flags, a
 * half-streamed transcript. None of that is persisted, so a reload is the whole
 * reset — resetting each slice by hand would still leave component-local state
 * and the metric and monitor timers running against a process that has
 * forgotten them.
 *
 * startedAt is stamped per spawn, so it names the process generation. The first
 * generation this page sees is recorded rather than acted on: a first start has
 * nothing stale to clear, and reloading there would throw the user off the logs
 * they are watching it boot in. Waiting for `healthy` rather than firing at
 * spawn means the reloaded page finds a backend that answers.
 */
export function useReloadOnBackendRestart(backend: ServiceSnapshot | undefined): void {
  // undefined until the first snapshot arrives, which is not the same as the
  // null this holds while the backend is stopped.
  const generation = useRef<number | null | undefined>(undefined);

  const startedAt = backend?.startedAt ?? null;
  const status = backend?.status;

  useEffect(() => {
    if (startedAt === null) {
      // Stopped, or attached to a backend started outside the app. Either way
      // there is no generation to compare a successor against.
      if (generation.current === undefined) generation.current = null;
      return;
    }
    // First live backend this page has seen: nothing on screen predates it.
    if (generation.current === undefined || generation.current === null) {
      generation.current = startedAt;
      return;
    }
    if (generation.current === startedAt) return;
    // A successor is booting. Leave the old generation recorded so this fires
    // on the healthy tick, and not at all if the start fails.
    if (status !== 'healthy') return;
    generation.current = startedAt;
    window.location.reload();
  }, [startedAt, status]);
}

const MAX_CLIENT_LINES = 2000;

/** Buffered log lines for one service, seeded from the main-process ring buffer. */
export function useServiceLogs(id: string | null) {
  const [lines, setLines] = useState<LogLine[]>([]);
  const idRef = useRef(id);
  idRef.current = id;

  useEffect(() => {
    if (!id || !isServiceManagerAvailable()) {
      setLines([]);
      return;
    }
    let cancelled = false;

    readLogs(id)
      .then((initial) => !cancelled && setLines(initial))
      .catch(() => !cancelled && setLines([]));

    const unsubscribe = window.electronAPI?.logs?.onAppend((batch) => {
      if (cancelled || batch.id !== idRef.current) return;
      setLines((previous) => [...previous, ...batch.lines].slice(-MAX_CLIENT_LINES));
    });

    return () => {
      cancelled = true;
      unsubscribe?.();
    };
  }, [id]);

  const clear = useCallback(async () => {
    if (!id) return;
    await clearLogs(id).catch(() => undefined);
    setLines([]);
  }, [id]);

  return { lines, clear };
}
