import { useState, useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import { startProcessing, stopProcessing } from '../../redux/slices/appSlice';
import { startAllWorkloads, stopAllWorkloads } from '../../redux/slices/servicesSlice';
import { api } from '../../services/api';
import SettingsModal from '../Settings/SettingsModal';
import '../../assets/css/TopPanel.css';

const TopPanel = () => {
  const dispatch = useAppDispatch();
  const { isProcessing } = useAppSelector((state) => state.app);
  const [notification, setNotification] = useState<string>('');
  const [isBackendReady, setIsBackendReady] = useState(true);
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const handleStart = async () => {
    if (!isBackendReady) {
      setNotification('Backend is not ready');
      setTimeout(() => setNotification(''), 5000);
      return;
    }
    if (isStarting || isProcessing) return;

    try {
      setIsStarting(true);
      setNotification('Starting...');
      dispatch(startProcessing());
      dispatch(startAllWorkloads());

      const response = await api.start('all');

      if (response.status === 'starting' || response.status === 'running' || response.status === 'ok') {
        const eventsUrl = api.getEventsUrl(['all']);
        dispatch({ type: 'sse/connect', payload: { url: eventsUrl } });
        setNotification('Running');
        setTimeout(() => setNotification(''), 3000);
      } else {
        throw new Error('Start failed');
      }
    } catch (err) {
      console.error('[TopPanel] Start failed:', err);
      setNotification('Error starting pipeline');
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
      setNotification('Failed to stop');
      setTimeout(() => setNotification(''), 3000);
    } finally {
      setIsStopping(false);
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
    <>
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
            {!isBackendReady ? 'Offline'
              : isStarting ? 'Starting...'
              : isProcessing ? 'Running'
              : 'Start'}
          </button>

          <button
            onClick={handleStop}
            disabled={isStopping || !isProcessing}
            className="stop-button"
          >
            {isStopping ? 'Stopping...' : 'Stop'}
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

        <div className="top-panel-right">
          <button
            onClick={() => setSettingsOpen(true)}
            className="settings-button"
            aria-label="Open Settings"
            data-tooltip="Open settings"
            data-tooltip-pos="left"
          >
            <span className="settings-button-icon" aria-hidden="true">⚙</span>
            <span className="settings-button-label">Settings</span>
          </button>
        </div>
      </div>

      <SettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </>
  );
};

export default TopPanel;
