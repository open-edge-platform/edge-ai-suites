// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import '../../assets/css/History.css';
import { useTitleBarTheme } from '../../hooks/useTitleBarTheme';
import {
  deleteSession,
  finalizeSession,
  getSessionEvents,
  listSessionArtifacts,
  listSessions,
  type SessionArtifact,
  type SessionSummary,
  type StageEvent,
} from '../../services/api';
import { SESSION_STATES, STAGE_ORDER } from '../../generated/pipeline';
import StageArtifactModal from './StageArtifactModal';

const PAGE_SIZE = 20;

/** Keyed off the generated vocabulary, so a new stage or state needs no edit here. */
const STATE_LABELS: Record<string, string> = Object.fromEntries(
  SESSION_STATES.map((state) => [state, `history.state.${state}`]),
);

function formatTimestamp(iso: string | null): string {
  if (!iso) return '—';
  // Stored as UTC ISO; show it in the teacher's own timezone.
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

function formatDuration(seconds: number | null): string {
  if (seconds == null) return '—';
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const m = Math.floor(seconds / 60);
  return `${m}m ${Math.round(seconds % 60)}s`;
}

function describeSources(sources: SessionSummary['sources']): string {
  if (!sources) return '—';
  const parts: string[] = [];
  if (sources.audio) parts.push(sources.audio);
  for (const name of Object.values(sources.video ?? {})) parts.push(name);
  return parts.length ? parts.join(', ') : '—';
}

interface HistoryPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

/**
 * Past sessions, as a slide-over rather than a screen of its own.
 *
 * Deliberately the same surface as the report panel: a teacher checking what
 * happened last Tuesday should not have to leave the class that is recording
 * right now. Covering the workspace and sliding back off keeps the transcript
 * running underneath, and reuses a gesture the report panel already taught.
 */
const HistoryPanel: React.FC<HistoryPanelProps> = ({ isOpen, onClose }) => {
  const { t } = useTranslation();
  // The panel sits below the caption strip, so what covers it is the dim
  // backdrop rather than the panel's own white sheet.
  useTitleBarTheme(isOpen, 'dimmed');

  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [events, setEvents] = useState<StageEvent[] | null>(null);
  const [eventsLoading, setEventsLoading] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  // What the expanded row's stages left on disk, so a stage name knows whether
  // it opens anything. Keyed by stage; a stage that wrote nothing is absent.
  const [artifacts, setArtifacts] = useState<Map<string, SessionArtifact>>(new Map());
  const [preview, setPreview] = useState<{ sessionId: string; artifact: SessionArtifact } | null>(
    null,
  );
  /** The row whose detail is in flight, so a slower earlier one cannot land. */
  const detailRequest = useRef<string | null>(null);

  const load = useCallback(async (pageIndex: number) => {
    setLoading(true);
    setError(null);
    try {
      const data = await listSessions(PAGE_SIZE, pageIndex * PAGE_SIZE);
      setSessions(data.sessions ?? []);
      setTotal(data.total ?? 0);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setSessions([]);
    } finally {
      setLoading(false);
    }
  }, []);

  // Reload on open rather than on mount: the panel stays mounted between
  // visits, and a session that finished while it was closed must show up.
  useEffect(() => {
    if (isOpen) void load(page);
    // A preview left open when the panel closed must not be waiting there when
    // it opens again.
    else setPreview(null);
  }, [isOpen, load, page]);

  // Close on Escape, like every other overlay in the app — innermost first, so
  // a file preview does not take the whole panel with it.
  useEffect(() => {
    if (!isOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      if (preview) setPreview(null);
      else onClose();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [isOpen, onClose, preview]);

  // Stage timings and the files they produced are two more requests, so only
  // fetch them for the row the user actually opened rather than for every row
  // in the page.
  const toggleRow = async (sessionId: string) => {
    if (expandedId === sessionId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(sessionId);
    setEvents(null);
    setArtifacts(new Map());
    setEventsLoading(true);
    detailRequest.current = sessionId;
    const [timings, files] = await Promise.all([
      getSessionEvents(sessionId).catch(() => [] as StageEvent[]),
      // A session with no files is the normal case for a failed run, so this
      // failing must not keep the timings off the screen.
      listSessionArtifacts(sessionId).catch(() => [] as SessionArtifact[]),
    ]);
    // Opening a second row before the first answered must not repaint the one
    // now on screen with the other one's detail.
    if (detailRequest.current !== sessionId) return;
    setEvents(timings);
    setArtifacts(new Map(files.map((f) => [f.stage, f])));
    setEventsLoading(false);
  };

  const withBusy = async (sessionId: string, action: () => Promise<unknown>) => {
    setBusyId(sessionId);
    setError(null);
    try {
      await action();
      await load(page);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = (session: SessionSummary) => {
    const ok = window.confirm(
      t(
        'history.confirmDelete',
        'Delete this session and every file it produced? This cannot be undone.',
      ),
    );
    if (ok) void withBusy(session.session_id, () => deleteSession(session.session_id));
  };

  // The escape hatch for a row the browser never got to close out — a crash, or
  // a beacon that did not land. Everything else settles on its own.
  const handleMarkFailed = (session: SessionSummary) =>
    void withBusy(session.session_id, () =>
      finalizeSession(
        session.session_id,
        'failed',
        t('history.markedByUser', 'Marked as failed by the user'),
      ),
    );

  if (!isOpen) return null;

  const lastPage = Math.max(0, Math.ceil(total / PAGE_SIZE) - 1);

  return (
    <>
      <div className="history-panel-overlay open" onClick={onClose} />

      <div className="history-panel open">
        <div className="history-panel-header">
          <div>
            <div className="history-panel-title">{t('history.title', 'Session history')}</div>
            <div className="history-panel-subtitle">
              {t('history.subtitle', 'Classes recorded on this machine, newest first.')}
            </div>
          </div>
          <div className="history-panel-header-actions">
            <button className="history-btn" onClick={() => void load(page)} disabled={loading}>
              {t('history.refresh', 'Refresh')}
            </button>
            <button className="history-panel-close" onClick={onClose}>
              &times;
            </button>
          </div>
        </div>

        <div className="history-panel-body">
          {error && <div className="history-error">{error}</div>}

          {!loading && sessions.length === 0 && !error && (
            <div className="history-empty">
              {t(
                'history.empty',
                'No sessions yet. Recordings and uploads made from now on will appear here.',
              )}
            </div>
          )}

          {sessions.map((session) => {
            const expanded = expandedId === session.session_id;
            const busy = busyId === session.session_id;
            return (
              <div key={session.session_id} className="history-item">
                <div
                  className={`history-row${expanded ? ' expanded' : ''}`}
                  onClick={() => void toggleRow(session.session_id)}
                >
                  <div className="history-row-top">
                    <span className="history-caret">{expanded ? '▾' : '▸'}</span>
                    <span className="history-time">{formatTimestamp(session.started_at)}</span>
                    <span className={`history-state state-${session.state ?? 'pending'}`}>
                      {t(STATE_LABELS[session.state ?? 'pending'] ?? '', session.state ?? '—')}
                    </span>
                    <span className="history-actions" onClick={(e) => e.stopPropagation()}>
                      {session.state === 'running' && (
                        <button
                          className="history-btn"
                          disabled={busy}
                          onClick={() => handleMarkFailed(session)}
                        >
                          {t('history.markFailed', 'Mark failed')}
                        </button>
                      )}
                      <button
                        className="history-btn danger"
                        // The backend refuses to delete a running session, so do
                        // not offer it.
                        disabled={busy || session.state === 'running'}
                        onClick={() => handleDelete(session)}
                      >
                        {t('history.delete', 'Delete')}
                      </button>
                    </span>
                  </div>

                  <div className="history-row-meta">
                    <span className="history-sources" title={describeSources(session.sources)}>
                      {describeSources(session.sources)}
                    </span>
                    <span className="history-pips">
                      {STAGE_ORDER.map((stage) => {
                        const status = session.stages?.[stage] ?? 'skipped';
                        return (
                          <span
                            key={stage}
                            className={`history-pip stage-${status}`}
                            title={`${stage}: ${status}`}
                          />
                        );
                      })}
                    </span>
                  </div>
                </div>

                {expanded && (
                  <div className="history-detail">
                    <div className="history-detail-meta">
                      <span className="history-detail-id">{session.session_id}</span>
                      {session.error && (
                        <span className="history-detail-error">{session.error}</span>
                      )}
                    </div>
                    {eventsLoading && (
                      <div className="history-detail-note">{t('history.loading', 'Loading…')}</div>
                    )}
                    {!eventsLoading && events && events.length === 0 && (
                      <div className="history-detail-note">
                        {t('history.noEvents', 'No stage timings were recorded for this session.')}
                      </div>
                    )}
                    {!eventsLoading && events && events.length > 0 && (
                      <table className="history-events">
                        <thead>
                          <tr>
                            <th>{t('history.stage', 'Stage')}</th>
                            <th>{t('history.status', 'Status')}</th>
                            <th>{t('history.duration', 'Duration')}</th>
                            <th>{t('history.detail', 'Detail')}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {events.map((ev, i) => {
                            // The stage name is the handle on its output: a
                            // stage that wrote a file opens it, one that did not
                            // stays plain text rather than a button that
                            // apologises.
                            const artifact = ev.stage ? artifacts.get(ev.stage) : undefined;
                            return (
                              <tr key={`${ev.stage}-${i}`}>
                                <td>
                                  {artifact ? (
                                    <button
                                      type="button"
                                      className="history-stage-link"
                                      title={t('history.openFile', 'Open {{file}}', {
                                        file: artifact.filename,
                                      })}
                                      onClick={() =>
                                        setPreview({ sessionId: session.session_id, artifact })
                                      }
                                    >
                                      {ev.stage}
                                    </button>
                                  ) : (
                                    ev.stage
                                  )}
                                </td>
                                <td className={`stage-text-${ev.status}`}>{ev.status}</td>
                                <td>{formatDuration(ev.duration_sec)}</td>
                                <td className="history-events-detail">
                                  {ev.error_detail
                                    ? `${ev.error_class}: ${ev.error_detail}`
                                    : formatTimestamp(ev.ended_at)}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {total > PAGE_SIZE && (
          <div className="history-pager">
            <button
              className="history-btn"
              disabled={page === 0}
              onClick={() => setPage((p) => p - 1)}
            >
              {t('history.prev', 'Previous')}
            </button>
            <span className="history-pager-label">
              {t('history.pageOf', '{{page}} / {{pages}}', { page: page + 1, pages: lastPage + 1 })}
            </span>
            <button
              className="history-btn"
              disabled={page >= lastPage}
              onClick={() => setPage((p) => p + 1)}
            >
              {t('history.next', 'Next')}
            </button>
          </div>
        )}
      </div>

      {preview && (
        <StageArtifactModal
          sessionId={preview.sessionId}
          artifact={preview.artifact}
          onClose={() => setPreview(null)}
        />
      )}
    </>
  );
};

export default HistoryPanel;
