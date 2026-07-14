import { useEffect, useRef } from 'react';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import { setPlatformInfo, setMetrics } from '../../redux/slices/metricsSlice';
import { getPlatformInfo, getResourceMetrics } from '../../services/api';

const POLL_INTERVAL = 3000;

export function MetricsPoller() {
  const dispatch = useAppDispatch();
  const isProcessing = useAppSelector((state) => state.app.isProcessing);
  const intervalRef = useRef<number | null>(null);

  // Fetch platform info once on mount
  useEffect(() => {
    (async () => {
      try {
        const platformInfo = await getPlatformInfo();
        dispatch(setPlatformInfo(platformInfo));
        console.log('[MetricsPoller] ✓ Platform info loaded:', platformInfo);
      } catch (error) {
        console.error('[MetricsPoller] ❌ Failed to load initial data:', error);
      }
    })();
  }, [dispatch]);

  // Poll hardware metrics only while processing.
  // When stopped, charts freeze showing the last captured data.
  useEffect(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    if (!isProcessing) return;

    const pollMetrics = async () => {
      try {
        const metrics = await getResourceMetrics();
        dispatch(setMetrics(metrics));
      } catch (error) {
        console.error('[MetricsPoller] ❌ Failed to fetch metrics:', error);
      }
    };

    pollMetrics();
    intervalRef.current = window.setInterval(pollMetrics, POLL_INTERVAL);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [dispatch, isProcessing]);

  return null;
}