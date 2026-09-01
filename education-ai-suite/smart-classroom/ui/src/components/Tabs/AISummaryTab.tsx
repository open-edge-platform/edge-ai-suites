import React, { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { useTranslation } from "react-i18next";
import "../../assets/css/AISummaryTab.css";
import { useAppDispatch, useAppSelector } from "../../redux/hooks";
import { firstSummaryToken, summaryDone, clearSummaryStartRequest, summaryStreamComplete } from "../../redux/slices/uiSlice";
import { appendSummary, finishSummary, startSummary } from "../../redux/slices/summarySlice";
import { streamSummary } from "../../services/api";
import { useFeatureConfig } from "../../hooks/useFeatureConfig";

const activeSummarySessions = new Set<string>();

const AISummaryTab: React.FC = () => {
  const dispatch = useAppDispatch();
  const { t } = useTranslation();
  const summaryEnabled = useAppSelector(s => s.ui.summaryEnabled);
  const isLoading = useAppSelector(s => s.ui.summaryLoading);
  const { streamingText, finalText } = useAppSelector(s => s.summary);
  const sessionId = useAppSelector(s => s.ui.sessionId);
  const shouldStartSummary = useAppSelector(s => s.ui.shouldStartSummary);
  const [boardOcrPartial, setBoardOcrPartial] = useState(false);
  
  // Check if mindmap feature is enabled in backend
  const { guard, loaded: featuresLoaded } = useFeatureConfig();
  const hasMindmapFeature = featuresLoaded && guard.hasFeature('mindmap');

  const startedRef = useRef(false);
  const sessionRef = useRef<string | null>(null);
  // Only set for long sessions, where the summary is built segment by segment.
  const [progress, setProgress] = useState<
    { stage: string; chunk: number; chunks: number } | null
  >(null);

  useEffect(() => {
    if (sessionRef.current && sessionRef.current !== sessionId) {
      activeSummarySessions.delete(sessionRef.current);
      startedRef.current = false;
    }
    sessionRef.current = sessionId ?? null;
  }, [sessionId]);

  useEffect(() => {
    if (!summaryEnabled || !sessionId || !shouldStartSummary) return;
    if (activeSummarySessions.has(sessionId) || startedRef.current) return;

    startedRef.current = true;
    activeSummarySessions.add(sessionId);
    dispatch(clearSummaryStartRequest());
    dispatch(startSummary());
    setBoardOcrPartial(false);

    (async () => {
      try {
        let sentFirst = false;
        for await (const ev of streamSummary(sessionId)) {
          if (ev.type === "summary_token") {
            if (!sentFirst) {
              dispatch(firstSummaryToken());
              sentFirst = true;
            }
            setProgress(null);
            dispatch(appendSummary(ev.token));
          } else if (ev.type === "board_ocr_partial") {
            setBoardOcrPartial(true);
          } else if (ev.type === "summary_progress") {
            setProgress({ stage: ev.stage, chunk: ev.chunk, chunks: ev.chunks });
          } else if (ev.type === "error") {
            window.dispatchEvent(new CustomEvent('global-error', { detail: ev.message || 'Summary error' }));
            setProgress(null);
            dispatch(finishSummary());
            dispatch(summaryStreamComplete());
            dispatch(summaryDone({ enableMindmap: hasMindmapFeature }));
            break;
          } else if (ev.type === "done") {
            setProgress(null);
            dispatch(finishSummary());
            dispatch(summaryStreamComplete());
            dispatch(summaryDone({ enableMindmap: hasMindmapFeature }));
            break;
          }
        }
      } catch (e: any) {
        if (e?.name !== 'AbortError') console.error('[AISummaryTab] stream error', e);
        dispatch(finishSummary());
        dispatch(summaryStreamComplete());
        dispatch(summaryDone({ enableMindmap: hasMindmapFeature }));
      } finally {
        console.log('[AISummaryTab] stream finished', sessionId);
      }
    })();
  }, [summaryEnabled, shouldStartSummary, sessionId, dispatch, hasMindmapFeature]);

  const typed = finalText ?? streamingText;

  // Each stage counts its own units, so they cannot share one label: a fold
  // restarts the numbering, and reduce has nothing to count at all.
  const progressLabel = (p: { stage: string; chunk: number; chunks: number }) => {
    if (p.stage === "reduce") {
      return t("tabs.summaryProgressReduce", {
        defaultValue: "Writing the summary…",
      });
    }
    const key = p.stage === "fold" ? "tabs.summaryProgressFold" : "tabs.summaryProgress";
    return t(key, {
      current: p.chunk,
      total: p.chunks,
      defaultValue: p.stage === "fold"
        ? "Merging notes {{current}} of {{total}}…"
        : "Analyzing part {{current}} of {{total}}…",
    });
  };

  return (
    <div className="summary-tab">
      {boardOcrPartial && (
        <div className="summary-board-warning" role="status">
          {t("summary.boardOcrPartial")}
        </div>
      )}
      {progress && !typed && (
        <div className="summary-progress">
          {progressLabel(progress).replace(/(?:\u2026|\.{3})\s*$/, "")}
          <span className="summary-progress-dots" aria-hidden="true">
            <span>.</span>
            <span>.</span>
            <span>.</span>
          </span>
        </div>
      )}
      {typed && (
        <div className="summary-content">
          <ReactMarkdown>{typed}</ReactMarkdown>
        </div>
      )}
    </div>
  );
};

export default AISummaryTab;