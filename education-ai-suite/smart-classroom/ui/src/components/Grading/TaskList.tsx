import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { gradingListTasks } from '../../services/api';
import type { GradingTask } from '../../services/api';
import TaskDetail from './TaskDetail';

interface TaskListProps {
  refreshSignal: number;
  onViewResults: (taskId: string) => void;
}

const POLL_MS = 4000;

const STATUS_LABELS: Record<string, string> = {
  PENDING: 'grading.status.pending',
  RUNNING: 'grading.status.running',
  PAUSING: 'grading.status.pausing',
  PAUSED: 'grading.status.paused',
  CANCELLING: 'grading.status.cancelling',
  CANCELLED: 'grading.status.cancelled',
  COMPLETED: 'grading.status.completed',
  FAILED: 'grading.status.failed',
};

const shortId = (id: string): string => (id ? id.slice(0, 8) : '');

const formatTime = (iso: string): string => {
  try {
    const d = new Date(iso);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  } catch {
    return iso;
  }
};

const TaskList: React.FC<TaskListProps> = ({ refreshSignal, onViewResults }) => {
  const { t } = useTranslation();

  const [tasks, setTasks] = useState<GradingTask[]>([]);
  const [statusCounts, setStatusCounts] = useState<Record<string, number>>({});
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // null = show all; otherwise filter by this status (server-side).
  const [filter, setFilter] = useState<string | null>(null);

  const fetchOnce = useCallback(async () => {
    const res = await gradingListTasks(filter ?? undefined);
    setTasks(res.tasks || []);
    setStatusCounts(res.status_counts || {});
    setTotal(res.total || 0);
    setError('');
  }, [filter]);

  useEffect(() => {
    let cancelled = false;
    let timeout: number | null = null;
    const poll = async () => {
      if (cancelled) return;
      try {
        await fetchOnce();
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
      if (!cancelled) {
        timeout = window.setTimeout(poll, POLL_MS);
      }
    };
    poll();
    return () => {
      cancelled = true;
      if (timeout) clearTimeout(timeout);
    };
  }, [fetchOnce, refreshSignal]);

  const handleRefresh = async () => {
    setLoading(true);
    try {
      await fetchOnce();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const patchTask = (updated: GradingTask) => {
    setTasks((prev) =>
      prev.map((tk) => (tk.task_id === updated.task_id ? { ...tk, ...updated } : tk))
    );
  };

  const removeTask = (taskId: string) => {
    setTasks((prev) => prev.filter((tk) => tk.task_id !== taskId));
    if (expandedId === taskId) setExpandedId(null);
  };

  const runningCount = statusCounts.RUNNING || 0;
  const completedCount = statusCounts.COMPLETED || 0;
  const pausedCount = statusCounts.PAUSED || 0;
  const allCount = Object.values(statusCounts).reduce((sum, n) => sum + n, 0) || total;

  const filterChip = (status: string | null, label: string, count: number) => (
    <button
      className={`grading-filter-chip${filter === status ? ' active' : ''}`}
      onClick={() => setFilter(status)}
    >
      {label}: {count}
    </button>
  );

  return (
    <div className="grading-tasklist">
      <div className="grading-tasklist-header">
        <h3 className="grading-section-title">{t('grading.list.title', 'Tasks')}</h3>
        <button
          className="grading-btn grading-btn-secondary grading-refresh"
          onClick={handleRefresh}
          disabled={loading}
        >
          {loading ? t('grading.list.refreshing', 'Refreshing...') : t('grading.list.refresh', 'Refresh')}
        </button>
      </div>

      <div className="grading-count-line">
        {filterChip(null, t('grading.list.total', 'Total'), allCount)}
        {filterChip('RUNNING', t('grading.list.running', 'Running'), runningCount)}
        {filterChip('COMPLETED', t('grading.list.completed', 'Completed'), completedCount)}
        {filterChip('PAUSED', t('grading.list.paused', 'Paused'), pausedCount)}
      </div>

      {error && <div className="grading-error">{error}</div>}

      {tasks.length === 0 && !error && (
        <div className="grading-empty">
          {filter
            ? t('grading.list.emptyFiltered', 'No tasks in this status.')
            : t('grading.list.empty', 'No tasks yet.')}
        </div>
      )}

      <div className="grading-rows">
        {tasks.map((task) => {
          const expanded = expandedId === task.task_id;
          const statusKey = STATUS_LABELS[task.status] || task.status;
          return (
            <div key={task.task_id} className="grading-row-wrap">
              <div
                className="grading-row"
                onClick={() => setExpandedId(expanded ? null : task.task_id)}
              >
                <span className={`grading-dot status-${task.status}`} />
                <span className="grading-row-time">{task.created_at ? formatTime(task.created_at) : '—'}</span>
                <span className="grading-row-status">{t(statusKey, task.status)}</span>
                <span className="grading-row-id" title={task.dir_info?.papers_dir || task.task_id}>
                  {task.dir_info?.dir_name || shortId(task.task_id)}
                  <span className="grading-row-taskid"> #{shortId(task.task_id)}</span>
                </span>
                <span className="grading-row-counts">
                  {task.dir_info
                    ? `${task.dir_info.completed}/${task.dir_info.total}`
                    : t('grading.list.progressUnknown', '—/—')}
                </span>
                <span className="grading-row-arrow">{expanded ? '▾' : '▸'}</span>
              </div>
              {expanded && (
                <TaskDetail
                  task={task}
                  onControlled={patchTask}
                  onDeleted={removeTask}
                  onViewResults={onViewResults}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default TaskList;
