import { useEffect, useRef } from 'react';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import setPlatformInfo from '../../redux/slices/metricsSlice';
import setResourceMetrics from '../../redux/slices/metricsSlice';
import { getPlatformInfo, getResourceMetrics } from '../../services/api';

const POLL_INTERVAL = 3000; // 3 seconds

/**
 * Background component that polls /platform-info and /metrics
 * Only polls when isProcessing is true
 */
export function MetricsPoller() {
  const dispatch = useAppDispatch();
  const isProcessing = useAppSelector((state) => state.app.isProcessing);
  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    // Fetch platform info once on mount (doesn't change)
    (async () => {
      try {
        const platformInfo = await getPlatformInfo();
        dispatch(setPlatformInfo(platformInfo));
        console.log('[MetricsPoller] ✓ Platform info loaded:', platformInfo);
      } catch (error) {
        console.error('[MetricsPoller] ❌ Failed to load platform info:', error);
      }
    })();
  }, [dispatch]);

  useEffect(() => {
    if (!isProcessing) {
      // Stop polling when not processing
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
        console.log('[MetricsPoller] ⏸️ Stopped polling');
      }
      return;
    }

    console.log('[MetricsPoller] ▶️ Started polling');

    // Poll immediately
    pollMetrics();

    // Then poll every 3 seconds
    intervalRef.current = window.setInterval(pollMetrics, POLL_INTERVAL);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [isProcessing, dispatch]);

  const pollMetrics = async () => {
    try {
      const metrics = await getResourceMetrics();
      dispatch(setResourceMetrics(metrics));
      console.log('[MetricsPoller] ✓ Metrics updated:', {
        cpu: metrics.cpu_utilization.length,
        gpu: metrics.gpu_utilization.length,
        memory: metrics.memory.length,
        power: metrics.power.length
      });
    } catch (error) {
      console.error('[MetricsPoller] ❌ Failed to fetch metrics:', error);
    }
  };

  return null; // This component doesn't render anything
}