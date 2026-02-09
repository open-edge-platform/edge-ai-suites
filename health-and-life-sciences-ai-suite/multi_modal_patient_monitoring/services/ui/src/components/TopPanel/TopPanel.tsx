// src/components/TopPanel/TopPanel.tsx
import { useState , useEffect} from 'react';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import { startProcessing, stopProcessing } from '../../redux/slices/appSlice';
import { api } from '../../services/api';
import '../../assets/css/TopPanel.css';

const TopPanel = () => {
  const dispatch = useAppDispatch();
  const { isProcessing } = useAppSelector((state) => state.app);
  const [notification, setNotification] = useState<string>('');
  const [isBackendReady, setIsBackendReady] = useState(true);

  // useEffect(() => {
  //   const checkBackend = async () => {
  //     const isHealthy = await api.pingBackend();
  //     setIsBackendReady(isHealthy);
  //     if (!isHealthy) {
  //       setNotification('⚠️ Backend unavailable');
  //     } else if (notification.includes('unavailable')) {
  //       setNotification('');
  //     }
  //   };
  //   checkBackend();
  //   const interval = setInterval(checkBackend, 10000); // Check every 10s
  //   return () => clearInterval(interval);
  // }, []);

  const handleStart = async () => {
    if (!isBackendReady) {
      setNotification('❌ Backend is not ready');
      setTimeout(() => setNotification(''), 5000);
      return;
    }
  
    try {
      setNotification('🚀 Starting workloads...');
      dispatch(startProcessing());
      
      console.log('[TopPanel] 🔵 Calling API start...');
      const response = await api.start('all');
      console.log('[TopPanel] 🟢 API response:', response);
      
      if (response.status === 'ok') {
        const autoStopTime = response.auto_stop_in_seconds || 60;
        setNotification(`✅ Started (auto-stop in ${autoStopTime}s)`);
        
        // Connect SSE
        const eventsUrl = api.getEventsUrl(['rppg', 'ai-ecg', 'mdpnp', '3d-pose']);
        console.log('[TopPanel] 🟡 SSE URL:', eventsUrl);
        console.log('[TopPanel] 🟡 Dispatching sse/connect...');
        
        dispatch({ type: 'sse/connect', payload: { url: eventsUrl } });
        
        console.log('[TopPanel] ✅ SSE connect dispatched');
        
        setTimeout(() => setNotification(''), 5000);
      } else {
        setNotification('❌ Failed to start');
        setTimeout(() => setNotification(''), 3000);
      }
    } catch (error) {
      console.error('[TopPanel] ❌ Start failed:', error);
      setNotification('❌ Error starting workloads');
      dispatch(stopProcessing());
      setTimeout(() => setNotification(''), 5000);
    }
  };
  const handleStop = async () => {
    try {
      setNotification('⏹️ Stopping...');
      dispatch(stopProcessing());
      
      await api.stop('all');
      dispatch({ type: 'sse/disconnect' });
      
      setNotification('✅ Stopped successfully');
      setTimeout(() => setNotification(''), 3000);
    } catch (error) {
      console.error('[TopPanel] Stop failed:', error);
      setNotification('❌ Failed to stop');
      dispatch(startProcessing()); // Revert
      setTimeout(() => setNotification(''), 3000);
    }
  };

  return (
    <div className="top-panel">
      <div className="action-buttons">
      <button
        onClick={handleStart}
        disabled={isProcessing || !isBackendReady}
        className="start-button"
        style={{
          opacity: isBackendReady && !isProcessing ? 1 : 0.5,
          cursor: isBackendReady && !isProcessing ? 'pointer' : 'not-allowed'
        }}
      >
        {!isBackendReady ? '⚠️ Offline' : isProcessing ? '▶️ Running' : '▶️ Start'}
      </button>

        <button
          onClick={handleStop}
          disabled={!isProcessing}
          className="stop-button"
          title={!isProcessing ? 'No workloads running' : 'Stop all workloads'}
        >
          Stop
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