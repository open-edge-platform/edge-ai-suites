import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  gradingPauseTask,
  gradingResumeTask,
  gradingCancelTask,
  gradingGetTaskLog,
} from '../../services/api';
import type { GradingTask } from '../../services/api';

interface TaskDetailProps {
  task: GradingTask;
  onControlled: (task: GradingTask) => void;
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

const TaskDetail: React.FC<TaskDetailProps> = ({ task, onControlled, onViewResults }) => {
  const { t } = useTranslation();
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [logLines, setLogLines] = useState<string[]>([]);
  const [logError, setLogError] = useState<string>('');

  const status = task.status;
  const isTerminal = status === 'COMPLETED' || status === 'FAILED' || status === 'CANCELLED';
  const isTransient = status === 'PAUSING' || status === 'CANCELLING';

  const canPause = status === 'RUNNING';
  const canResume = status === 'PAUSED';
  const canCancel = !isTerminal && !isTransient;

  const info = task.dir_info || null;
  const dash = '—';

  const logBoxRef = useRef<HTMLPreElement | null>(null);
  const logTimeoutRef = useRef<number | null>(null);
  const logCancelledRef = useRef<boolean>(false);

  useEffect(() => {
    logCancelledRef.current = false;
    const fetchLog = async () => {
      try {
        const res = await gradingGetTaskLog(task.task_id, LOG_TAIL);
        if (logCancelledRef.current) return;
        setLogLines(res.lines || []);
        setLogError('');
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
          {t('grading.detail.dir', 'Directory')}: {info?.papers_dir || dash}
        </span>
        <span>
          {t('grading.detail.rubric', 'Rubric')}: {info?.rubric_name || dash}
        </span>
        <span>
          {t('grading.detail.elapsed', 'Elapsed')}: {elapsed}
        </span>
      </div>

      {task.error_message && <div className="grading-error">{task.error_message}</div>}
      {error && <div className="grading-error">{error}</div>}

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
          disabled={!canCancel || busy}
          onClick={() => run(() => gradingCancelTask(task.task_id))}
        >
          {t('grading.detail.cancel', 'Cancel')}
        </button>
        <button
          className="grading-btn grading-btn-primary grading-detail-view"
          onClick={() => onViewResults(task.task_id)}
        >
          {t('grading.detail.viewResults', 'View results →')}
        </button>
      </div>

      <div className="grading-log">
        <div className="grading-log-title">{t('grading.detail.log', 'Live log')}</div>
        {logError && <div className="grading-error">{logError}</div>}
        <pre className="grading-log-box" ref={logBoxRef}>
          {logLines.length > 0
            ? logLines.join('\n')
            : t('grading.detail.logEmpty', 'No log output yet.')}
        </pre>
      </div>
    </div>
  );
};

export default TaskDetail;
