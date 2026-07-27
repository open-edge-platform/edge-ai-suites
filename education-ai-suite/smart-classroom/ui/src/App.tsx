import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom'; // Add this import
import TopPanel from './components/TopPanel/TopPanel';
import HeaderBar from './components/Header/Header';
import Body from './components/common/Body';
import GradingScreen from './components/Grading/GradingScreen';
import Footer from './components/Footer/Footer';
import Modal from './components/Modals/Modal'; // Import your existing Modal
import SettingsForm from './components/Modals/SettingsForm'; // Import your existing SettingsForm
import './App.css';
import './assets/css/HeaderBar.css';
import MetricsPoller from './components/common/MetricsPoller';
import { getSettings, pingBackend } from './services/api';
import { useVideoPipelineMonitor } from "../src/redux/videoMonitor";
import { useTranslation } from 'react-i18next';
import { useFeatureConfig } from './hooks/useFeatureConfig';
  
const App: React.FC = () => {
  const { t } = useTranslation();
  const [projectName, setProjectName] = useState<string>('');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [backendStatus, setBackendStatus] = useState<'checking' | 'available' | 'unavailable'>('checking');
  const [activeScreen, setActiveScreen] = useState<'main' | 'content-search' | 'grading'>('main');
  useVideoPipelineMonitor();

  // Check if any main features are enabled
  const hasMainFeatures = featuresLoaded && guard ? 
    ['asr', 'summary', 'mindmap', 'topic_segmentation', 'video_analytics', 'report'].some(f => guard.hasFeature(f)) : 
    true; // Default to true during loading

  // Auto-switch to content-search screen if only content-search features are enabled
  useEffect(() => {
    if (!featuresLoaded || !guard) return;

    const mainFeatures = ['asr', 'summary', 'mindmap', 'topic_segmentation', 'video_analytics', 'report'];
    const contentSearchFeatures = ['content_search', 'qa'];

    const hasMainFeature = mainFeatures.some(f => guard.hasFeature(f));
    const hasContentSearchFeature = contentSearchFeatures.some(f => guard.hasFeature(f));

    // If only content-search features are enabled (no main features), auto-switch
    if (!hasMainFeature && hasContentSearchFeature) {
      console.log('📋 Only content-search features enabled - auto-switching to content-search screen');
      setActiveScreen('content-search');
    }
  }, [featuresLoaded, guard]);
  const checkBackendHealth = async () => {
    try {
      const isHealthy = await pingBackend();

      if (isHealthy) {
        setBackendStatus('available');
        loadSettings();
        return;
      }

      setBackendStatus('unavailable');
    } catch {
      setBackendStatus('unavailable');
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
    checkBackendHealth(); 
  }, []);

  useEffect(() => {
    if (backendStatus === 'available') return;

    const interval = setInterval(checkBackendHealth, 5000);
    return () => clearInterval(interval);
  }, [backendStatus]);


    if (backendStatus === 'checking') {
    return (
      <div className="app-loading">
        <div className="loading-content">
          <div className="spinner" />
          <h2>Checking backend status</h2>
          <p>Please wait while we connect to the backend…</p>
        </div>
      </div>
    );
  }

  if (backendStatus === 'unavailable') {
    return (
      <div className="app-error">
        <div className="error-content">
          <h1>Backend Not Available</h1>
          <p>
            The backend server is currently unreachable.
            Please ensure it is running.
          </p>
        </div>
      </div>
    );
  }

  // Wait for features to load before rendering main UI
  if (featuresLoading || !featuresLoaded) {
    return (
      <div className="app-loading">
        <div className="loading-content">
          <div className="spinner" />
          <h2>Loading configuration</h2>
          <p>Detecting enabled features from backend…</p>
        </div>
      </div>
    );
  }

  if (featuresError) {
    return (
      <div className="app-error">
        <div className="error-content">
          <h1>Configuration Error</h1>
          <p>{featuresError}</p>
          <p>Please check your backend configuration.</p>
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
        activeScreen={activeScreen}
        setActiveScreen={setActiveScreen}
        featureGuard={guard}
        hasMainFeatures={hasMainFeatures}
      />
      <div style={{ display: activeScreen === 'main' ? 'contents' : 'none' }}>
        <HeaderBar projectName={projectName} setProjectName={setProjectName} featureGuard={guard} />
      </div>
      {activeScreen === 'content-search' && (
        <div className="content-search-subheader">
          <span>{t('contentSearch.subtitle')}</span>
        </div>
      )}
<<<<<<< HEAD
      <div className="main-content">
        <Body isModalOpen={isSettingsOpen} activeScreen={activeScreen} featureGuard={guard} />
=======
      <div style={{ display: activeScreen === 'grading' ? 'none' : 'contents' }}>
        <div className="main-content">
          <Body isModalOpen={isSettingsOpen} activeScreen={activeScreen} />
        </div>
>>>>>>> 5b6e87f38e8d831888df270fd622316f875094dd
      </div>
      {activeScreen === 'grading' && (
        <>
          <div className="header-bar grading-header-bar" />
          <div className="main-content">
            <GradingScreen />
          </div>
        </>
      )}
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
            featureGuard={guard}
          />
        </Modal>,
        document.body
      )}
    </div>
  );
};

export default App;