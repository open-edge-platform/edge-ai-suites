import React, { useState, useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import { startProcessing, stopProcessing } from '../../redux/slices/appSlice';
// ADD THIS IMPORT:
import { startAllWorkloads, stopAllWorkloads } from '../../redux/slices/servicesSlice';
import { api } from '../../services/api';
import '../../assets/css/TopPanel.css';

const TopPanel = () => {
  const dispatch = useAppDispatch();
  const { isProcessing } = useAppSelector((state) => state.app);
  const [notification, setNotification] = useState<string>('');
  const [isBackendReady, setIsBackendReady] = useState(true);
  const [isStarting, setIsStarting] = useState(false); // ADD THIS
  const [isStopping, setIsStopping] = useState(false); // ADD THIS

  const handleStart = async () => {
    if (!isBackendReady) {
      setNotification('❌ Backend is not ready');
      setTimeout(() => setNotification(''), 5000);
      return;
    }
    if (isStarting || isProcessing) {
      return; // FIXED: Prevent double-click
    }
  
    try {
      setIsStarting(true);
      setNotification('🚀 Starting workloads...');
      dispatch(startProcessing());
      dispatch(startAllWorkloads()); // ADD THIS
      
      const response = await api.start('all');
      
      if (response.status === 'ok') {
        setNotification('✅ Workloads started successfully'); // REMOVE auto-stop message
        
        const eventsUrl = api.getEventsUrl(['rppg', 'ai-ecg', 'mdpnp', '3d-pose']);
        dispatch({ type: 'sse/connect', payload: { url: eventsUrl } });
        
        setTimeout(() => setNotification(''), 3000); // CHANGE from 5000 to 3000
      } else {
        setNotification('❌ Failed to start');
        dispatch(stopAllWorkloads()); // ADD THIS
        setTimeout(() => setNotification(''), 3000);
      }
    } catch (error) {
      console.error('[TopPanel] ❌ Start failed:', error);
      setNotification('❌ Error starting workloads');
      dispatch(stopProcessing());
      dispatch(stopAllWorkloads()); // ADD THIS
      setTimeout(() => setNotification(''), 5000);
    }finally {
      setIsStarting(false); // ADD THIS
    }
  };

  const handleStop = async () => {
    if (isStopping || !isProcessing) {
      return; // FIXED: Prevent double-click
    }
    try {
      setIsStopping(true);
      setNotification('⏹️ Stopping...');
      dispatch(stopProcessing());
      dispatch(stopAllWorkloads()); // ADD THIS
      
      await api.stop('all');
      dispatch({ type: 'sse/disconnect' });
      
      setNotification('✅ Stopped successfully');
      setTimeout(() => setNotification(''), 3000);
    } catch (error) {
      console.error('[TopPanel] Stop failed:', error);
      setNotification('❌ Failed to stop');
      setTimeout(() => setNotification(''), 3000);
    }
    finally {
      setIsStopping(false); // ADD THIS
    }
  };

  return (
    <div className="top-panel">
      <div className="action-buttons">
      <button
        onClick={handleStart}
        disabled={isStarting || isProcessing || !isBackendReady}
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
          disabled={isStopping || !isProcessing}
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