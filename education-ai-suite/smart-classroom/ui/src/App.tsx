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

  const [backendError, setBackendError] = useState<string | null>(null);

  useEffect(() => {
    const checkBackend = async () => {
      const isAvailable = await pingBackend();
      if (!isAvailable) {
        setBackendError('The backend server is unavailable. Please try again later.');
      }
    };

    checkBackend();
  }, []);

  useEffect(() => {
    if (backendError) return;
    getSettings()
      .then(s => {
        if (s.projectName) setProjectName(s.projectName);
      })
      .catch(() => {
        console.warn('Failed to fetch project settings');
      });
  }, [backendError]);

  if (backendError) {
    return (
      <div className="error-container">
        <div>
          <h1>Backend Unavailable</h1>
          <p>{backendError}</p>
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
