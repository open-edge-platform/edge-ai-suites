import { useState, useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import { startProcessing, stopProcessing } from '../../redux/slices/appSlice';
import { startAllWorkloads, stopAllWorkloads } from '../../redux/slices/servicesSlice';
import { resetDetectionState, setActiveDevice } from '../../redux/slices/detectionSlice';
import { api } from '../../services/api';
import '../../assets/css/TopPanel.css';

const TopPanel = () => {
  const dispatch = useAppDispatch();
  const { isProcessing } = useAppSelector((state) => state.app);
  const currentDevice = useAppSelector(
    (state) =>
      state.detection.data.modelInfo?.device ||
      state.detection.data.pipelinePerformance?.workloads?.[0]?.device ||
      'GPU'
  );
  const [notification, setNotification] = useState<string>('');
  const [isBackendReady, setIsBackendReady] = useState(true);
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [isResetting, setIsResetting] = useState(false);

  const handleStart = async () => {
    if (!isBackendReady) {
      setNotification('❌ Backend is not ready');
      setTimeout(() => setNotification(''), 5000);
      return;
    }
    if (isStarting || isProcessing) return;

    try {
      setIsStarting(true);
      setNotification('🚀 Starting...');
      dispatch(startProcessing());
      dispatch(startAllWorkloads());

      const response = await api.start('all');

      if (response.status === 'starting' || response.status === 'running' || response.status === 'ok') {
        const eventsUrl = api.getEventsUrl(['all']);
        dispatch({ type: 'sse/connect', payload: { url: eventsUrl } });
        setNotification('✅ Running');
        setTimeout(() => setNotification(''), 3000);
      } else {
        throw new Error('Start failed');
      }
    } catch (err) {
      console.error('[TopPanel] Start failed:', err);
      setNotification('❌ Error starting pipeline');
      dispatch(stopProcessing());
      dispatch(stopAllWorkloads());
      setTimeout(() => setNotification(''), 5000);
    } finally {
      setIsStarting(false);
    }
  };

  const handleStop = async () => {
    if (isStopping || !isProcessing) return;

    try {
      setIsStopping(true);
      setNotification('⏹️ Stopping...');
      dispatch({ type: 'sse/disconnect' });
      dispatch(stopProcessing());
      dispatch(stopAllWorkloads());

      await api.stop('all');
      setNotification('✅ Stopped successfully');
      setTimeout(() => setNotification(''), 3000);
    } catch (err) {
      console.error('[TopPanel] Stop failed:', err);
      setNotification('❌ Failed to stop');
      setTimeout(() => setNotification(''), 3000);
    } finally {
      setIsStopping(false);
    }
  };

  const handleReset = async () => {
    if (isResetting || isProcessing || isStarting || isStopping) return;
    try {
      setIsResetting(true);
      setNotification('🔄 Resetting session...');
      // Preserve the currently-selected device so the dropdown stays on the
      // user's choice — resetDetectionState clears modelInfo which drives it.
      const dev = currentDevice;
      await api.reset();
      dispatch(resetDetectionState());
      dispatch(setActiveDevice(dev));
      setNotification('✅ Session cleared — ready to Start');
      setTimeout(() => setNotification(''), 3000);
    } catch (err) {
      console.error('[TopPanel] Reset failed:', err);
      const msg = err instanceof Error ? err.message : String(err);
      setNotification(`❌ Reset failed: ${msg}`);
      setTimeout(() => setNotification(''), 5000);
    } finally {
      setIsResetting(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const ok = await api.pingBackend();
        if (!cancelled) setIsBackendReady(ok);
      } catch {
        if (!cancelled) setIsBackendReady(false);
      }
    };
    check();
    const id = setInterval(check, 10000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  return (
    <div className="top-panel">
      <div className="action-buttons">
        <button
          onClick={handleStart}
          disabled={isStarting || isProcessing || !isBackendReady}
          className="start-button"
          style={{
            opacity: isBackendReady && !isProcessing && !isStarting ? 1 : 0.5,
            cursor: isBackendReady && !isProcessing && !isStarting ? 'pointer' : 'not-allowed',
          }}
        >
          {!isBackendReady ? '⚠️ Offline'
            : isStarting ? '⏳ Starting...'
            : isProcessing ? '✅ Running'
            : '▶️ Start'}
        </button>

        <button
          onClick={handleStop}
          disabled={isStopping || !isProcessing}
          className="stop-button"
          title={!isProcessing ? 'No pipeline running' : 'Stop pipeline'}
        >
          {isStopping ? '⏳ Stopping...' : '⏹ Stop'}
        </button>

        <button
          onClick={handleReset}
          disabled={isResetting || isProcessing || isStarting || isStopping}
          className="reset-button"
          title={
            isProcessing
              ? 'Stop the pipeline before resetting'
              : 'Clear the last session (frame + KPIs) so you can change device and Start fresh'
          }
        >
          {isResetting ? '⏳ Resetting...' : '🔄 Reset'}
        </button>
      </div>

      <div className="notification-center">
        {notification && (
          <span style={{
            padding: '8px 16px',
            background: notification.includes('❌') ? '#fee' : notification.includes('⚠️') ? '#ffc' : '#efe',
            borderRadius: '4px',
            fontSize: '13px',
            border: `1px solid ${notification.includes('❌') ? '#fcc' : notification.includes('⚠️') ? '#fc6' : '#cfc'}`,
          }}>
            {notification}
          </span>
        )}
      </div>

      <div className="spacer"></div>
    </div>
  );
};

export default TopPanel;
