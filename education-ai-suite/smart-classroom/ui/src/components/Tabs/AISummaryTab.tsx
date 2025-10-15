import React, { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import "../../assets/css/AISummaryTab.css";
import { useAppDispatch, useAppSelector } from "../../redux/hooks";
import { firstSummaryToken, summaryDone, clearSummaryStartRequest } from "../../redux/slices/uiSlice";
import { appendSummary, finishSummary, startSummary } from "../../redux/slices/summarySlice";
import { streamSummary } from "../../services/api";

const activeSummarySessions = new Set<string>();

const AISummaryTab: React.FC = () => {
  const dispatch = useAppDispatch();
  const summaryEnabled = useAppSelector(s => s.ui.summaryEnabled);
  const isLoading = useAppSelector(s => s.ui.summaryLoading);
  const { streamingText, finalText } = useAppSelector(s => s.summary);
  const sessionId = useAppSelector(s => s.ui.sessionId);
  const shouldStartSummary = useAppSelector(s => s.ui.shouldStartSummary);

  const startedRef = useRef(false);
  const sessionRef = useRef<string | null>(null);

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

    (async () => {
      try {
        let sentFirst = false;
        for await (const ev of streamSummary(sessionId)) {
          if (ev.type === "summary_token") {
            if (!sentFirst) { dispatch(firstSummaryToken()); sentFirst = true; }
            dispatch(appendSummary(ev.token));
          } else if (ev.type === "error") {
            window.dispatchEvent(new CustomEvent('global-error', { detail: ev.message || 'Summary error' }));
            dispatch(finishSummary());
            dispatch(summaryDone());
            break;
          } else if (ev.type === "done") {
            dispatch(finishSummary());
            dispatch(summaryDone());
            break;
          }
        }
      } catch (e: any) {
        if (e?.name !== 'AbortError') console.error('[AISummaryTab] stream error', e);
        dispatch(finishSummary());
        dispatch(summaryDone());
      } finally {
        console.log('[AISummaryTab] stream finished', sessionId);
      }
    })();
  }, [summaryEnabled, shouldStartSummary, sessionId, dispatch]);

  const typed = finalText ?? streamingText;

  return (
    <div className="summary-tab">
      {isLoading && (
        <div className="summary-loading">
          <span className="tab-spinner" aria-label="loading" />
          Generating summary…
        </div>
      )}
      <div className="summary-content">
        <ReactMarkdown>{typed}</ReactMarkdown>
      </div>
    </div>
  );
};

export default AISummaryTab;
