// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { LogLine } from '../../types/services';

// Presentational on purpose: the Services screen feeds it one service's log and
// the Setup screen feeds it the setup log, so filter/follow/clear/open-folder
// exist once rather than twice.
interface LogViewerProps {
  lines: LogLine[];
  title: string;
  onClear?: () => void;
  onReveal?: () => void;
}

const LogViewer: React.FC<LogViewerProps> = ({ lines, title, onClear, onReveal }) => {
  const { t } = useTranslation();
  const [filter, setFilter] = useState('');
  const [follow, setFollow] = useState(true);
  const bodyRef = useRef<HTMLDivElement>(null);

  const visible = useMemo(() => {
    if (!filter.trim()) return lines;
    const needle = filter.toLowerCase();
    return lines.filter((line) => line.text.toLowerCase().includes(needle));
  }, [lines, filter]);

  useEffect(() => {
    if (follow && bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
  }, [visible, follow]);

  return (
    <div className="services-logs">
      <div className="services-logs-header">
        <span className="services-logs-title">
          {t('services.logs.title', 'Logs')}
          {title ? ` — ${title}` : ''}
        </span>
        <input
          className="services-logs-filter"
          value={filter}
          placeholder={t('services.logs.filter', 'Filter…')}
          onChange={(event) => setFilter(event.target.value)}
        />
        <label className="services-logs-follow">
          <input type="checkbox" checked={follow} onChange={(event) => setFollow(event.target.checked)} />
          {t('services.logs.follow', 'Follow')}
        </label>
        <button className="services-btn" onClick={onClear} disabled={!onClear}>
          {t('services.logs.clear', 'Clear')}
        </button>
        {onReveal && (
          <button className="services-btn" onClick={onReveal}>
            {t('services.logs.openFolder', 'Open folder')}
          </button>
        )}
      </div>
      <div className="services-logs-body" ref={bodyRef}>
        {visible.length === 0 ? (
          <div className="services-logs-empty">{t('services.logs.empty', 'No output captured yet.')}</div>
        ) : (
          visible.map((line) => (
            <div key={line.seq} className={`services-log-line stream-${line.stream}`}>
              <span className="services-log-time">{new Date(line.ts).toLocaleTimeString()}</span>
              <span className="services-log-text">{line.text}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default LogViewer;
