// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// Landing screen whenever the machine is not ready to run. Stays reachable once
// everything is green, so "why won't the backend start?" always has one answer.

import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import '../../assets/css/Config.css';
import '../../assets/css/GetStarted.css';
import type { ConfigChange, ConfigField, ConfigValue } from '../../types/config';
import { useConfig, fieldKey as keyOf } from '../../services/configManager';
import { useServices } from '../../services/serviceManager';
import { useSetup } from '../../services/setupManager';
import { useReadiness, type ReadinessItem } from '../../services/useReadiness';
import ConfigFieldControl from './ConfigFieldControl';

type Draft = Record<string, ConfigValue>;

interface GetStartedScreenProps {
  /** `target` deep-links to one row: a setup step id, or a config field path. */
  onOpenScreen: (screen: 'services' | 'config' | 'setup', target?: string) => void;
}

const GetStartedScreen: React.FC<GetStartedScreenProps> = ({ onOpenScreen }) => {
  const { t } = useTranslation();
  const { steps, check } = useSetup();
  const { services, busyId: serviceBusy, start, error: serviceError } = useServices();
  const { description, saving, save } = useConfig();
  const { items, ready } = useReadiness(steps, services, description);

  const [draft, setDraft] = useState<Draft>({});
  // A setup run started on the Setup screen is global state, so this screen has
  // to respect it even though it never starts one itself.
  const setupRunning = steps.some((step) => step.status === 'running');
  const busy = !!serviceBusy || saving || setupRunning;

  const commonFields = useMemo(
    () => description?.fields.filter((field) => field.wizard) ?? [],
    [description]
  );
  const groups = useMemo(() => {
    const seen = new Map<string, ConfigField[]>();
    for (const field of commonFields) {
      if (!seen.has(field.group)) seen.set(field.group, []);
      seen.get(field.group)!.push(field);
    }
    return [...seen.entries()];
  }, [commonFields]);

  const dirty = Object.keys(draft);

  const handleSave = async () => {
    if (!description) return;
    const changes: ConfigChange[] = commonFields
      .filter((field) => draft[keyOf(field)] !== undefined)
      .map((field) => ({ file: field.file, path: field.path, value: draft[keyOf(field)] }));
    if (changes.length && (await save(changes))) setDraft({});
  };

  // This screen never runs setup work itself. So each row points at the place
  // that can do the job and show it happening.
  const renderItemAction = (item: ReadinessItem) => {
    if (item.state === 'ok' || item.state === 'pending') return null;

    if (item.id === 'prerequisites' || item.id === 'environment') {
      return (
        <button className="gs-btn gs-btn-primary" disabled={busy} onClick={() => onOpenScreen('setup', item.focus)}>
          {t('getStarted.openSetup', 'Open Setup')}
        </button>
      );
    }

    if (item.id === 'settings') {
      return (
        <button className="gs-btn" disabled={busy} onClick={() => onOpenScreen('config', item.focus)}>
          {t('getStarted.openConfig', 'Open Configuration')}
        </button>
      );
    }

    if (item.id === 'services') {
      const backend = services.find((service) => service.id === 'backend');
      return (
        <button
          className="gs-btn gs-btn-primary"
          disabled={busy || !backend?.runnable}
          onClick={() => {
            // Startup takes a while; the Services screen is where the logs are.
            void start('backend');
            onOpenScreen('services');
          }}
        >
          {t('getStarted.startBackend', 'Start backend')}
        </button>
      );
    }


    return null;
  };

  return (
    <div className="gs-screen">
      <div className="gs-body">
        <div className="gs-header">
          <div>
            <h3 className="gs-title">{t('getStarted.title', 'Get started')}</h3>
            <span className="gs-subtitle">
              {ready
                ? t('getStarted.allReady', 'Everything is ready. The backend is running.')
                : t('getStarted.subtitle', 'Finish these steps to run Smart Classroom.')}
            </span>
          </div>
          <button className="gs-btn" disabled={busy} onClick={check}>
            {t('getStarted.recheck', 'Re-check')}
          </button>
        </div>

        {serviceError && <div className="config-error">{serviceError}</div>}

        <ol className="gs-list">
          {items.map((item, index) => (
            <li key={item.id} className={`gs-item state-${item.state}`}>
              <span className="gs-index">{item.state === 'ok' ? '✓' : index + 1}</span>
              <div className="gs-item-text">
                <span className="gs-item-label">{t(`getStarted.items.${item.id}`, item.id)}</span>
                <span className="gs-item-detail">{item.detail}</span>
              </div>
              <div className="gs-item-action">{renderItemAction(item)}</div>
            </li>
          ))}
        </ol>

        <section className="gs-settings">
          <div className="gs-settings-header">
            <div>
              <h4 className="gs-settings-title">{t('getStarted.commonTitle', 'Commonly used settings')}</h4>
              <span className="gs-subtitle">
                {t('getStarted.commonSubtitle', 'The settings most people change. The full list is under Configuration.')}
              </span>
            </div>
            <div className="gs-settings-actions">
              <button className="gs-btn" disabled={busy} onClick={() => onOpenScreen('config')}>
                {t('getStarted.allSettings', 'All settings')}
              </button>
              <button className="gs-btn gs-btn-primary" disabled={!dirty.length || busy} onClick={handleSave}>
                {saving
                  ? t('getStarted.saving', 'Saving…')
                  : t('getStarted.save', 'Save {{count}} change', { count: dirty.length })}
              </button>
            </div>
          </div>

          {groups.map(([group, fields]) => (
            <div className="gs-group" key={group}>
              <h5 className="gs-group-title">{t(`config.groups.${group}`, group)}</h5>
              <div className={`config-fields${fields.every((f) => f.type === 'boolean') ? ' compact' : ''}`}>
                {fields.map((field) => (
                  <ConfigFieldControl
                    key={keyOf(field)}
                    field={field}
                    draft={draft}
                    onChange={(value) => setDraft((previous) => ({ ...previous, [keyOf(field)]: value }))}
                  />
                ))}
              </div>
            </div>
          ))}
        </section>
      </div>
    </div>
  );
};

export default GetStartedScreen;
