// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// One row of the settings form. Shared by the full Configuration editor and the
// "commonly used" subset on Get started, so both render and validate alike.

import React from 'react';
import { useTranslation } from 'react-i18next';
import type { ConfigField, ConfigValue } from '../../types/config';
import { fieldKey } from '../../services/configManager';

interface ConfigFieldControlProps {
  field: ConfigField;
  draft: Record<string, ConfigValue>;
  onChange: (value: ConfigValue) => void;
  /** Set so a deep link from Get started can scroll straight to this row. */
  id?: string;
  /** Briefly flagged after such a jump, so the row is findable by eye. */
  flashed?: boolean;
}

const ConfigFieldControl: React.FC<ConfigFieldControlProps> = ({ field, draft, onChange, id, flashed }) => {
  const { t } = useTranslation();
  const key = fieldKey(field);
  const edited = draft[key] !== undefined;
  const value = edited ? draft[key] : field.value ?? (field.type === 'boolean' ? false : '');

  const control = () => {
    if (field.type === 'boolean') {
      return (
        <label className="config-switch">
          <input type="checkbox" checked={!!value} onChange={(event) => onChange(event.target.checked)} />
          <span />
        </label>
      );
    }

    if (field.type === 'enum') {
      return (
        <select className="config-input" value={String(value)} onChange={(event) => onChange(event.target.value)}>
          {(field.options ?? []).map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      );
    }

    if (field.type === 'secret') {
      return (
        <input
          className="config-input"
          type="password"
          value={edited ? String(value) : ''}
          placeholder={
            field.isSet ? t('config.secretSet', 'Stored — type to replace') : t('config.secretUnset', 'Not set')
          }
          onChange={(event) => onChange(event.target.value)}
        />
      );
    }

    if (field.type === 'number') {
      return (
        <input
          className="config-input"
          type="number"
          value={String(value)}
          min={field.min ?? undefined}
          max={field.max ?? undefined}
          step="any"
          onChange={(event) => onChange(event.target.value)}
        />
      );
    }

    if (field.type === 'path') {
      return (
        <div className="config-path">
          <input
            className="config-input"
            type="text"
            value={String(value)}
            onChange={(event) => onChange(event.target.value)}
          />
          <button
            className="config-btn"
            onClick={async () => {
              const picked = await window.electronAPI?.pickDirectory(String(value));
              if (picked) onChange(picked);
            }}
          >
            {t('config.browse', 'Browse…')}
          </button>
        </div>
      );
    }

    // Suggestions offer the documented choices without forbidding others.
    const listId = field.suggestions?.length ? `${key}-options` : undefined;
    return (
      <>
        <input
          className="config-input"
          type="text"
          list={listId}
          value={String(value)}
          onChange={(event) => onChange(event.target.value)}
        />
        {listId && (
          <datalist id={listId}>
            {field.suggestions!.map((option) => (
              <option key={option} value={option} />
            ))}
          </datalist>
        )}
      </>
    );
  };

  return (
    <div id={id} className={`config-field${edited ? ' dirty' : ''}${flashed ? ' flashed' : ''}`}>
      <div className="config-field-label">
        <span className="config-field-name">{field.label}</span>
        <code className="config-field-path" title={field.path}>
          {field.path}
        </code>
        {field.help && <span className="config-field-help">{field.help}</span>}
      </div>
      <div className="config-field-control">{control()}</div>
    </div>
  );
};

export default ConfigFieldControl;
