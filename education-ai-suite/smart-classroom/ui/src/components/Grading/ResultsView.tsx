import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { toErrorMessage, formatDateTime, compareByNumericThenString } from './gradingUtils';
import GradingModal from './GradingModal';
import { useTranslation } from 'react-i18next';
import { gradingGetTaskSummary, gradingGetStudentResult } from '../../services/api';
import type { GradingSummary, GradingStudentResult, GradingStudentResultDetail, GradingQuestionNode } from '../../services/api';

interface ResultsViewProps {
  taskId: string | null;
  onBack: () => void;
}

const dash = '—';

const numOrDash = (v: number | null | undefined): string =>
  v === null || v === undefined ? dash : String(v);

const toRootQuestionMap = (student: GradingStudentResult): Record<string, { score: number | null; max_score: number | null }> => {
  const roots = student.questions_hierarchy || [];
  const out: Record<string, { score: number | null; max_score: number | null }> = {};
  for (const node of roots) {
    const qn = node.question_no;
    if (qn === null || qn === undefined) continue;
    const key = String(qn);
    out[key] = {
      score: node.meta?.grading_score ?? null,
      max_score: node.meta?.max_score ?? null,
    };
  }
  return out;
};

const ResultsView: React.FC<ResultsViewProps> = ({ taskId, onBack }) => {
  const { t } = useTranslation();
  const [summary, setSummary] = useState<GradingSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [detailOpen, setDetailOpen] = useState<boolean>(false);
  const [detailData, setDetailData] = useState<GradingStudentResultDetail | null>(null);
  const [detailError, setDetailError] = useState<string>('');
  const [detailTitle, setDetailTitle] = useState<string>('');
  const [detailLoading, setDetailLoading] = useState<boolean>(false);

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
    base.sort((a, b) => compareByNumericThenString(a.key, b.key));
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

  // Union of every first-level question id across all students, plus each question's max.
  const { questionIds, questionMax } = useMemo(() => {
    const maxMap: Record<string, number | null | undefined> = {};
    const idSet = new Set<string>();
    for (const { student } of rows) {
      const questions = toRootQuestionMap(student);
      for (const [qid, q] of Object.entries(questions)) {
        idSet.add(qid);
        if (!(qid in maxMap)) maxMap[qid] = q.max_score;
      }
    }
    return { questionIds: [...idSet].sort(compareByNumericThenString), questionMax: maxMap };
  }, [rows]);

  const metadata = (summary?.metadata || {}) as Record<string, unknown>;
  const paperTitle = (metadata.paper_title as string) || '';
  const subject = (metadata.subject as string) || '';
  const papersDir = (metadata.papers_dir as string) || '';

  const studentName = (s: GradingStudentResult): string =>
    s.student_name || s.student_id || dash;

  const renderDetail = (detail: GradingStudentResultDetail): React.ReactNode => {
    const s = detail.summary || {};
    const meta = detail.student_meta || {};
    const name = (meta.student_name as string) || (detail.input?.student_id as string) || '';
    const rows: Array<{
      label: string;
      answer: string;
      score: string;
      reason: string;
      scoreClass: string;
    }> = [];

    const walk = (node: GradingQuestionNode, parentNo?: number | null) => {
      const qno = node.question_no ?? parentNo;
      const children = node.questions;
      if (children && children.length > 0) {
        for (const child of children) walk(child, qno);
        return;
      }
      const partPath = node.meta?.part_path && node.meta.part_path.length > 0
        ? `(${node.meta.part_path.join('.')})`
        : '';
      const label = `Q${qno ?? ''}${partPath}`;
      const answer = (node.student_answer ?? '').toString().trim() || dash;
      const rawScore = node.meta?.grading_score;
      const rawMax = node.meta?.max_score;
      const score = `${numOrDash(rawScore)}/${numOrDash(rawMax)}`;
      const reason = (node.reason ?? '').toString().trim() || dash;
      let scoreClass = '';
      if (typeof rawScore === 'number' && typeof rawMax === 'number') {
        if (rawScore === 0) {
          scoreClass = 'grading-detail-score-zero';
        } else if (rawScore < rawMax) {
          scoreClass = 'grading-detail-score-partial';
        }
      }
      rows.push({ label, answer, score, reason, scoreClass });
    };

    for (const root of detail.questions_hierarchy || []) walk(root);

    return (
      <div className="grading-detail-viewer">
        <div className="grading-detail-summary-line">{t('grading.results.name', 'Student')}: {name || dash}</div>
        <div className="grading-detail-summary-line">{t('grading.results.total', 'Total')}: {numOrDash(s.total_score)} / {numOrDash(s.total_max)}</div>
        <div className="grading-detail-sep">-----</div>
        <div className="grading-detail-list">
          {rows.map((row, idx) => (
            <div className="grading-detail-question" key={`${row.label}-${idx}`}>
              <div className="grading-detail-q-title">{row.label}</div>
              <div className="grading-detail-q-line"><strong>studentanswer:</strong> {row.answer}</div>
              <div className="grading-detail-q-line">
                <strong>score:</strong>{' '}
                <span className={row.scoreClass}>{row.score}</span>
              </div>
              <div className="grading-detail-q-line"><strong>Reason:</strong> {row.reason}</div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const openDetail = async (slot: string, student: GradingStudentResult) => {
    if (!taskId) return;
    setDetailTitle(studentName(student));
    setDetailData(null);
    setDetailError('');
    setDetailOpen(true);
    setDetailLoading(true);
    try {
      const detail = await gradingGetStudentResult(taskId, slot);
      setDetailData(detail);
    } catch (e) {
      setDetailError(toErrorMessage(e));
    } finally {
      setDetailLoading(false);
    }
  };

  const exportCsv = () => {
    const header = [
      '#',
      t('grading.results.studentId', 'Student ID'),
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
        `"${(student.student_id || '').replace(/"/g, '""')}"`,
        `"${studentName(student).replace(/"/g, '""')}"`,
        numOrDash(student.total_score),
        numOrDash(student.objective_score),
        numOrDash(student.subjective_score),
        ...questionIds.map((qid) => numOrDash(toRootQuestionMap(student)[qid]?.score)),
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
            <span className="grading-results-meta-value">{formatDateTime(summary.updated_at, true)}</span>
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
                <th className="sticky-col sticky-col-2">{t('grading.results.studentId', 'Student ID')}</th>
                <th className="sticky-col sticky-col-3">{t('grading.results.name', 'Student')}</th>
                <th className="grading-results-detail-col"></th>
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
                  <td className="sticky-col sticky-col-2">{student.student_id || dash}</td>
                  <td className="sticky-col sticky-col-3">{studentName(student)}</td>
                  <td className="grading-results-detail-col">
                    <button
                      className="grading-results-detail-btn"
                      onClick={() => openDetail(key, student)}
                      title={t('grading.results.viewDetail', 'View grading detail')}
                    >
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <path d="M14 2v6h6" />
                        <line x1="8" y1="13" x2="16" y2="13" />
                        <line x1="8" y1="17" x2="16" y2="17" />
                        <line x1="8" y1="9" x2="10" y2="9" />
                      </svg>
                    </button>
                  </td>
                  <td className="grading-results-total">
                    {numOrDash(student.total_score)}
                    <span className="grading-results-max">/{numOrDash(student.total_max)}</span>
                  </td>
                  <td>{numOrDash(student.objective_score)}</td>
                  <td>{numOrDash(student.subjective_score)}</td>
                  {questionIds.map((qid) => {
                    const q = toRootQuestionMap(student)[qid];
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

      {detailOpen && (
        <GradingModal
          title={`${t('grading.results.detailTitle', 'Grading Detail')} — ${detailTitle}`}
          onClose={() => setDetailOpen(false)}
          className="grading-log-modal"
        >
          <div className="grading-log-modal-box">
            {detailLoading
              ? t('grading.results.detailLoading', 'Loading…')
              : detailError
                ? detailError
                : detailData
                  ? renderDetail(detailData)
                  : dash}
          </div>
        </GradingModal>
      )}
    </div>
  );
};

export default ResultsView;
