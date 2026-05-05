// ...existing code...
import { useEffect, useRef } from "react";
import { useAppDispatch, useAppSelector } from "../../redux/hooks";
import { getResourceMetrics } from "../../services/api";
import { setMetrics } from "../../redux/slices/resourceSlice";

const POLL_MS = 3000;

const MetricsPoller: React.FC = () => {
  const sessionId = useAppSelector(s => s.ui.sessionId);
  const aiProcessing = useAppSelector(s => s.ui.aiProcessing);
  const csProcessing = useAppSelector(s => s.ui.csProcessing);
  const summaryStatus = useAppSelector(s => s.summary.status);
  const monitoringPaused = useAppSelector(s => s.ui.monitoringPaused);
  const dispatch = useAppDispatch();

  const timeoutRef = useRef<number | null>(null);
  const finalFetchDoneRef = useRef(false);
  const lastSessionRef = useRef<string | null>(null);

  useEffect(() => {
    const effectiveSessionId = sessionId;

    if (lastSessionRef.current !== effectiveSessionId) {
      if (timeoutRef.current) { clearTimeout(timeoutRef.current); timeoutRef.current = null; }
      finalFetchDoneRef.current = false;
      lastSessionRef.current = effectiveSessionId;
    }

    if (!effectiveSessionId) {
      if (timeoutRef.current) { clearTimeout(timeoutRef.current); timeoutRef.current = null; }
      finalFetchDoneRef.current = false;
      return; // keep previous metrics visible
    }

    // Stop polling when monitoring has been paused by the duration timer
    if (monitoringPaused) {
      if (timeoutRef.current) { clearTimeout(timeoutRef.current); timeoutRef.current = null; }
      return;
    }

    if (summaryStatus === 'done' && !aiProcessing && !csProcessing) {
      if (timeoutRef.current) { clearTimeout(timeoutRef.current); timeoutRef.current = null; }
      if (!finalFetchDoneRef.current) {
        (async () => {
          try { dispatch(setMetrics(await getResourceMetrics(effectiveSessionId))); } catch {}
          finally { finalFetchDoneRef.current = true; }
        })();
      }
      return; 
    }

    const shouldPoll = aiProcessing || csProcessing || summaryStatus === 'streaming';
    if (!shouldPoll) return;

    let cancelled = false;
    const poll = async () => {
      if (cancelled) return;
      try { dispatch(setMetrics(await getResourceMetrics(effectiveSessionId))); } catch (e) { console.warn('Metrics poll error:', e); }
      finally { if (!cancelled) timeoutRef.current = window.setTimeout(poll, POLL_MS); }
    };
    poll();

    return () => {
      cancelled = true;
      if (timeoutRef.current) { clearTimeout(timeoutRef.current); timeoutRef.current = null; }
    };
  }, [sessionId, aiProcessing, csProcessing, summaryStatus, monitoringPaused, dispatch]);

  return null;
};

export default MetricsPoller;
