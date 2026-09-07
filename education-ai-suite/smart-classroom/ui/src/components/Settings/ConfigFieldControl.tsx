// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// One row of the settings form. Shared by the full Configuration editor and the
// "commonly used" subset on Get started, so both render and validate alike.

import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import type { ConfigField, ConfigProblem, ConfigValue } from '../../types/config';
import { fieldKey } from '../../services/configManager';

interface SuggestionInputProps {
  value: string;
  suggestions: string[];
  onChange: (value: string) => void;
}

/**
 * Free text with a dropdown of the documented choices.
 *
 * A native <datalist> would be less code, but it matches its options against
 * what is already typed, so the rest of the list disappears after a character
 * or two — and its popup ignores every style rule. This lists all suggestions
 * whatever is in the box, and is styled to match the enum <select> beside it.
 */
const SuggestionInput: React.FC<SuggestionInputProps> = ({ value, suggestions, onChange }) => {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number; width: number } | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Portalled to the body: .config-fields clips its children to get rounded
  // corners, so a list positioned inside the row would be cut off.
  const openList = () => {
    const rect = wrapRef.current?.getBoundingClientRect();
    if (!rect) return;
    setPos({ top: rect.bottom + 2, left: rect.left, width: rect.width });
    setOpen(true);
  };

  // Placed once on open, so close on any movement rather than let the list hang
  // away from its field.
  useEffect(() => {
    if (!open) return;

    const onPointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      // The list lives outside wrapRef, so it needs its own check or picking an
      // option would count as clicking away.
      if (!wrapRef.current?.contains(target) && !listRef.current?.contains(target)) setOpen(false);
    };
    const close = () => setOpen(false);

    document.addEventListener('mousedown', onPointerDown);
    window.addEventListener('resize', close);
    document.addEventListener('scroll', close, true);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      window.removeEventListener('resize', close);
      document.removeEventListener('scroll', close, true);
    };
  }, [open]);

  return (
    <div className="config-combo" ref={wrapRef}>
      <input
        ref={inputRef}
        className="config-input"
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-autocomplete="list"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Escape' && open) {
            event.stopPropagation();
            setOpen(false);
          } else if (event.key === 'ArrowDown' && !open) {
            event.preventDefault();
            openList();
          }
        }}
      />
      <button
        type="button"
        className="config-combo-toggle"
        // The input is the tab stop; the arrow is a shortcut for the mouse.
        tabIndex={-1}
        aria-label={t('config.showOptions', 'Show options')}
        onClick={() => (open ? setOpen(false) : openList())}
      />
      {open &&
        pos &&
        createPortal(
          <div
            className="config-combo-list"
            ref={listRef}
            role="listbox"
            style={{ top: pos.top, left: pos.left, width: pos.width }}
          >
            {suggestions.map((option) => (
              <button
                type="button"
                key={option}
                role="option"
                aria-selected={option === value}
                className={`config-combo-option${option === value ? ' selected' : ''}`}
                onClick={() => {
                  onChange(option);
                  setOpen(false);
                  inputRef.current?.focus();
                }}
              >
                {option}
              </button>
            ))}
          </div>,
          document.body
        )}
    </div>
  );
};

interface ConfigFieldControlProps {
  field: ConfigField;
  draft: Record<string, ConfigValue>;
  onChange: (value: ConfigValue) => void;
  /** Set so a deep link from Get started can scroll straight to this row. */
  id?: string;
  /** Briefly flagged after such a jump, so the row is findable by eye. */
  flashed?: boolean;
  /** A cross-field rule this value takes part in breaking. */
  problem?: ConfigProblem;
}

const ConfigFieldControl: React.FC<ConfigFieldControlProps> = ({ field, draft, onChange, id, flashed, problem }) => {
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
    if (field.suggestions?.length) {
      return <SuggestionInput value={String(value)} suggestions={field.suggestions} onChange={onChange} />;
    }

    return (
      <input
        className="config-input"
        type="text"
        value={String(value)}
        onChange={(event) => onChange(event.target.value)}
      />
    );
  };

  const problemClass = problem ? (problem.blocking ? ' invalid' : ' questionable') : '';

  return (
    <div id={id} className={`config-field${edited ? ' dirty' : ''}${flashed ? ' flashed' : ''}${problemClass}`}>
      <div className="config-field-label">
        <span className="config-field-name">{field.label}</span>
        <code className="config-field-path" title={field.path}>
          {field.path}
        </code>
        {field.help && <span className="config-field-help">{field.help}</span>}
        {/* Short form only: the banner above already states the problem in full,
            and a rule can name several fields, so the sentence would otherwise
            appear two or three times within one screenful. */}
        {problem && (
          <span className="config-field-problem" title={problem.message}>
            {problem.summary}
          </span>
        )}
      </div>
      <div className="config-field-control">{control()}</div>
    </div>
  );
};

export default ConfigFieldControl;
