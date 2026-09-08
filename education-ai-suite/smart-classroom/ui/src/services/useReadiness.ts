// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// Derives "is this machine ready to run?" from live state only.
//
// Nothing is persisted: a stored "setup complete" flag would keep claiming
// success after the Python environment is deleted, upgraded or moved.

import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import type { ConfigDescription, ConfigProblem } from '../types/config';
import type { ServiceSnapshot } from '../types/services';
import type { SetupStep } from '../types/setup';

export type ReadinessState = 'ok' | 'blocked' | 'attention' | 'pending';

export interface ReadinessItem {
  id: 'prerequisites' | 'environment' | 'settings' | 'services';
  state: ReadinessState;
  detail: string;
  /** Setup steps behind this item, so the screen can offer their fix actions. */
  steps: SetupStep[];
  /**
   * What to jump to on the target screen: a setup step id, or a config field
   * path. Without it the user lands on a long list and has to hunt for the one
   * row this item is complaining about.
   */
  focus?: string;
}

const ENVIRONMENT_STEPS = ['venv', 'gradingVenv', 'layoutModel'];

const isBad = (step: SetupStep) => step.status === 'missing' || step.status === 'failed';
const isWarn = (step: SetupStep) => step.status === 'warn';
// A step being fixed is neither bad nor warn. Without this it drops out of both
// lists and the item claims to be ready while the work is still running.
const isRunning = (step: SetupStep) => step.status === 'running';

/**
 * Config is always structurally valid, so "reviewed" is not derivable. Only
 * genuine contradictions are reported, and those come from the rule set in
 * config-schema.cjs.
 *
 * One entry per rule, so a rule spanning two fields is not reported twice.
 */
function ruleProblems(problems: ConfigProblem[]): ConfigProblem[] {
  const seen = new Set<string>();
  return problems.filter((problem) => {
    if (seen.has(problem.rule)) return false;
    seen.add(problem.rule);
    return true;
  });
}

/**
 * @param problems cross-field problems in the *saved* config. Pending edits are
 *   deliberately excluded: this drives whether the machine is ready to run, and
 *   a half-typed value is not the state of the system.
 */
export function useReadiness(
  steps: SetupStep[],
  services: ServiceSnapshot[],
  description: ConfigDescription | null,
  configProblems: ConfigProblem[] = []
): { items: ReadinessItem[]; ready: boolean; blocked: boolean } {
  const { t } = useTranslation();

  return useMemo(() => {
    const checked = steps.filter((step) => step.status !== 'unknown');
    const environment = steps.filter((step) => ENVIRONMENT_STEPS.includes(step.id));
    const prerequisites = steps.filter((step) => !ENVIRONMENT_STEPS.includes(step.id));
    const backend = services.find((service) => service.id === 'backend');
    const problems = ruleProblems(configProblems);

    const prerequisiteBad = prerequisites.filter(isBad);
    const prerequisiteWarn = prerequisites.filter(isWarn);
    const prerequisiteRunning = prerequisites.filter(isRunning);
    const environmentBad = environment.filter(isBad);
    const environmentRunning = environment.filter(isRunning);

    const working = (running: SetupStep[]) =>
      t('getStarted.details.working', 'Setting up: {{items}}…', {
        items: running.map((s) => s.label).join(', '),
      });

    const items: ReadinessItem[] = [
      {
        id: 'prerequisites',
        state: !checked.length
          ? 'pending'
          : prerequisiteRunning.length
            ? 'pending'
            : prerequisiteBad.length
              ? 'blocked'
              : prerequisiteWarn.length
                ? 'attention'
                : 'ok',
        detail: !checked.length
          ? t('getStarted.details.checking', 'Checking…')
          : prerequisiteRunning.length
            ? working(prerequisiteRunning)
            : prerequisiteBad.length
              ? t('getStarted.details.missing', 'Missing: {{items}}', {
                  items: prerequisiteBad.map((s) => s.label).join(', '),
                })
              : prerequisiteWarn.length
                ? t('getStarted.details.warnings', 'Warnings: {{items}}', {
                    items: prerequisiteWarn.map((s) => s.label).join(', '),
                  })
                : t('getStarted.details.prereqOk', 'System, drivers and tools are in place'),
        steps: [...prerequisiteBad, ...prerequisiteWarn],
        focus: (prerequisiteBad[0] ?? prerequisiteWarn[0])?.id,
      },
      {
        id: 'environment',
        state: !checked.length
          ? 'pending'
          : environmentRunning.length
            ? 'pending'
            : environmentBad.length
              ? 'blocked'
              : 'ok',
        detail: !checked.length
          ? t('getStarted.details.checking', 'Checking…')
          : environmentRunning.length
            ? working(environmentRunning)
            : environmentBad.length
              ? environmentBad.map((s) => s.label).join(', ')
              : t('getStarted.details.envOk', 'Python environment and models are ready'),
        steps: environmentBad,
        focus: environmentBad[0]?.id,
      },
      {
        id: 'settings',
        state: !description ? 'pending' : problems.length ? 'attention' : 'ok',
        detail: !description
          ? t('getStarted.details.loading', 'Loading…')
          : problems.length
            ? problems.map((problem) => problem.message).join(' ')
            : t('getStarted.details.settingsOk', 'Review the commonly used settings'),
        steps: [],
        focus: problems[0]?.path,
      },
      {
        id: 'services',
        state:
          backend?.status === 'healthy'
            ? 'ok'
            : backend?.status === 'starting'
              ? 'pending'
              : backend?.runnable === false
                ? 'blocked'
                : 'attention',
        detail:
          backend?.status === 'healthy'
            ? t('getStarted.details.backendRunning', 'Backend is running')
            : backend?.status === 'starting'
              ? t('getStarted.details.backendStarting', 'Backend is starting…')
              : backend?.runnable === false
                ? t('getStarted.details.backendNeedsEnv', 'Create the Python environment first')
                : t('getStarted.details.backendStopped', 'Backend is not running'),
        steps: [],
      },
    ];

    return {
      items,
      ready: items.every((item) => item.state === 'ok'),
      blocked: items.some((item) => item.state === 'blocked' || item.state === 'attention'),
    };
  }, [steps, services, description, configProblems, t]);
}
