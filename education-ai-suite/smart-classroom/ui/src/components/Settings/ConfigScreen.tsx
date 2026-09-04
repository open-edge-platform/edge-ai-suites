// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import '../../assets/css/Config.css';
import type { ConfigChange, ConfigField, ConfigSubgroup, ConfigValue } from '../../types/config';
import { revealConfig, useConfig, fieldKey as keyOf } from '../../services/configManager';
import { useServices } from '../../services/serviceManager';
import ConfigFieldControl from './ConfigFieldControl';

type Draft = Record<string, ConfigValue>;

/** Fields of one group, split into the subgroup sections they render as. */
interface Section {
  subgroup: ConfigSubgroup | null;
  fields: ConfigField[];
}

interface ConfigScreenProps {
  /** Restarting hands over to Services, which is where the logs and status are. */
  onOpenScreen?: (screen: 'services') => void;
  /** Dotted path of a field to open on and flag, when opened from Get started. */
  focusPath?: string | null;
}

const ConfigScreen: React.FC<ConfigScreenProps> = ({ onOpenScreen, focusPath }) => {
  const { t } = useTranslation();
  const { description, error, saving, save } = useConfig();
  // serviceError is separate from useConfig's: without it a failed restart is
  // indistinguishable from a dead button.
  const { services, restart, busyId, error: serviceError } = useServices();
  // Only edited fields land here, which is also what keeps untouched secrets
  // out of the payload.
  const [draft, setDraft] = useState<Draft>({});
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [flashed, setFlashed] = useState<string | null>(null);
  const consumedFocus = useRef<string | null>(null);

  const backend = services.find((service) => service.id === 'backend');
  const backendRunning = !!backend && backend.status !== 'stopped' && backend.status !== 'failed';
  const dirtyKeys = Object.keys(draft);

  const groupLabel = (id: string, fallback: string) => t(`config.groups.${id}`, fallback);
  const subgroupLabel = (subgroup: ConfigSubgroup) => t(`config.subgroups.${subgroup.id}`, subgroup.label);

  // Every token has to match somewhere, so "qa tokens" narrows to
  // content_search.qa.max_tokens rather than returning every "tokens" field.
  const tokens = useMemo(() => query.toLowerCase().split(/\s+/).filter(Boolean), [query]);

  // Deliberately not searching the group label: the nav already selects groups,
  // and folding it in means "device" returns every field under "Models and
  // devices" whether or not it names one.
  const matches = useMemo(() => {
    if (!description || !tokens.length) return null;
    const byId = new Map(description.subgroups.map((s) => [s.id, s]));
    const hits = new Set<string>();
    for (const field of description.fields) {
      const subgroup = field.subgroup ? byId.get(field.subgroup) : undefined;
      const haystack = [
        field.label,
        field.path,
        field.help ?? '',
        subgroup ? subgroupLabel(subgroup) : '',
        subgroup?.node ?? '',
      ]
        .join(' ')
        .toLowerCase();
      if (tokens.every((token) => haystack.includes(token))) hits.add(keyOf(field));
    }
    return hits;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [description, tokens, t]);

  const grouped = useMemo(() => {
    if (!description) return [];
    const visible = description.fields.filter((field) => !matches || matches.has(keyOf(field)));

    return description.groups
      .map((group) => {
        const fields = visible.filter((field) => field.group === group.id);
        const sections: Section[] = [];

        const loose = fields.filter((field) => !field.subgroup);
        if (loose.length) sections.push({ subgroup: null, fields: loose });

        for (const subgroup of description.subgroups.filter((s) => s.group === group.id)) {
          const owned = fields.filter((field) => field.subgroup === subgroup.id);
          if (owned.length) sections.push({ subgroup, fields: owned });
        }

        return { group, fields, sections };
      })
      .filter((entry) => entry.fields.length > 0);
  }, [description, matches]);

  // Unsaved edits can sit in a group the user has navigated away from, so
  // surface the count next to each entry. Counted over every field, not just
  // the visible ones, so a filter cannot hide pending work.
  const dirtyByGroup = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const field of description?.fields ?? []) {
      if (draft[keyOf(field)] !== undefined) counts[field.group] = (counts[field.group] ?? 0) + 1;
    }
    return counts;
  }, [description, draft]);

  const active = grouped.find((entry) => entry.group.id === selectedGroup) ?? grouped[0];

  // Searching can empty the selected group; follow the results instead of
  // showing a blank panel.
  useEffect(() => {
    if (grouped.length && !grouped.some((entry) => entry.group.id === selectedGroup)) {
      setSelectedGroup(grouped[0].group.id);
    }
  }, [grouped, selectedGroup]);

  // Arriving from Get started with one field in mind: switch to its group,
  // drop any filter that would hide it, then scroll to it and flag it.
  useEffect(() => {
    if (!focusPath || !description) return;
    // Consume it once: description is replaced after every save, and without
    // this the screen would jump back here each time the user saves something.
    if (consumedFocus.current === focusPath) return;
    const field = description.fields.find((entry) => entry.path === focusPath);
    if (!field) return;
    consumedFocus.current = focusPath;

    setQuery('');
    setSelectedGroup(field.group);
    setFlashed(keyOf(field));

    // The group only renders on the next paint, so the node cannot be found yet.
    const raf = requestAnimationFrame(() => {
      document.getElementById(`config-field-${keyOf(field)}`)?.scrollIntoView({ block: 'center', behavior: 'smooth' });
    });
    const timer = setTimeout(() => setFlashed(null), 2200);
    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(timer);
    };
  }, [focusPath, description]);

  const setValue = (field: ConfigField, value: ConfigValue) => {
    setDraft((previous) => ({ ...previous, [keyOf(field)]: value }));
  };

  const handleSave = async () => {
    if (!description) return;
    // Iterates every field, not the filtered view: an edit the search is
    // currently hiding still has to be saved.
    const changes: ConfigChange[] = description.fields
      .filter((field) => draft[keyOf(field)] !== undefined)
      .map((field) => ({ file: field.file, path: field.path, value: draft[keyOf(field)] }));
    if (!changes.length) return;

    if (await save(changes)) {
      setDraft({});
      setSavedAt(Date.now());
    }
  };

  const matchCount = matches?.size ?? 0;

  return (
    <div className="config-screen">
      <div className="config-body">
        <div className="config-header">
          <div className="config-heading">
            <h3 className="config-title">{t('config.title', 'Configuration')}</h3>
            <span className="config-subtitle">
              {t('config.subtitle', 'Edits are written to config.yaml, runtime_config.yaml and .proxy-config.')}
            </span>
          </div>
          <div className="config-actions">
            <div className="config-search">
              <input
                className="config-input config-search-input"
                type="text"
                value={query}
                placeholder={t('config.search', 'Search settings…')}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Escape') setQuery('');
                }}
              />
              {query && (
                <button
                  className="config-search-clear"
                  aria-label={t('config.searchClear', 'Clear search')}
                  onClick={() => setQuery('')}
                >
                  ×
                </button>
              )}
            </div>
            <button className="config-btn" onClick={() => revealConfig().catch(() => undefined)}>
              {t('config.reveal', 'Show file')}
            </button>
            <button className="config-btn" disabled={!dirtyKeys.length || saving} onClick={() => setDraft({})}>
              {t('config.discard', 'Discard')}
            </button>
            <button
              className="config-btn config-btn-primary"
              disabled={!dirtyKeys.length || saving}
              onClick={handleSave}
            >
              {saving
                ? t('config.saving', 'Saving…')
                : t('config.save', 'Save {{count}} change', { count: dirtyKeys.length })}
            </button>
          </div>
        </div>

        {error && <div className="config-error">{error}</div>}
        {serviceError && <div className="config-error">{serviceError}</div>}

        {savedAt && !dirtyKeys.length && (
          <div className="config-banner">
            <span>
              {backendRunning
                ? t('config.restartRequired', 'Saved. Restart the backend to apply changes.')
                : t('config.savedIdle', 'Saved. It takes effect the next time the backend starts.')}
            </span>
            {backendRunning && (
              <button
                className="config-btn config-btn-primary"
                disabled={busyId === 'backend' || backend?.external}
                onClick={() => {
                  void restart('backend');
                  setSavedAt(null);
                  onOpenScreen?.('services');
                }}
              >
                {t('config.restartBackend', 'Restart backend')}
              </button>
            )}
          </div>
        )}

        {backend?.external && savedAt && (
          <div className="config-note">
            {t('config.externalBackend', 'The backend was started outside this app, so it cannot be restarted from here.')}
          </div>
        )}

        {!description && !error && <div className="config-note">{t('config.loading', 'Loading configuration…')}</div>}

        {matches && (
          <div className="config-note">
            {matchCount
              ? t('config.matchCount', '{{count}} setting matches', { count: matchCount })
              : t('config.noResults', 'No setting matches “{{query}}”.', { query })}
          </div>
        )}

        <div className="config-split">
          <nav className="config-nav">
            {grouped.map(({ group, fields }) => (
              <button
                key={group.id}
                className={`config-nav-item${active?.group.id === group.id ? ' active' : ''}`}
                onClick={() => setSelectedGroup(group.id)}
              >
                <span className="config-nav-label">{groupLabel(group.id, group.label)}</span>
                {dirtyByGroup[group.id] ? (
                  <span className="config-nav-dirty">{dirtyByGroup[group.id]}</span>
                ) : (
                  <span className="config-nav-count">{fields.length}</span>
                )}
              </button>
            ))}
          </nav>

          <div className="config-panel">
            {active?.sections.map(({ subgroup, fields }) => (
              <section className="config-group" key={subgroup?.id ?? '_'}>
                {subgroup && (
                  <div className="config-subgroup">
                    <h4 className="config-subgroup-title">{subgroupLabel(subgroup)}</h4>
                    <code className="config-subgroup-node">{subgroup.node}</code>
                  </div>
                )}
                <div className={`config-fields${fields.every((f) => f.type === 'boolean') ? ' compact' : ''}`}>
                  {fields.map((field) => (
                    <ConfigFieldControl
                      key={keyOf(field)}
                      id={`config-field-${keyOf(field)}`}
                      field={field}
                      draft={draft}
                      flashed={flashed === keyOf(field)}
                      onChange={(value) => setValue(field, value)}
                    />
                  ))}
                </div>
              </section>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ConfigScreen;
