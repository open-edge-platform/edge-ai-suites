// src/components/TopPanel/TopPanel.tsx
import { useState } from 'react';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import { startProcessing, stopProcessing } from '../../redux/slices/appSlice';
import { api } from '../../services/api';
import '../../assets/css/TopPanel.css';

const TopPanel = () => {
  const dispatch = useAppDispatch();
  const { isProcessing } = useAppSelector((state) => state.app);
  const [notification, setNotification] = useState<string>('');

  const handleStart = async () => {
    try {
      setNotification('Starting workloads...');
      dispatch(startProcessing()); // Enable Stop, Disable Start
      
      const response = await api.start('all');
      
      if (response.status === 'ok') {
        setNotification('Workloads started successfully');
        dispatch({ type: 'sse/connect' });
        
        // Clear notification after 3 seconds
        setTimeout(() => setNotification(''), 3000);
      } else if (response.status === 'locked') {
        setNotification(`Already running (${response.remaining_seconds}s remaining)`);
      }
    } catch (error) {
      console.error('Start failed:', error);
      setNotification('Failed to start workloads');
      dispatch(stopProcessing()); // Revert on error
    }
  };

  const handleStop = async () => {
    try {
      setNotification('Stopping workloads...');
      dispatch(stopProcessing()); // Enable Start, Disable Stop
      
      await api.stop('all');
      dispatch({ type: 'sse/disconnect' });
      setNotification('Workloads stopped successfully');
      
      // Clear notification after 3 seconds
      setTimeout(() => setNotification(''), 3000);
    } catch (error) {
      console.error('Stop failed:', error);
      setNotification('Failed to stop workloads');
      dispatch(startProcessing()); // Revert on error
    }
  };

  return (
    <div className="top-panel">
      <div className="action-buttons">
        <button
          onClick={handleStart}
          disabled={isProcessing}
          className="start-button"
          title={isProcessing ? 'Workloads are running' : 'Start all workloads'}
        >
          Start
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
        {notification && <span>{notification}</span>}
      </div>

      <div className="spacer"></div>
    </div>
  );
};

export default TopPanel;