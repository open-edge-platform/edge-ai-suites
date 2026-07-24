import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  gradingPauseTask,
  gradingResumeTask,
  gradingDeleteTask,
  gradingGetTaskLog,
  gradingGetTaskSummary,
} from '../../services/api';
import type { GradingTask, GradingSummary } from '../../services/api';
import RemoveConfirmationModal from '../common/RemoveConfirmationModal';

interface TaskDetailProps {
  task: GradingTask;
  onControlled: (task: GradingTask) => void;
  onDeleted: (taskId: string) => void;
  onViewResults: (taskId: string) => void;
}

const LOG_POLL_MS = 3000;
const LOG_TAIL = 50;

// Format elapsed time between two ISO timestamps as "1h 03m 05s" / "45s".
const formatElapsed = (fromIso?: string, toIso?: string | null): string => {
  if (!fromIso) return '—';
  const start = Date.parse(fromIso);
  const end = toIso ? Date.parse(toIso) : Date.now();
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return '—';
  let s = Math.floor((end - start) / 1000);
  const h = Math.floor(s / 3600);
  s -= h * 3600;
  const m = Math.floor(s / 60);
  s -= m * 60;
  if (h > 0) return `${h}h ${String(m).padStart(2, '0')}m ${String(s).padStart(2, '0')}s`;
  if (m > 0) return `${m}m ${String(s).padStart(2, '0')}s`;
  return `${s}s`;
};

