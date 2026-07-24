import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { toErrorMessage } from './gradingUtils';

const formatDateTime = (iso: string): string => {
  try {
    const d = new Date(iso);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  } catch { return iso; }
};
import { useTranslation } from 'react-i18next';
import { gradingGetTaskSummary } from '../../services/api';
import type { GradingSummary, GradingStudentResult } from '../../services/api';

interface ResultsViewProps {
  taskId: string | null;
  onBack: () => void;
}

const dash = '—';

const numOrDash = (v: number | null | undefined): string =>
  v === null || v === undefined ? dash : String(v);

// Order question ids numerically when possible, falling back to string order.
const sortQuestionIds = (ids: string[]): string[] =>
  [...ids].sort((a, b) => {
    const na = Number(a);
    const nb = Number(b);
    const aNum = !Number.isNaN(na);
    const bNum = !Number.isNaN(nb);
    if (aNum && bNum) return na - nb;
    if (aNum) return -1;
    if (bNum) return 1;
    return a.localeCompare(b);
  });

const ResultsView: React.FC<ResultsViewProps> = ({ taskId, onBack }) => {
  const { t } = useTranslation();
  const [summary, setSummary] = useState<GradingSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');

  const load = useCallback(async () => {
    if (!taskId) return;
    setLoading(true);
    setError('');
    try {
      setSummary(await gradingGetTaskSummary(taskId));
    } catch (e) {
      setError(toErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [taskId]);

  useEffect(() => {
    load();
  }, [load]);

  // Sort state for the score columns; null = natural order (by student key).
  type SortField = 'total_score' | 'objective_score' | 'subjective_score';
  const [sortField, setSortField] = useState<SortField | null>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  const toggleSort = (field: SortField) => {
    if (sortField !== field) {
      setSortField(field);
      setSortDir('desc');
    } else if (sortDir === 'desc') {
      setSortDir('asc');
    } else {
      // asc -> back to natural order
      setSortField(null);
      setSortDir('desc');
    }
  };

  const sortArrow = (field: SortField): string =>
    sortField === field ? (sortDir === 'asc' ? ' ▲' : ' ▼') : '';

  // Rows sorted by the numeric student key by default, or by a score column when
  // a sort is active. Null scores sort to the bottom regardless of direction.
  const rows = useMemo<Array<{ key: string; student: GradingStudentResult }>>(() => {
    if (!summary?.students) return [];
    const base = Object.entries(summary.students).map(([key, student]) => ({ key, student }));
    base.sort((a, b) => {
      const na = Number(a.key);
      const nb = Number(b.key);
      if (!Number.isNaN(na) && !Number.isNaN(nb)) return na - nb;
      return a.key.localeCompare(b.key);
    });
    if (!sortField) return base;
    const dir = sortDir === 'asc' ? 1 : -1;
    return base.sort((a, b) => {
      const va = a.student[sortField];
      const vb = b.student[sortField];
      const aNull = va === null || va === undefined;
      const bNull = vb === null || vb === undefined;
      if (aNull && bNull) return 0;
      if (aNull) return 1;
      if (bNull) return -1;
      return (Number(va) - Number(vb)) * dir;
    });
  }, [summary, sortField, sortDir]);

  // Union of every question id across all students, plus each question's max.
  const { questionIds, questionMax } = useMemo(() => {
    const maxMap: Record<string, number | null | undefined> = {};
    const idSet = new Set<string>();
    for (const { student } of rows) {
      const questions = student.questions || {};
      for (const [qid, q] of Object.entries(questions)) {
        idSet.add(qid);
        if (!(qid in maxMap)) maxMap[qid] = q.max_score;
      }
    }
    return { questionIds: sortQuestionIds([...idSet]), questionMax: maxMap };
  }, [rows]);

  const metadata = (summary?.metadata || {}) as Record<string, unknown>;
  const paperTitle = (metadata.paper_title as string) || '';
  const subject = (metadata.subject as string) || '';
  const papersDir = (metadata.papers_dir as string) || '';

  const studentName = (s: GradingStudentResult): string =>
    s.student_name || s.student_id || dash;

  const exportCsv = () => {
    const header = [
      '#',
      t('grading.results.name', 'Student'),
      t('grading.results.total', 'Total'),
      t('grading.results.objective', 'Objective'),
      t('grading.results.subjective', 'Subjective'),
      ...questionIds,
    ];
    const lines = [header.join(',')];
    rows.forEach(({ student }, idx) => {
      const cells: string[] = [
        String(idx + 1),
        `"${studentName(student).replace(/"/g, '""')}"`,
        numOrDash(student.total_score),
        numOrDash(student.objective_score),
        numOrDash(student.subjective_score),
        ...questionIds.map((qid) => numOrDash(student.questions?.[qid]?.score)),
      ];
      lines.push(cells.join(','));
    });
    const blob = new Blob(['﻿' + lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `grading_${taskId || 'result'}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!taskId) {
    return (
      <div className="grading-placeholder">
        <p>{t('grading.results.noTask', 'Open a task from the list to view its results.')}</p>
      </div>
    );
  }

  return (
    <div className="grading-results">
      <div className="grading-results-header">
        <button className="grading-results-back" onClick={onBack} title={t('grading.results.back', 'Back')}>←</button>
        <div className="grading-results-title">
          {paperTitle || t('grading.resultsTitle', 'Results')}
          {subject && <span className="grading-results-subject"> · {subject}</span>}
        </div>
      </div>

      <div className="grading-results-meta-panel">
        <div className="grading-results-meta-item">
          <span className="grading-results-meta-label">{t('grading.results.taskId', 'Task')}</span>
          <span className="grading-results-meta-value">{taskId}</span>
        </div>
        <div className="grading-results-meta-item">
          <span className="grading-results-meta-label">{t('grading.results.count', 'Students')}</span>
          <span className="grading-results-meta-value">{summary?.student_count ?? rows.length}</span>
        </div>
        {papersDir && (
          <div className="grading-results-meta-item">
            <span className="grading-results-meta-label">{t('grading.results.papersDir', 'Directory')}</span>
            <span className="grading-results-meta-value grading-results-meta-path">{papersDir}</span>
          </div>
        )}
        {summary?.updated_at && (
          <div className="grading-results-meta-item">
            <span className="grading-results-meta-label">{t('grading.results.updated', 'Updated')}</span>
            <span className="grading-results-meta-value">{formatDateTime(summary.updated_at)}</span>
          </div>
        )}
      </div>

      {error && <div className="grading-error">{error}</div>}

      {rows.length === 0 && !error ? (
        <div className="grading-empty">{t('grading.results.empty', 'No graded papers yet.')}</div>
      ) : (
        <>
          <div className="grading-results-table-actions">
            <span className="grading-results-table-title">{t('grading.results.tableTitle', 'Grading Results')}</span>
            <button className="grading-btn grading-btn-secondary grading-export-btn" onClick={load} disabled={loading} title={t('grading.results.refresh', 'Refresh')}>
              <span className={loading ? 'grading-spinning' : ''}>↻</span>
            </button>
            <button className="grading-btn grading-btn-secondary grading-export-btn" onClick={exportCsv} disabled={rows.length === 0} title={t('grading.results.export', 'Export CSV')}>
              ⬇ CSV
            </button>
          </div>
        <div className="grading-results-tablewrap">
          <table className="grading-results-table">
            <thead>
              <tr>
                <th className="sticky-col">#</th>
                <th className="sticky-col sticky-col-2">{t('grading.results.name', 'Student')}</th>
                <th className="grading-results-sortable" onClick={() => toggleSort('total_score')}>
                  {t('grading.results.total', 'Total')}{sortArrow('total_score')}
                </th>
                <th className="grading-results-sortable" onClick={() => toggleSort('objective_score')}>
                  {t('grading.results.objective', 'Objective')}{sortArrow('objective_score')}
                </th>
                <th className="grading-results-sortable" onClick={() => toggleSort('subjective_score')}>
                  {t('grading.results.subjective', 'Subjective')}{sortArrow('subjective_score')}
                </th>
                {questionIds.map((qid) => (
                  <th key={qid} title={`${t('grading.results.maxScore', 'Max')}: ${numOrDash(questionMax[qid])}`}>
                    {qid}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(({ key, student }, idx) => (
                <tr key={key}>
                  <td className="sticky-col">{idx + 1}</td>
                  <td className="sticky-col sticky-col-2">{studentName(student)}</td>
                  <td className="grading-results-total">
                    {numOrDash(student.total_score)}
                    <span className="grading-results-max">/{numOrDash(student.total_max)}</span>
                  </td>
                  <td>{numOrDash(student.objective_score)}</td>
                  <td>{numOrDash(student.subjective_score)}</td>
                  {questionIds.map((qid) => {
                    const q = student.questions?.[qid];
                    return (
                      <td key={qid} className="grading-results-q">
                        {q ? numOrDash(q.score) : dash}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        </>
      )}
    </div>
  );
};

export default ResultsView;
