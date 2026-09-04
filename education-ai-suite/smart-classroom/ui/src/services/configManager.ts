// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// Typed bridge to the schema-guarded settings editor in the main process.

import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ConfigChange, ConfigDescription, ConfigField, ConfigProblem } from '../types/config';
import { toMessage, unwrap } from './ipcResult';

/** Draft key for one field; a path alone is ambiguous across the three files. */
export const fieldKey = (field: ConfigField) => `${field.file}:${field.path}`;

export const isConfigManagerAvailable = (): boolean => !!window.electronAPI?.config;

export const describeConfig = () => unwrap(window.electronAPI?.config?.describe());
export const applyConfig = (changes: ConfigChange[]) => unwrap(window.electronAPI?.config?.apply(changes));
export const validateConfig = (changes: ConfigChange[]) => unwrap(window.electronAPI?.config?.validate(changes));
export const revealConfig = () => unwrap(window.electronAPI?.config?.reveal());

/**
 * Stable identity for "no pending edits". A fresh [] on every render would
 * retrigger the effect in useConfigProblems forever.
 */
export const NO_CHANGES: ConfigChange[] = [];

/**
 * Cross-field problems for the pending edits, refreshed as they change.
 *
 * The rules live in the main process because one of them has to look at the
 * filesystem, so this is a round trip; it is debounced, and a stale reply is
 * dropped rather than allowed to overwrite a newer one.
 */
export function useConfigProblems(changes: ConfigChange[], description: ConfigDescription | null) {
  const [problems, setProblems] = useState<ConfigProblem[]>([]);

  useEffect(() => {
    if (!description || !isConfigManagerAvailable()) {
      setProblems([]);
      return;
    }
    let live = true;
    const timer = setTimeout(() => {
      validateConfig(changes)
        .then((found) => {
          if (live) setProblems(found);
        })
        // A failed dry run must not block the user; apply() still enforces.
        .catch(() => {
          if (live) setProblems([]);
        });
    }, 200);
    return () => {
      live = false;
      clearTimeout(timer);
    };
    // description is a dependency, not just a guard: useConfig replaces it after
    // every save, which is exactly when the on-disk answer can have changed.
  }, [changes, description]);

  const blocking = useMemo(() => problems.filter((problem) => problem.blocking), [problems]);
  const byField = useMemo(() => {
    const map = new Map<string, ConfigProblem>();
    // Blocking wins the row when a field carries both.
    for (const problem of [...problems].sort((a, b) => Number(b.blocking) - Number(a.blocking))) {
      const key = `${problem.file}:${problem.path}`;
      if (!map.has(key)) map.set(key, problem);
    }
    return map;
  }, [problems]);

  /** One line per rule, deduped across the fields it flags. */
  const messages = useMemo(() => {
    const seen = new Set<string>();
    return problems.filter((problem) => !seen.has(problem.rule) && seen.add(problem.rule));
  }, [problems]);

  return { problems, blocking, byField, messages };
}

export function useConfig() {
  const [description, setDescription] = useState<ConfigDescription | null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const reload = useCallback(async () => {
    try {
      setDescription(await describeConfig());
      setError('');
    } catch (e) {
      setError(toMessage(e));
    }
  }, []);

  useEffect(() => {
    if (isConfigManagerAvailable()) reload();
  }, [reload]);

  const save = useCallback(
    async (changes: ConfigChange[]) => {
      setSaving(true);
      setError('');
      try {
        await applyConfig(changes);
        await reload();
        return true;
      } catch (e) {
        setError(toMessage(e));
        return false;
      } finally {
        setSaving(false);
      }
    },
    [reload]
  );

  return { description, error, saving, save, reload, clearError: () => setError('') };
}
