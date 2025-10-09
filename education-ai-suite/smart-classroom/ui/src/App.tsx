import React, { useState, useEffect, useRef } from 'react';
import TopPanel from './components/TopPanel/TopPanel';
import HeaderBar from './components/Header/Header';
import Body from './components/common/Body';
import Footer from './components/Footer/Footer';
import './App.css';
import MetricsPoller from './components/common/MetricsPoller';
import { getSettings, pingBackend } from './services/api';

const App: React.FC = () => {
  const [projectName, setProjectName] = useState<string>(''); 
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [backendStatus, setBackendStatus] = useState<'checking' | 'available' | 'unavailable'>('checking');
  const [retryCount, setRetryCount] = useState(0);
  const [showConnectionLostBanner, setShowConnectionLostBanner] = useState(false);
  const [consecutiveFailures, setConsecutiveFailures] = useState(0);

  const backendStatusRef = useRef(backendStatus);
  useEffect(() => {
    backendStatusRef.current = backendStatus;
  }, [backendStatus]);

  const checkBackendHealth = async () => {
    console.log('Checking backend health...');
    try {
      const isHealthy = await pingBackend();

      if (isHealthy) {
        if (backendStatusRef.current !== 'available') {
          console.log('Backend is healthy - switching to available');
          setBackendStatus('available');
          setRetryCount(0);
          setShowConnectionLostBanner(false);
          loadSettings();
        }
        setConsecutiveFailures(0);
      } else {
        setConsecutiveFailures(prev => prev + 1);
        if (consecutiveFailures >= 2 && backendStatusRef.current !== 'unavailable') {
          console.warn('Backend health check failed - switching to unavailable');
          setBackendStatus('unavailable');
          setShowConnectionLostBanner(true);
        }
      }
    } catch (error) {
      console.error('Backend health check error:', error);
      setConsecutiveFailures(prev => prev + 1);
      if (consecutiveFailures >= 2 && backendStatusRef.current !== 'unavailable') {
        console.warn('Switching to unavailable due to error');
        setBackendStatus('unavailable');
        setShowConnectionLostBanner(true);
      }
    }
  };

  const loadSettings = async () => {
    try {
      const settings = await getSettings();
      if (settings.projectName) {
        setProjectName(settings.projectName);
      }
    } catch (error) {
      console.warn('Failed to fetch project settings:', error);
    }
  };

  const handleRetry = () => {
    setRetryCount(prev => prev + 1);
    setConsecutiveFailures(0);
    checkBackendHealth();
  };

  useEffect(() => {
    checkBackendHealth();
    const interval = setInterval(() => {
      console.log('Health check every 10s...');
      checkBackendHealth();
    }, 10000); 

    return () => clearInterval(interval);
  }, [consecutiveFailures]); 

  useEffect(() => {
    if (backendStatus === 'unavailable') {
      const timer = setTimeout(() => {
        setRetryCount(prev => prev + 1);
      }, 8000); 

      return () => clearTimeout(timer);
    }
  }, [backendStatus, retryCount]);

  if (backendStatus === 'checking') {
    return (
      <div className="app-loading">
        <div className="loading-content">
          <div className="spinner"></div>
          <h2>Connecting to Backend...</h2>
          <p>Checking backend server availability...</p>
          {retryCount > 0 && (
            <p className="retry-info">Retry attempt: {retryCount}</p>
          )}
        </div>
      </div>
    );
  }

  if (backendStatus === 'unavailable') {
    return (
      <div className="app-error">
        <div className="error-content">
          <h1>Backend Connection Lost</h1>
          <p>The connection to the backend server has been interrupted.</p>
          <p>Automatically attempting to reconnect every 8 seconds...</p>
          {showConnectionLostBanner && (
            <div className="connection-lost-info">
              <p>⚠️ Connection was lost during operation. Any ongoing tasks have been interrupted.</p>
            </div>
          )}
          <div className="error-actions">
            <button onClick={handleRetry} className="retry-button">
              Retry Now
            </button>
          </div>
          {retryCount > 0 && (
            <p className="retry-info">Reconnection attempts: {retryCount}</p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <MetricsPoller /> 
      <TopPanel
        projectName={projectName}
        setProjectName={setProjectName}
        isSettingsOpen={isSettingsOpen}
        setIsSettingsOpen={setIsSettingsOpen}
      />
      <HeaderBar projectName={projectName} setProjectName={setProjectName} />
      <div className="main-content">
        <Body isModalOpen={isSettingsOpen} />
      </div>
      <Footer />
    </div>
  );
};

export default App;