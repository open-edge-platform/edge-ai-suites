// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// Typed bridge to the schema-guarded settings editor in the main process.

import { useCallback, useEffect, useState } from 'react';
import type { ConfigChange, ConfigDescription, ConfigField } from '../types/config';
import { toMessage, unwrap } from './ipcResult';

/** Draft key for one field; a path alone is ambiguous across the three files. */
export const fieldKey = (field: ConfigField) => `${field.file}:${field.path}`;

export const isConfigManagerAvailable = (): boolean => !!window.electronAPI?.config;

export const describeConfig = () => unwrap(window.electronAPI?.config?.describe());
export const applyConfig = (changes: ConfigChange[]) => unwrap(window.electronAPI?.config?.apply(changes));
export const revealConfig = () => unwrap(window.electronAPI?.config?.reveal());

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
