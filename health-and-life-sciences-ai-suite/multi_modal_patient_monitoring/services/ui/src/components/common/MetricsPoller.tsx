import { useEffect, useRef } from 'react';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import { setPlatformInfo, setWorkloadDevices, setMetrics } from '../../redux/slices/metricsSlice';
import { getPlatformInfo, getWorkloadDevices, getResourceMetrics } from '../../services/api';

const POLL_INTERVAL = 3000;

export function MetricsPoller() {
  const dispatch = useAppDispatch();
  const isProcessing = useAppSelector((state) => state.app.isProcessing);
  const intervalRef = useRef<number | null>(null);

  // Fetch platform info and workload devices once on mount
  useEffect(() => {
    (async () => {
      try {
        // Fetch platform info
        const platformInfo = await getPlatformInfo();
        dispatch(setPlatformInfo(platformInfo));
        console.log('[MetricsPoller] ✓ Platform info loaded:', platformInfo);

        // Fetch workload devices - ADD THIS
        const workloadDevices = await getWorkloadDevices();
        dispatch(setWorkloadDevices(workloadDevices));
        console.log('[MetricsPoller] ✓ Workload devices loaded:', workloadDevices);
      } catch (error) {
        console.error('[MetricsPoller] ❌ Failed to load initial data:', error);
      }
    })();
  }, [dispatch]);

  // Poll metrics when processing
  useEffect(() => {
    if (!isProcessing) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }

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
      }
    };
  }, [isProcessing, dispatch]);

  return null;
}