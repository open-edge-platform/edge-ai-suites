// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import '../../assets/css/Services.css';
import type { ServiceSnapshot } from '../../types/services';
import { revealLogs, useServiceLogs, useServices } from '../../services/serviceManager';
import LogViewer from './LogViewer';

const STATUS_LABELS: Record<string, string> = {
  stopped: 'services.status.stopped',
  starting: 'services.status.starting',
  healthy: 'services.status.healthy',
  degraded: 'services.status.degraded',
  stopping: 'services.status.stopping',
  failed: 'services.status.failed',
};

function formatUptime(ms: number | null): string {
  if (!ms || ms < 0) return '—';
  const seconds = Math.floor(ms / 1000);
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours) return `${hours}h ${minutes}m`;
  if (minutes) return `${minutes}m ${seconds % 60}s`;
  return `${seconds}s`;
}

interface TreeNode {
  service: ServiceSnapshot;
  depth: number;
}

/** Depth-first flatten of the ownedBy graph, so children render under their owner. */
function buildTree(services: ServiceSnapshot[]): TreeNode[] {
  const present = new Set(services.map((service) => service.id));
  const nodes: TreeNode[] = [];
  const walk = (parentId: string | null, depth: number) => {
    for (const service of services) {
      const owner = service.ownedBy && present.has(service.ownedBy) ? service.ownedBy : null;
      if (owner !== parentId) continue;
      nodes.push({ service, depth });
      walk(service.id, depth + 1);
    }
  };
  walk(null, 0);
  return nodes;
}

const ServicesScreen: React.FC = () => {
  const { t } = useTranslation();
  const { services, error, busyId, start, stop, restart } = useServices();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  // Held here rather than inside LogViewer, which is now shared with Setup.
  const { lines: logLines, clear: clearLogLines } = useServiceLogs(selectedId);
  // Uptime is derived from a timestamp, so tick locally instead of asking the
  // main process to push a snapshot every second.
  const [, setTick] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => setTick((value) => value + 1), 1000);
    return () => clearInterval(interval);
  }, []);

  const visible = useMemo(() => services.filter((service) => service.enabled), [services]);
  const disabled = useMemo(() => services.filter((service) => !service.enabled), [services]);
  const tree = useMemo(() => buildTree(visible), [visible]);
  const controllable = useMemo(() => visible.filter((service) => service.managed), [visible]);

  useEffect(() => {
    if (!selectedId && visible.length) setSelectedId(controllable[0]?.id ?? visible[0].id);
  }, [visible, controllable, selectedId]);

  const renderControls = (service: ServiceSnapshot) => {
    const busy = busyId === service.id;
    const running = service.status !== 'stopped' && service.status !== 'failed';
    return (
      <div className="services-actions" key={service.id}>
        {controllable.length > 1 && <span className="services-actions-label">{service.label}</span>}
        <button className="services-btn" disabled={busy || running || !service.runnable} onClick={() => start(service.id)}>
          {t('services.start', 'Start')}
        </button>
        <button className="services-btn" disabled={busy || !running} onClick={() => stop(service.id)}>
          {t('services.stop', 'Stop')}
        </button>
        <button
          className="services-btn"
          disabled={busy || service.external || !service.runnable}
          onClick={() => restart(service.id)}
        >
          {t('services.restart', 'Restart')}
        </button>
      </div>
    );
  };

  return (
    <div className="services-screen">
      <div className="services-header">
        <div className="services-heading">
          <h3 className="services-title">{t('services.title', 'Services')}</h3>
          <span className="services-subtitle">
            {t('services.subtitle', 'Start, stop and inspect the backend processes.')}
          </span>
        </div>
        {controllable.map(renderControls)}
      </div>

      {error && <div className="services-error">{error}</div>}

      {controllable.some((service) => !service.runnable) && (
        <div className="services-banner">
          {t(
            'services.needsSetup',
            'The Python environment is missing. Create it on the Setup screen before starting the backend.'
          )}
        </div>
      )}

      <div className="services-split">
        <div className="services-pane">
          <div className="services-list">
            {tree.map(({ service, depth }) => (
              <div
                key={service.id}
                className={`services-row${selectedId === service.id ? ' selected' : ''}`}
                onClick={() => setSelectedId(service.id)}
              >
                <div className="services-row-top" style={{ paddingLeft: depth * 14 }}>
                  {depth > 0 && <span className="services-tree-branch">└</span>}
                  <span className={`services-dot status-${service.status}`} />
                  <span className="services-row-name">{service.label}</span>
                  {service.external && <span className="services-badge">{t('services.external', 'external')}</span>}
                  <span className="services-row-status">
                    {t(STATUS_LABELS[service.status] ?? service.status, service.status)}
                  </span>
                </div>
                <div className="services-row-meta" style={{ paddingLeft: depth * 14 }}>
                  {[
                    service.port ? `:${service.port}` : null,
                    service.pid ? `pid ${service.pid}` : null,
                    service.uptimeMs ? formatUptime(service.uptimeMs) : null,
                  ]
                    .filter(Boolean)
                    .join('  ·  ') || '—'}
                </div>
              </div>
            ))}
          </div>

          {visible.some((service) => service.error) && (
            <div className="services-error">
              {visible
                .filter((service) => service.error)
                .map((service) => `${service.label}: ${service.error}`)
                .join(' · ')}
            </div>
          )}

          {disabled.length > 0 && (
            <div className="services-disabled-note">
              {t('services.disabledIn', 'Disabled in config.yaml')}:{' '}
              {disabled.map((service) => service.label).join(', ')}
            </div>
          )}
        </div>

        <LogViewer
          lines={logLines}
          title={visible.find((service) => service.id === selectedId)?.label ?? ''}
          onClear={selectedId ? clearLogLines : undefined}
          onReveal={selectedId ? () => revealLogs(selectedId).catch(() => undefined) : undefined}
        />
      </div>
    </div>
  );
};

export default ServicesScreen;
