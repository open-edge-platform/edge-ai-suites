import React, { useState, useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import { startProcessing, stopProcessing } from '../../redux/slices/appSlice';
<<<<<<< HEAD
import { startAllWorkloads, stopAllWorkloads } from '../../redux/slices/servicesSlice';
import { api } from '../../services/api';
import InfoModal from '../InfoModal/InfoModal';
=======
// ADD THIS IMPORT:
import { startAllWorkloads, stopAllWorkloads } from '../../redux/slices/servicesSlice';
import { api } from '../../services/api';
>>>>>>> dev
import '../../assets/css/TopPanel.css';

const TopPanel = () => {
  const dispatch = useAppDispatch();
  const { isProcessing } = useAppSelector((state) => state.app);
  const [notification, setNotification] = useState<string>('');
  const [isBackendReady, setIsBackendReady] = useState(true);
<<<<<<< HEAD
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [showInfoModal, setShowInfoModal] = useState(false);
=======
>>>>>>> dev

  const handleStart = async () => {
    if (!isBackendReady) {
      setNotification('❌ Backend is not ready');
      setTimeout(() => setNotification(''), 5000);
      return;
    }
<<<<<<< HEAD

    if (isStarting || isProcessing) {
      return;
    }
  
    try {
      setIsStarting(true);
      setNotification('🚀 Starting workloads...');
      dispatch(startProcessing());
      dispatch(startAllWorkloads());
=======
  
    try {
      setNotification('🚀 Starting workloads...');
      dispatch(startProcessing());
      dispatch(startAllWorkloads()); // ADD THIS
>>>>>>> dev
      
      const response = await api.start('all');
      
      if (response.status === 'ok') {
<<<<<<< HEAD
        setNotification('✅ Workloads started successfully');
=======
        setNotification('✅ Workloads started successfully'); // REMOVE auto-stop message
>>>>>>> dev
        
        const eventsUrl = api.getEventsUrl(['rppg', 'ai-ecg', 'mdpnp', '3d-pose']);
        dispatch({ type: 'sse/connect', payload: { url: eventsUrl } });
        
<<<<<<< HEAD
        setTimeout(() => setNotification(''), 3000);
      } else {
        throw new Error('Start failed');
=======
        setTimeout(() => setNotification(''), 3000); // CHANGE from 5000 to 3000
      } else {
        setNotification('❌ Failed to start');
        dispatch(stopAllWorkloads()); // ADD THIS
        setTimeout(() => setNotification(''), 3000);
>>>>>>> dev
      }
    } catch (error) {
      console.error('[TopPanel] ❌ Start failed:', error);
      setNotification('❌ Error starting workloads');
      dispatch(stopProcessing());
<<<<<<< HEAD
      dispatch(stopAllWorkloads());
      setTimeout(() => setNotification(''), 5000);
    } finally {
      setIsStarting(false);
=======
      dispatch(stopAllWorkloads()); // ADD THIS
      setTimeout(() => setNotification(''), 5000);
>>>>>>> dev
    }
  };

  const handleStop = async () => {
<<<<<<< HEAD
    if (isStopping || !isProcessing) {
      return;
    }

    try {
      setIsStopping(true);
      setNotification('⏹️ Stopping...');
      dispatch(stopProcessing());
      dispatch(stopAllWorkloads());
=======
    try {
      setNotification('⏹️ Stopping...');
      dispatch(stopProcessing());
      dispatch(stopAllWorkloads()); // ADD THIS
>>>>>>> dev
      
      await api.stop('all');
      dispatch({ type: 'sse/disconnect' });
      
      setNotification('✅ Stopped successfully');
      setTimeout(() => setNotification(''), 3000);
    } catch (error) {
      console.error('[TopPanel] Stop failed:', error);
      setNotification('❌ Failed to stop');
      setTimeout(() => setNotification(''), 3000);
<<<<<<< HEAD
    } finally {
      setIsStopping(false);
    }
  };

  useEffect(() => {
    const checkBackend = async () => {
      try {
        const isReady = await api.pingBackend();
        setIsBackendReady(isReady);
      } catch {
        setIsBackendReady(false);
      }
    };

    checkBackend();
    const interval = setInterval(checkBackend, 10000);
    return () => clearInterval(interval);
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
              cursor: isBackendReady && !isProcessing && !isStarting ? 'pointer' : 'not-allowed'
            }}
          >
            {!isBackendReady ? '⚠️ Offline' : 
             isStarting ? '⏳ Starting...' : 
             isProcessing ? '✅ Running' : 
             '▶️ Start'}
          </button>

          <button
            onClick={handleStop}
            disabled={isStopping || !isProcessing}
            className="stop-button"
            title={!isProcessing ? 'No workloads running' : 'Stop all workloads'}
          >
            {isStopping ? '⏳ Stopping...' : '⏹ Stop'}
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

        <button
          className="guide-button"
          onClick={() => setShowInfoModal(true)}
          title="Medical Reference Guide"
        >
         Guide
        </button>
      </div>

      <InfoModal isOpen={showInfoModal} onClose={() => setShowInfoModal(false)} />
    </>
=======
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
>>>>>>> dev
  );
};

export default TopPanel;