const TaskDetail: React.FC<TaskDetailProps> = ({ task, onControlled, onDeleted, onViewResults }) => {
  const { t } = useTranslation();
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [logLines, setLogLines] = useState<string[]>([]);
  const [logError, setLogError] = useState<string>('');
  const [confirmDelete, setConfirmDelete] = useState<boolean>(false);
  const [summary, setSummary] = useState<GradingSummary | null>(null);
  const [logModalOpen, setLogModalOpen] = useState<boolean>(false);
  const [fullLogLines, setFullLogLines] = useState<string[]>([]);
  const [fullLogLoading, setFullLogLoading] = useState<boolean>(false);

  const status = task.status;
  const isTerminal = status === 'COMPLETED' || status === 'FAILED' || status === 'CANCELLED';

  const canPause = status === 'RUNNING';
  const canResume = status === 'PAUSED';

  const info = task.dir_info || null;
  const dash = '—';

  const logBoxRef = useRef<HTMLPreElement | null>(null);
  const logTimeoutRef = useRef<number | null>(null);
  const logCancelledRef = useRef<boolean>(false);

  useEffect(() => {
    logCancelledRef.current = false;
    const fetchLog = async () => {
      try {
        const [logRes, summaryRes] = await Promise.all([
          gradingGetTaskLog(task.task_id, LOG_TAIL),
          gradingGetTaskSummary(task.task_id),
        ]);
        if (logCancelledRef.current) return;
        setLogLines(logRes.lines || []);
        setLogError('');
        setSummary(summaryRes);
      } catch (e) {
        if (logCancelledRef.current) return;
        setLogError(e instanceof Error ? e.message : String(e));
      }
    };
    const poll = async () => {
      if (logCancelledRef.current) return;
      await fetchLog();
      if (!logCancelledRef.current && !isTerminal) {
        logTimeoutRef.current = window.setTimeout(poll, LOG_POLL_MS);
      }
    };
    poll();
    return () => {
      logCancelledRef.current = true;
      if (logTimeoutRef.current) {
        clearTimeout(logTimeoutRef.current);
        logTimeoutRef.current = null;
      }
    };
  }, [task.task_id, isTerminal]);

  // Keep the log box scrolled to the newest line.
  useEffect(() => {
    if (logBoxRef.current) {
      logBoxRef.current.scrollTop = logBoxRef.current.scrollHeight;
    }
  }, [logLines]);

  const run = async (fn: () => Promise<GradingTask>) => {
    setBusy(true);
    setError('');
    try {
      onControlled(await fn());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const processing = info?.current
    ? info.current
    : task.current_step && !isTerminal
    ? task.current_step
    : dash;

  const elapsed = formatElapsed(task.created_at, isTerminal ? task.updated_at : null);

  return (
    <div className="grading-detail">
      <div className="grading-detail-progress">
        <span className="grading-count">
          {t('grading.detail.total', 'Total')}: {info ? info.total : dash}
        </span>
        <span className="grading-count">
          {t('grading.detail.completed', 'Completed')}: {info ? info.completed : dash}
        </span>
        <span className="grading-count">
          {t('grading.detail.failed', 'Failed')}: {info ? info.failed : dash}
        </span>
        <span className="grading-count">
          {t('grading.detail.processing', 'Processing')}: {processing}
        </span>
      </div>

      <div className="grading-detail-meta">
        <span>
          {t('grading.detail.rubric', 'Rubric')}: {info?.rubric_name || dash}
        </span>
        <span>
          {t('grading.detail.elapsed', 'Elapsed')}: {elapsed}
        </span>
      </div>

      {task.error_message && <div className="grading-error">{task.error_message}</div>}
      {error && <div className="grading-error">{error}</div>}

      <div className="grading-log-row">
        {task.dir_info && (
          <div className="grading-timing">
            <div className="grading-log-title">{t('grading.detail.timing', 'Processing time')}</div>
            <table className="grading-timing-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>{t('grading.detail.timingStudent', 'Student')}</th>
                  <th>{t('grading.detail.timingSeconds', 'Time (s)')}</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(summary?.students || {}).map(([key, s], idx) => (
                  <tr key={key}>
                    <td>{idx + 1}</td>
                    <td>{s.student_name || s.student_id || key}</td>
                    <td>{s.processing_seconds != null ? s.processing_seconds.toFixed(1) : '—'}</td>
                  </tr>
                ))}
                {summary?.total_processing_seconds != null && (
                  <tr className="grading-timing-total">
                    <td></td>
                    <td><strong>{t('grading.detail.timingTotal', 'Total')}</strong></td>
                    <td><strong>{summary.total_processing_seconds.toFixed(1)}</strong></td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        <div className="grading-log">
          <div className="grading-log-title-row">
            <span className="grading-log-title">{t('grading.detail.log', 'Live log')}</span>
            <button className="grading-log-expand" onClick={async () => {
              setLogModalOpen(true);
              setFullLogLoading(true);
              try {
                const res = await gradingGetTaskLog(task.task_id, 5000);
                setFullLogLines(res.lines || []);
              } catch {
                setFullLogLines(logLines);
              } finally {
                setFullLogLoading(false);
              }
            }} title={t('grading.detail.logExpand', 'Expand')}>⤢</button>
          </div>
          {logError && <div className="grading-error">{logError}</div>}
          <pre className="grading-log-box" ref={logBoxRef}>
            {logLines.length > 0
              ? logLines.join('\n')
              : t('grading.detail.logEmpty', 'No log output yet.')}
          </pre>
        </div>

        <div className="grading-detail-actions">
          <button
            className="grading-btn grading-btn-secondary"
            disabled={!canPause || busy}
            onClick={() => run(() => gradingPauseTask(task.task_id))}
          >
            {t('grading.detail.pause', 'Pause')}
          </button>
          <button
            className="grading-btn grading-btn-secondary"
            disabled={!canResume || busy}
            onClick={() => run(() => gradingResumeTask(task.task_id))}
          >
            {t('grading.detail.resume', 'Resume')}
          </button>
          <button
            className="grading-btn grading-btn-danger"
            disabled={busy}
            onClick={() => setConfirmDelete(true)}
          >
            {t('grading.detail.delete', 'Delete')}
          </button>
          <button
            className="grading-btn grading-btn-primary"
            onClick={() => onViewResults(task.task_id)}
          >
            {t('grading.detail.viewResults', 'View results →')}
          </button>
        </div>
      </div>

      {logModalOpen && (
        <div className="grading-picker-overlay" onClick={() => setLogModalOpen(false)}>
          <div className="grading-log-modal" onClick={(e) => e.stopPropagation()}>
            <div className="grading-picker-header">
              <span className="grading-picker-title">{t('grading.detail.log', 'Live log')} — {task.task_id.slice(0, 8)}</span>
              <button className="grading-picker-close" onClick={() => setLogModalOpen(false)}>×</button>
            </div>
            <pre className="grading-log-modal-box">
              {fullLogLoading
                ? t('grading.detail.logLoading', 'Loading...')
                : fullLogLines.length > 0
                  ? fullLogLines.join('\n')
                  : t('grading.detail.logEmpty', 'No log output yet.')}
            </pre>
          </div>
        </div>
      )}

      <RemoveConfirmationModal
        isOpen={confirmDelete}
        fileName={task.dir_info?.dir_name || task.task_id.slice(0, 8)}
        isRemoving={busy}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={async () => {
          setBusy(true);
          setError('');
          try {
            await gradingDeleteTask(task.task_id);
            onDeleted(task.task_id);
          } catch (e) {
            setError(e instanceof Error ? e.message : String(e));
            setConfirmDelete(false);
          } finally {
            setBusy(false);
          }
        }}
      />
    </div>
  );
};

export default TaskDetail;
