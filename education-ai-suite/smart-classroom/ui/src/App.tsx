import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom'; // Add this import
import TopPanel from './components/TopPanel/TopPanel';
import HeaderBar from './components/Header/Header';
import Body from './components/common/Body';
import Footer from './components/Footer/Footer';
import Modal from './components/Modals/Modal'; // Import your existing Modal
import SettingsForm from './components/Modals/SettingsForm'; // Import your existing SettingsForm
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
      
      {/* Render modal as portal to document.body using your existing Modal component */}
      {createPortal(
        <Modal 
          isOpen={isSettingsOpen}
          onClose={() => setIsSettingsOpen(false)}
          showCloseIcon={true}
        >
          <SettingsForm 
            onClose={() => setIsSettingsOpen(false)}
            projectName={projectName}
            setProjectName={setProjectName}
          />
        </Modal>,
        document.body
      )}
    </div>
  );
};

export default App;