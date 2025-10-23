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
  const wasInitiallyUnavailableRef = useRef(false);
  const reloadTriggeredRef = useRef(false);

  const checkBackendHealth = async () => {
    try {
      const isHealthy = await pingBackend();
      if (isHealthy) {
        setBackendStatus('available');
        // reload only if backend was initially unavailable
        if (wasInitiallyUnavailableRef.current && !reloadTriggeredRef.current) {
          reloadTriggeredRef.current = true;
          window.location.reload();
          return;
        }
        loadSettings();
      } else {
        setBackendStatus('unavailable');
        if (!wasInitiallyUnavailableRef.current) {
          wasInitiallyUnavailableRef.current = true;
        }
      }
    } catch {
      setBackendStatus('unavailable');
      if (!wasInitiallyUnavailableRef.current) {
        wasInitiallyUnavailableRef.current = true;
      }
    }
  };

  const loadSettings = async () => {
    try {
      const settings = await getSettings();
      if (settings.projectName) setProjectName(settings.projectName);
    } catch {
      console.warn('Failed to fetch project settings');
    }
  };

  useEffect(() => {
    checkBackendHealth(); // initial check
  }, []);

  useEffect(() => {
    if ((backendStatus === 'unavailable' || backendStatus === 'checking') && wasInitiallyUnavailableRef.current && !reloadTriggeredRef.current) {
      const interval = setInterval(() => {
        checkBackendHealth();
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [backendStatus]);

  if (backendStatus === 'checking') {
    return (
      <div className="app-loading">
        <div className="loading-content">
          <div className="spinner"></div>
          <h2>Connecting to Backend...</h2>
          <p>Checking backend server availability...</p>
        </div>
      </div>
    );
  }

  if (backendStatus === 'unavailable') {
    return (
      <div className="app-error">
        <div className="error-content">
          <h1>Backend Connection Lost</h1>
          <p>Please check your server. Auto reload will occur once backend is up.</p>
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