import React, { useEffect, useRef, useState } from 'react';
import ReactMarkdown, { defaultUrlTransform } from 'react-markdown';
import { useAppDispatch, useAppSelector } from '../redux/hooks';
import {
  clearReportStartRequest,
  reportDone,
  reportFailed,
  startReport,
} from '../redux/slices/uiSlice';
import {
  streamGenerateReport,
  reselectReport,
  downloadReport,
  downloadReportPdf,
  getTemplateFields,
  getReport,
  type TemplateFieldGroup,
  type TemplateFieldMeta,
} from '../services/api';
import { useTranslation } from 'react-i18next';
import '../assets/css/ReportPanel.css';

const activeReportSessions = new Set<string>();

const env = (import.meta as any).env ?? {};
const API_BASE_URL: string = (env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

const reportUrlTransform = ((url: string) => {
  if (url.startsWith('data:image/')) return url;
  // Report markdown may contain image URLs like /report/{session}/mindmap-image.
  // In dev/proxy setups those need an explicit backend base URL to avoid
  // resolving against the frontend origin and returning 404.
  if (url.startsWith('/report/')) {
    return `${API_BASE_URL}${url}`;
  }
  return defaultUrlTransform(url);
}) as any;

const isManual = (f: TemplateFieldMeta) => f.input === 'manual';
const isAlwaysOn = (f: TemplateFieldMeta) => !!f.always_on;
// Every field except always-on auto metadata has a checkbox; manual fields also
// get a text input. So "has a checkbox" == "not always-on".
const hasCheckbox = (f: TemplateFieldMeta) => !isAlwaysOn(f);

const fallbackFieldLabel = (f: TemplateFieldMeta, lang: 'en' | 'zh') =>
  f.label?.[lang] || f.code;

const fallbackGroupLabel = (g: TemplateFieldGroup, lang: 'en' | 'zh') =>
  g.group?.[lang] || g.group_key || 'group';

interface ReportPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

const ReportPanel: React.FC<ReportPanelProps> = ({ isOpen, onClose }) => {
  const dispatch = useAppDispatch();
  const { i18n, t } = useTranslation();
  const lang: 'en' | 'zh' = (i18n.language || 'en').startsWith('zh') ? 'zh' : 'en';
  const sessionId = useAppSelector(s => s.ui.sessionId);
  const reportStatus = useAppSelector(s => s.ui.reportStatus);
  const reportError = useAppSelector(s => s.ui.reportError);
  const shouldStartReport = useAppSelector(s => s.ui.shouldStartReport);
  const audioStatus = useAppSelector(s => s.ui.audioStatus);
  // The report must wait for topic/content segmentation, which the report reads
  // as a data source. For uploaded audio+video it is triggered only AFTER the
  // video reaches playback mode (see useContentSegmentation), so its completion
  // also guarantees video processing is done — no separate video gating needed.
  const contentSegmentationStatus = useAppSelector(s => s.ui.contentSegmentationStatus);
  const videoStatus = useAppSelector(s => s.ui.videoStatus);
  const processingMode = useAppSelector(s => s.ui.processingMode);
  const uploadedAudioPath = useAppSelector(s => s.ui.uploadedAudioPath);

  // Field catalog. Checkbox fields go in `selected`; manual (basic-info) fields
  // are text the teacher types in `manualValues`; always-on fields (report_time)
  // aren't shown at all. Deselected/blank fields are dropped server-side.
  const [fieldGroups, setFieldGroups] = useState<TemplateFieldGroup[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [manualValues, setManualValues] = useState<Record<string, string>>({});
  const [reportText, setReportText] = useState<string>('');
  const [reapplying, setReapplying] = useState(false);
  const [reportAvailable, setReportAvailable] = useState(true);
  const [reportUnavailableReason, setReportUnavailableReason] = useState('');
  // After a report exists, changing fields/inputs marks the view dirty; the
  // teacher clicks "Apply changes" to re-project (no AI re-run).
  const [dirty, setDirty] = useState(false);
  const disabledMsg = t('reportPanel.disabledByConfig', 'Report feature is disabled by configuration.');

  const startedRef = useRef(false);

  // Load the field catalog once on mount (NOT gated on the panel being open),
  // so UI-triggered generation always has a ready default selection.
  useEffect(() => {
    if (fieldGroups.length > 0) return;
    getTemplateFields()
      .then(data => {
        setReportAvailable(true);
        setReportUnavailableReason('');
        setFieldGroups(data.groups);
        setSelected(new Set(
          data.groups.flatMap(g => g.fields.filter(hasCheckbox).map(f => f.code)),
        ));
      })
      .catch(err => {
        const message = err?.message || t('reportPanel.loadFieldsFailed', 'Failed to load report fields.');
        console.error('Failed to load report fields:', err);
        setReportAvailable(false);
        setReportUnavailableReason(message);
        setFieldGroups([]);
        setSelected(new Set());
      });
  }, []);

  // Load an already-generated report's content when the panel opens, so the
  // markdown is shown inline (not only downloadable) without re-running anything.
  useEffect(() => {
    if (!reportAvailable || !isOpen || !sessionId || reportStatus !== 'done' || reportText) return;
    getReport(sessionId).then(setReportText).catch(() => { /* no report yet */ });
  }, [reportAvailable, isOpen, sessionId, reportStatus]);

  // Auto-start report generation if requested
  useEffect(() => {
    if (!reportAvailable || !sessionId || !shouldStartReport) return;
    if (activeReportSessions.has(sessionId) || startedRef.current) return;

    startedRef.current = true;
    activeReportSessions.add(sessionId);
    dispatch(clearReportStartRequest());

    setReportText('');
    const fields = Array.from(selected);
    const manual = { ...manualValues };
    (async () => {
      // Track whether the backend actually finished. Refusals (audio still
      // processing) / no-data come through as plain text tokens and then the
      // stream ends WITHOUT report_ready — those must not be marked as success.
      let gotReady = false;
      let lastText = '';
      try {
        for await (const event of streamGenerateReport(sessionId, fields, manual)) {
          if (event.type === 'partial_report' || event.type === 'report') {
            lastText = event.content;
            setReportText(event.content);
          } else if (event.type === 'token') {
            lastText += event.token;
            setReportText(prev => prev + event.token);
          } else if (event.type === 'report_ready') {
            gotReady = true;
            setDirty(false);
            dispatch(reportDone());
            activeReportSessions.delete(sessionId);
            startedRef.current = false;
            return;
          } else if (event.type === 'error') {
            dispatch(reportFailed(event.message));
            activeReportSessions.delete(sessionId);
            startedRef.current = false;
            return;
          }
        }
        if (gotReady) {
          dispatch(reportDone());
        } else {
          // Stream ended without completing — show the backend's message
          // (e.g. "Audio processing is in progress…") as an error, not success.
          setReportText('');
          dispatch(reportFailed(lastText.trim() || t('reportPanel.generationNotComplete', 'Report generation did not complete.')));
        }
      } catch (err: any) {
        dispatch(reportFailed(err.message));
      } finally {
        activeReportSessions.delete(sessionId);
        startedRef.current = false;
      }
    })();
  }, [reportAvailable, sessionId, shouldStartReport, selected, manualValues, dispatch]);

  // Reset when session changes
  useEffect(() => {
    if (sessionId) {
      startedRef.current = false;
      activeReportSessions.delete(sessionId);
    }
  }, [sessionId]);

  // Topic/content segmentation runs only for UPLOADED audio (both audio-only and
  // audio+video); microphone recordings never trigger it (see
  // useContentSegmentation), so its status stays 'idle' there and we must not
  // wait for it. When it does run, hold the report until it reaches a terminal
  // state ('complete'/'error') — placing report generation strictly after
  // "Content Generating…". Because segmentation for audio+video only starts once
  // the video is in playback mode, waiting for it also guarantees video is done.
  const hasUploadedAudio = Boolean(
    uploadedAudioPath && uploadedAudioPath !== 'MICROPHONE' && uploadedAudioPath.trim() !== '',
  );
  const topicTerminal =
    contentSegmentationStatus === 'complete' || contentSegmentationStatus === 'error';
  // Failsafe: a failed video never reaches playback, so segmentation is never
  // triggered — don't deadlock the report waiting for it in that case.
  const pipelineSettled = !hasUploadedAudio || topicTerminal || videoStatus === 'failed';

  const handleGenerate = () => {
    if (!reportAvailable) {
      alert(reportUnavailableReason || disabledMsg);
      return;
    }
    if (!sessionId) return;
    dispatch(startReport());
  };

  const handleRegenerate = () => {
    if (!reportAvailable) {
      alert(reportUnavailableReason || disabledMsg);
      return;
    }
    if (!sessionId) return;
    startedRef.current = false;
    activeReportSessions.delete(sessionId);
    dispatch(startReport());
  };

  // Explicit "Apply changes": re-project the cached report onto the current
  // selection + manual values. No LLM, so it's instant; only Regenerate rewrites
  // the AI analysis.
  const handleApply = async () => {
    if (!reportAvailable) {
      alert(reportUnavailableReason || disabledMsg);
      return;
    }
    if (!sessionId) return;
    setReapplying(true);
    try {
      const res = await reselectReport(sessionId, Array.from(selected), { ...manualValues });
      setReportText(res.report);
      setDirty(false);
    } catch (err: any) {
      console.error('Apply changes failed:', err);
      alert(err.message || t('reportPanel.applyChangesFailed', 'Failed to apply changes'));
    } finally {
      setReapplying(false);
    }
  };

  const handleDownload = async () => {
    if (!reportAvailable) {
      alert(reportUnavailableReason || disabledMsg);
      return;
    }
    if (!sessionId) return;
    try {
      await downloadReport(sessionId);
    } catch (err: any) {
      alert(err.message || t('reportPanel.downloadDocxFailed', 'Download failed'));
    }
  };

  const handleDownloadPdf = async () => {
    if (!reportAvailable) {
      alert(reportUnavailableReason || disabledMsg);
      return;
    }
    if (!sessionId) return;
    try {
      await downloadReportPdf(sessionId);
    } catch (err: any) {
      alert(err.message || t('reportPanel.downloadPdfFailed', 'PDF download failed'));
    }
  };

  const markDirty = () => {
    if (reportStatus === 'done') setDirty(true);
  };

  const toggleField = (code: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code); else next.add(code);
      return next;
    });
    markDirty();
  };

  const toggleGroup = (group: TemplateFieldGroup) => {
    const codes = group.fields.filter(hasCheckbox).map(f => f.code);
    if (codes.length === 0) return;
    const allOn = codes.every(c => selected.has(c));
    setSelected(prev => {
      const next = new Set(prev);
      codes.forEach(c => (allOn ? next.delete(c) : next.add(c)));
      return next;
    });
    markDirty();
  };

  const setManual = (code: string, value: string) => {
    setManualValues(prev => ({ ...prev, [code]: value }));
    markDirty();
  };

  const getGroupLabel = (group: TemplateFieldGroup) => {
    if (group.group_key) {
      return t(`reportFields.groups.${group.group_key}`, fallbackGroupLabel(group, lang));
    }
    return fallbackGroupLabel(group, lang);
  };

  const getFieldLabel = (field: TemplateFieldMeta) => {
    if (field.label_key) {
      return t(`reportFields.fields.${field.label_key}`, fallbackFieldLabel(field, lang));
    }
    return fallbackFieldLabel(field, lang);
  };

  // Enabled when either:
  // 1) the audio pipeline finished (classic path), or
  // 2) this is a video-only run and video reached playback/terminal state.
  // In both cases, keep the pipeline-settled guard to avoid half-written inputs.
  const videoOnlyReady =
    processingMode === 'video-only' &&
    (videoStatus === 'playback' || videoStatus === 'completed' || videoStatus === 'failed');
  const canGenerate = reportAvailable && Boolean(sessionId) && pipelineSettled && (audioStatus === 'complete' || videoOnlyReady);
  const generating = reportStatus === 'generating';
  const hasContent = selected.size > 0;

  if (!isOpen) return null;

  return (
    <>
      {/* Overlay */}
      <div
        className={`report-panel-overlay ${isOpen ? 'open' : ''}`}
        onClick={onClose}
      />

      {/* Slide-in Panel */}
      <div className={`report-panel ${isOpen ? 'open' : ''}`}>
        {/* Header */}
        <div className="report-panel-header">
          <div>
            <div className="report-panel-title">{t('reportPanel.classReport', 'Class Report')}</div>
            <div className="report-panel-subtitle">
              {sessionId || t('reportPanel.noSessionActive', 'No session active')}
            </div>
          </div>
          <button className="report-panel-close" onClick={onClose}>
            &times;
          </button>
        </div>

        {/* Body */}
        <div className="report-panel-body">
          {/* Field Selection */}
          <div className="field-block">
            <div className="field-block-label">{t('reportPanel.reportFields', 'Report Fields')}</div>
            <div className="field-block-hint">
              {t('reportPanel.fieldHint', 'Tick the fields to include; deselected fields are omitted. For basic info, type a value or leave it blank to fill in later on the document.')}
            </div>

            {!reportAvailable && (
              <div className="report-state-error" style={{ marginBottom: 10 }}>
                <div className="report-error-text">
                  {reportUnavailableReason || disabledMsg}
                </div>
              </div>
            )}

            <div className="field-groups">
              {fieldGroups.map(group => {
                const codes = group.fields.filter(hasCheckbox).map(f => f.code);
                const allOn = codes.length > 0 && codes.every(c => selected.has(c));
                const groupTitle = getGroupLabel(group);
                return (
                  <div className="field-group" key={group.group_key || groupTitle}>
                    {codes.length > 0 ? (
                      <label className="field-group-head">
                        <input
                          type="checkbox"
                          checked={allOn}
                          onChange={() => toggleGroup(group)}
                          disabled={generating || !reportAvailable}
                        />
                        <span className="field-group-title">{groupTitle}</span>
                      </label>
                    ) : (
                      <div className="field-group-head">
                        <span className="field-group-title">{groupTitle}</span>
                      </div>
                    )}

                    <div className="field-list">
                      {group.fields.filter(hasCheckbox).map(f => (
                        isManual(f) ? (
                          // Manual field: checkbox controls inclusion, text input
                          // supplies the value (blank kept as an empty line).
                          <div className="field-manual-row" key={f.code}>
                            <label className="field-item field-manual-check">
                              <input
                                type="checkbox"
                                checked={selected.has(f.code)}
                                onChange={() => toggleField(f.code)}
                                disabled={generating || !reportAvailable}
                              />
                              <span className="field-item-label">{getFieldLabel(f)}</span>
                            </label>
                            <input
                              className="field-manual-input"
                              type="text"
                              value={manualValues[f.code] ?? ''}
                              placeholder={getFieldLabel(f)}
                              onChange={e => setManual(f.code, e.target.value)}
                              disabled={generating || !reportAvailable || !selected.has(f.code)}
                            />
                          </div>
                        ) : (
                          <label className="field-item" key={f.code}>
                            <input
                              type="checkbox"
                              checked={selected.has(f.code)}
                              onChange={() => toggleField(f.code)}
                              disabled={generating || !reportAvailable}
                            />
                            <span className="field-item-label">{getFieldLabel(f)}</span>
                          </label>
                        )
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Generate / Apply Buttons */}
            <div className="field-actions">
              {reportStatus === 'done' && dirty && (
                <button
                  className="template-action-btn apply-action"
                  onClick={handleApply}
                  disabled={reapplying || !hasContent || !reportAvailable}
                  title={t('reportPanel.applyTitle', 'Update the report with your field changes - no AI re-run')}
                >
                  {reapplying
                    ? t('reportPanel.updatingReport', 'Updating report...')
                    : t('reportPanel.applyChanges', '🔄 Apply field changes to report')}
                </button>
              )}
              <button
                className="template-action-btn primary-action"
                onClick={reportStatus === 'done' ? handleRegenerate : handleGenerate}
                disabled={!canGenerate || generating || !hasContent || !reportAvailable}
                title={
                  !reportAvailable
                    ? (reportUnavailableReason || disabledMsg)
                    : canGenerate
                    ? ''
                    : (audioStatus === 'complete' || videoOnlyReady) && !pipelineSettled
                      ? t('reportPanel.contentGeneratingWait', 'Content is still being generated. Please wait until it finishes.')
                      : processingMode === 'video-only'
                        ? t('reportPanel.waitVideoPlayback', 'Wait for video processing to enter playback mode first.')
                        : t('reportPanel.completeSessionFirst', 'Complete the session first')
                }
              >
                ⚡ {reportStatus === 'done'
                  ? t('reportPanel.regenerateReport', 'Regenerate Report')
                  : t('reportPanel.generateReport', 'Generate Report')}
              </button>
            </div>

            {/* Hint */}
            <div className="field-note">
              {reportStatus === 'done'
                ? (dirty
                    ? t('reportPanel.doneHintDirty', 'You changed the fields. Click “Apply changes” to update the report (no AI re-run), or Regenerate to rewrite the AI analysis.')
                    : t('reportPanel.doneHintClean', 'Change any field, then an “Apply changes” button appears to update the report instantly. Regenerate rewrites the AI analysis.'))
                : (!reportAvailable
                  ? (reportUnavailableReason || disabledMsg)
                  : !canGenerate
                  ? ((audioStatus === 'complete' || videoOnlyReady) && !pipelineSettled
                        ? t('reportPanel.contentGeneratingHint', 'Content is still being generated. Generate is enabled once it finishes.')
                    : processingMode === 'video-only'
                      ? t('reportPanel.videoOnlyHint', 'For video-only sessions, Generate is enabled once video processing reaches playback mode.')
                      : t('reportPanel.noSessionHint', 'No active session yet. Once a class is recorded and processed, Generate is enabled. After generating, tweak fields and click Apply.'))
                    : t('reportPanel.clickGenerateHint', 'Click Generate. Afterwards you can tweak fields and click Apply to update instantly.'))}
            </div>
          </div>

          {/* Report Section */}
          <div className="report-section-label">{t('reportPanel.generatedReport', 'Generated Report')}</div>

          {/* Empty State */}
          {reportStatus === 'idle' && (
            <div className="report-state-empty">
              <div className="report-state-empty-icon">📋</div>
              <span>{t('reportPanel.noReportYet', 'No report yet.')}</span>
              <span style={{ fontSize: '12px' }}>
                {t('reportPanel.autoGenerateOnEnd', 'It can be generated after content segmentation completes, or generated manually here.')}
              </span>
            </div>
          )}

          {/* Generating State — show the raw-filled skeleton as it streams in */}
          {reportStatus === 'generating' && (
            <div className="report-state-generating">
              <div className="gen-status">
                <div className="gen-spinner"></div>
                <div className="gen-text">
                  {reportText
                    ? t('reportPanel.writingAnalysis', 'Writing analysis...')
                    : t('reportPanel.generatingFromTemplate', 'Generating report from template...')}
                </div>
              </div>
              {reportText && (
                <div className="report-markdown">
                  <ReactMarkdown urlTransform={reportUrlTransform}>{reportText}</ReactMarkdown>
                </div>
              )}
            </div>
          )}

          {/* Error State */}
          {reportStatus === 'error' && (
            <div className="report-state-error">
              <div className="report-error-icon">⚠️</div>
              <div className="report-error-text">
                {reportError || t('reportPanel.reportGenerationFailed', 'Report generation failed')}
              </div>
            </div>
          )}

          {/* Success State */}
          {reportStatus === 'done' && sessionId && (
            <div className="report-state-done">
              <div className="report-done-header">
                <span className="report-done-icon">✓</span>
                <span className="report-done-text">
                  {reapplying
                    ? t('reportPanel.updatingFields', 'Updating fields...')
                    : t('reportPanel.reportReady', 'Report ready')}
                </span>
              </div>
              {reportText && (
                <div className="report-markdown">
                  <ReactMarkdown urlTransform={reportUrlTransform}>{reportText}</ReactMarkdown>
                </div>
              )}
              <div className="report-done-actions">
                <button className="report-download-btn" onClick={handleDownload}>
                  {t('reportPanel.downloadDocx', '📥 Download .docx')}
                </button>
                <button className="report-download-btn" onClick={handleDownloadPdf}>
                  {t('reportPanel.downloadPdf', '📄 Download .pdf')}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
};

export default ReportPanel;
