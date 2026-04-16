import { useEffect, useRef } from 'react';
import { useAppDispatch, useAppSelector } from '../redux/hooks';
import { setMonitoringActive, setMonitoringPaused } from '../redux/slices/uiSlice';
import { startMonitoring, stopMonitoring } from '../services/api';
import { RESOURCE_METRIC_DURATION_MS } from '../utils/resourceMetricConfig';

/**
 * Automatically pauses resource metric polling after RESOURCE_METRIC_DURATION_MS.
 * Sets monitoringPaused=true in Redux when the duration expires.
 * Provides a resumeMonitoring() function to restart polling and reset the timer.
 */
export function useResourceMetricTimer() {
  const dispatch = useAppDispatch();
  const monitoringActive = useAppSelector((s) => s.ui.monitoringActive);
  const sessionId = useAppSelector((s) => s.ui.sessionId);
  const timerRef = useRef<number | null>(null);

  const clearTimer = () => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };

  useEffect(() => {
    if (monitoringActive) {
      clearTimer();
      timerRef.current = window.setTimeout(async () => {
        try {
          await stopMonitoring();
        } catch {
          // best-effort: proceed even if the API call fails
        }
        dispatch(setMonitoringActive(false));
        dispatch(setMonitoringPaused(true));
      }, RESOURCE_METRIC_DURATION_MS);
    } else {
      clearTimer();
    }

    return clearTimer;
  }, [monitoringActive, dispatch]);

  const resumeMonitoring = async () => {
    if (!sessionId) return;
    try {
      await startMonitoring(sessionId);
      dispatch(setMonitoringPaused(false));
      dispatch(setMonitoringActive(true));
    } catch (e) {
      console.error('Failed to resume resource metric monitoring:', e);
    }
  };

  return { resumeMonitoring };
}
