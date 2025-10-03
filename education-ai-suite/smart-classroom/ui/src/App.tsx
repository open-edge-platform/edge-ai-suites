import React, { useState, useEffect } from 'react';
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

  const checkBackendHealth = async () => {
    console.log('Checking backend health...');
    setBackendStatus('checking');

    try {
      const isHealthy = await pingBackend();
      if (isHealthy) {
        console.log('Backend is healthy');
        setBackendStatus('available');
        setRetryCount(0);
        // Load settings only after confirming backend is available
        loadSettings();
      } else {
        console.warn('Backend health check failed');
        setBackendStatus('unavailable');
      }
    } catch (error) {
      console.error('Backend health check error:', error);
      setBackendStatus('unavailable');
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
    checkBackendHealth();
  };

  useEffect(() => {
    // Always check backend health first on app load
    checkBackendHealth();

    // Set up continuous health monitoring every 5 seconds throughout app lifecycle
    const healthCheckInterval = setInterval(() => {
      console.log('Continuous health check (every 5s)...');

      // Only update status if we detect a change to avoid unnecessary re-renders
      pingBackend().then(isHealthy => {
        if (isHealthy && backendStatus === 'unavailable') {
          console.log('Backend recovered - switching to available');
          setBackendStatus('available');
          setRetryCount(0);
          setShowConnectionLostBanner(false); // Clear the banner
          loadSettings();
        } else if (!isHealthy && backendStatus === 'available') {
          console.log('Backend went down - switching to unavailable');
          setBackendStatus('unavailable');
          setShowConnectionLostBanner(true);
        }
      }).catch(error => {
        console.warn('Health check failed:', error);
        if (backendStatus === 'available') {
          console.log('Backend went down due to error - switching to unavailable');
          setBackendStatus('unavailable');
          setShowConnectionLostBanner(true);
        }
      });
    }, 5000); // Check every 5 seconds always

    return () => {
      clearInterval(healthCheckInterval);
    };
  }, [backendStatus]); // Re-run when backendStatus changes

  // Additional retry logic for manual retries when unavailable
  useEffect(() => {
    if (backendStatus === 'unavailable') {
      // This is just for counting retry attempts, the actual checking is handled above
      const timer = setTimeout(() => {
        setRetryCount(prev => prev + 1);
      }, 5000);

      return () => clearTimeout(timer);
    }
  }, [backendStatus, retryCount]);

  // Show loading state while checking backend health
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

  // Show error state if backend is unavailable
  if (backendStatus === 'unavailable') {
    return (
      <div className="app-error">
        <div className="error-content">
          <h1>Backend Connection Lost</h1>
          <p>The connection to the backend server has been interrupted.</p>
          <p>Automatically attempting to reconnect every 5 seconds...</p>
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

  // Render normal app only when backend is available
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
