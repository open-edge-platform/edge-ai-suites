// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import '../../assets/css/Setup.css';
// The log pane is shared with the Services screen, and its classes live there.
import '../../assets/css/Services.css';
import type { SetupStep } from '../../types/setup';
import { copyText, revealSetupLogs, useSetup, useSetupLogs } from '../../services/setupManager';
import { useServices } from '../../services/serviceManager';
import LogViewer from '../Services/LogViewer';

const STATUS_LABELS: Record<string, string> = {
  unknown: 'setup.status.unknown',
  ok: 'setup.status.ok',
  warn: 'setup.status.warn',
  missing: 'setup.status.missing',
  running: 'setup.status.running',
  failed: 'setup.status.failed',
};

/** The action a bulk "fix" run would use: the first non-destructive one. */
const repairAction = (step: SetupStep) =>
  step.status === 'missing' || step.status === 'failed'
    ? step.actions.find((action) => !action.destructive)
    : undefined;

interface SetupScreenProps {
  /** Where to hand over once there is nothing left to fix. */
  onOpenScreen?: (screen: 'services' | 'ready') => void;
  /** Step to scroll to and flag on arrival, when opened from Get started. */
  focusStepId?: string | null;
}

const SetupScreen: React.FC<SetupScreenProps> = ({ onOpenScreen, focusStepId }) => {
  const { t } = useTranslation();
  const { sections, steps, error, busyId, checking, check, run, cancel } = useSetup();
  const { services, start } = useServices();
  const { lines, clear: clearLogs } = useSetupLogs();
  const [runningAll, setRunningAll] = useState(false);
  const [copied, setCopied] = useState(false);
  const stepRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const consumedFocus = useRef<string | null>(null);
  const [flashed, setFlashed] = useState<string | null>(null);

  // Fourteen rows is enough to have to hunt for the one Get started meant.
  // steps.length is a dependency because the rows may not exist yet on arrival.
  useEffect(() => {
    if (!focusStepId || consumedFocus.current === focusStepId) return;
    const node = stepRefs.current[focusStepId];
    if (!node) return;
    consumedFocus.current = focusStepId;

    node.scrollIntoView({ block: 'center', behavior: 'smooth' });
    setFlashed(focusStepId);
    const timer = setTimeout(() => setFlashed(null), 2200);
    return () => clearTimeout(timer);
  }, [focusStepId, steps.length]);

  const pending = useMemo(
    () => steps.map((step) => ({ step, action: repairAction(step) })).filter((entry) => entry.action),
    [steps]
  );
  const grouped = useMemo(
    () =>
      sections
        .map((section) => ({ section, items: steps.filter((step) => step.section === section.id) }))
        .filter((entry) => entry.items.length > 0),
    [sections, steps]
  );
  const busy = !!busyId || runningAll;

  // "Nothing left to fix", not "a run finished": a fully prepared machine gets
  // the same confirmation the first time it opens this screen.
  const checked = steps.some((step) => step.status !== 'unknown');
  const working = busy || checking || steps.some((step) => step.status === 'running');
  const settled = checked && !working && !pending.length;

  // Warnings do not block anything, so they must not block the handover — but
  // claiming "everything is ready" while one stands would be a lie.
  const warnings = steps.filter((step) => step.status === 'warn');

  // Steps that cannot run yet because something they need is not OK. Without
  // this the buttons are live and fail with "Create the Python environment
  // first" only after being clicked.
  const blockedBy = useMemo(() => {
    const byId = new Map(steps.map((step) => [step.id, step]));
    const map: Record<string, string[]> = {};
    for (const step of steps) {
      const unmet = step.requires
        .map((id) => byId.get(id))
        .filter((required): required is SetupStep => !!required && required.status !== 'ok')
        .map((required) => required.label);
      if (unmet.length) map[step.id] = unmet;
    }
    return map;
  }, [steps]);

  const diagnostics = () => {
    const rows = steps.map(
      (step) => `${step.status.padEnd(8)} ${step.label}${step.optional ? ' (optional)' : ''}\n           ${step.detail}`
    );
    return [
      `Smart Classroom setup — ${new Date().toISOString()}`,
      `${navigator.userAgent}`,
      '',
      ...rows,
    ].join('\n');
  };

  const backend = services.find((service) => service.id === 'backend');
  const backendHealthy = backend?.status === 'healthy';
  const backendStartable =
    !!backend?.runnable && (backend.status === 'stopped' || backend.status === 'failed');

  // Sequential on purpose: later steps depend on earlier ones (the environment
  // must exist before packages install into it).
  const runAll = async () => {
    setRunningAll(true);
    try {
      for (const { step, action } of pending) {
        if (!(await run(step.id, action!.id))) break;
      }
    } finally {
      setRunningAll(false);
    }
  };

  return (
    <div className="setup-screen">
      <div className="setup-header">
        <div className="setup-heading">
          <h3 className="setup-title">{t('setup.title', 'Setup')}</h3>
          <span className="setup-subtitle">
            {t('setup.subtitle', 'Check prerequisites and prepare the Python environment and models.')}
          </span>
        </div>
        <div className="setup-actions">
          <button className="setup-btn" disabled={busy || checking} onClick={check}>
            {checking ? t('setup.checking', 'Checking…') : t('setup.recheck', 'Re-check')}
          </button>
          <button
            className="setup-btn"
            disabled={!checked}
            onClick={async () => {
              await copyText(diagnostics()).catch(() => undefined);
              setCopied(true);
              setTimeout(() => setCopied(false), 1800);
            }}
          >
            {copied ? t('setup.copied', 'Copied') : t('setup.copyDiagnostics', 'Copy diagnostics')}
          </button>
          {busy ? (
            <button className="setup-btn" onClick={() => cancel().catch(() => undefined)}>
              {t('setup.cancel', 'Cancel')}
            </button>
          ) : (
            <button className="setup-btn setup-btn-primary" disabled={!pending.length} onClick={runAll}>
              {t('setup.runAll', 'Fix {{count}} item', { count: pending.length })}
            </button>
          )}
        </div>
      </div>

      {error && <div className="setup-error">{error}</div>}

      {/* The environment is what everything else waits on, so lead with it. */}
      {steps.some((step) => step.id === 'venv' && (step.status === 'missing' || step.status === 'failed')) && (
        <div className="setup-banner">
          {t(
            'setup.firstRun',
            'The Python environment is missing, so the backend cannot start. Select Fix to create it — the first run downloads several gigabytes.'
          )}
        </div>
      )}

      {/* Finishing the last step otherwise just leaves the user staring at a
          log. Offer the next move rather than navigating for them: they may
          still be reading the output. */}
      {settled && (
        <div className="setup-banner setup-banner-done">
          <span>
            {backendHealthy
              ? t('setup.allReadyRunning', 'Everything is ready and the backend is running.')
              : warnings.length
                ? t('setup.settledWithWarnings', 'Nothing left to fix — {{count}} warning remains.', {
                    count: warnings.length,
                  })
                : t('setup.allReady', 'Everything is ready.')}
          </span>
          <div className="setup-actions">
            {backendStartable && (
              <button
                className="setup-btn setup-btn-primary"
                onClick={() => {
                  // Startup is slow; Services is where the logs are.
                  void start('backend');
                  onOpenScreen?.('services');
                }}
              >
                {t('setup.startBackend', 'Start backend')}
              </button>
            )}
            <button className="setup-btn" onClick={() => onOpenScreen?.('ready')}>
              {t('setup.backToGetStarted', 'Back to Get started')}
            </button>
          </div>
        </div>
      )}

      <div className="setup-split">
        <div className="setup-list">
          {grouped.map(({ section, items }) => (
            <section className="setup-section" key={section.id}>
              <h4 className="setup-section-title">{t(`setup.sections.${section.id}`, section.label)}</h4>
              {items.map((step) => (
                <div
                  key={step.id}
                  ref={(node) => {
                    stepRefs.current[step.id] = node;
                  }}
                  className={`setup-step status-${step.status}${flashed === step.id ? ' flashed' : ''}`}
                >
                  <div className="setup-step-top">
                    <span className={`setup-dot status-${step.status}`} />
                    <span className="setup-step-label">{step.label}</span>
                    {step.optional && <span className="setup-badge">{t('setup.optional', 'optional')}</span>}
                    <span className="setup-step-status">
                      {t(STATUS_LABELS[step.status] ?? step.status, step.status)}
                    </span>
                  </div>
                  <div className="setup-step-detail">{step.detail}</div>
                  {step.hint &&
                    (/^https?:\/\//.test(step.hint) ? (
                      // target=_blank hits the main process window-open handler,
                      // which sends it to the OS browser instead of the app window.
                      <a className="setup-step-link" href={step.hint} target="_blank" rel="noreferrer">
                        {step.hint}
                      </a>
                    ) : (
                      <code className="setup-step-hint">{step.hint}</code>
                    ))}
                  {blockedBy[step.id] && (
                    <div className="setup-step-blocked">
                      {t('setup.blockedBy', 'Needs {{items}} first.', { items: blockedBy[step.id].join(', ') })}
                    </div>
                  )}
                  {step.actions.length > 0 && busyId !== step.id && (
                    <div className="setup-step-actions">
                      {step.actions.map((action) => (
                        <button
                          key={action.id}
                          className={`setup-btn${action.destructive ? ' setup-btn-danger' : ''}`}
                          disabled={busy || step.status === 'unknown' || !!blockedBy[step.id]}
                          onClick={() => run(step.id, action.id)}
                        >
                          {action.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </section>
          ))}
        </div>

        <LogViewer
          lines={lines}
          title={t('setup.output', 'Output')}
          onClear={clearLogs}
          onReveal={() => revealSetupLogs().catch(() => undefined)}
        />
      </div>
    </div>
  );
};

export default SetupScreen;
