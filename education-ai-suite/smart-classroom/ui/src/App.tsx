import React, { useEffect, useState } from 'react';
import TopPanel from './components/TopPanel/TopPanel';
import HeaderBar from './components/Header/Header';
import Body from './components/common/Body';
import GradingScreen from './components/Grading/GradingScreen';
import Footer from './components/Footer/Footer';
import ReportPanel from './components/ReportPanel';
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
  const [isReportOpen, setIsReportOpen] = useState(false);
  useVideoPipelineMonitor();

  // Load feature configuration
  const { features, guard, loaded: featuresLoaded, loading: featuresLoading, error: featuresError } = useFeatureConfig();

  // Check if any main features are enabled
  const hasMainFeatures = featuresLoaded && guard ? 
    ['asr', 'summary', 'mindmap', 'topic_segmentation', 'video_analytics', 'report'].some(f => guard.hasFeature(f)) : 
    true; // Default to true during loading

  // Auto-switch to content-search or grading screen if only those features are enabled
  useEffect(() => {
    if (!featuresLoaded || !guard) return;

    const mainFeatures = ['asr', 'summary', 'mindmap', 'topic_segmentation', 'video_analytics', 'report'];
    const contentSearchFeatures = ['content_search', 'qa'];
    const gradingFeatures = ['grading'];

    const hasMainFeature = mainFeatures.some(f => guard.hasFeature(f));
    const hasContentSearchFeature = contentSearchFeatures.some(f => guard.hasFeature(f));
    const hasGradingFeature = gradingFeatures.some(f => guard.hasFeature(f));

    // If main features are disabled, auto-switch based on what's available
    if (!hasMainFeature) {
      // Prefer content-search if available (grading can coexist)
      if (hasContentSearchFeature) {
        console.log('📋 Main features disabled, content-search enabled - auto-switching to content-search screen');
        setActiveScreen('content-search');
      }
      // Only switch to grading if content-search is not available
      else if (hasGradingFeature) {
        console.log('📝 Only grading feature enabled - auto-switching to grading screen');
        setActiveScreen('grading');
      }
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
          <div className="app-spinner" />
          <h2>{t('app.checkingBackendTitle')}</h2>
          <p>{t('app.checkingBackendMessage')}</p>
        </div>
      </div>
    );
  }

  if (backendStatus === 'unavailable') {
    return (
      <div className="app-error">
        <div className="error-content">
          <h1>{t('app.backendUnavailableTitle')}</h1>
          <p>
            {t('app.backendUnavailableMessage')}
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
          <div className="app-spinner" />
          <h2>{t('app.loadingConfigTitle')}</h2>
          <p>{t('app.loadingConfigMessage')}</p>
        </div>
      </div>
    );
  }

  if (featuresError) {
    return (
      <div className="app-error">
        <div className="error-content">
          <h1>{t('app.configErrorTitle')}</h1>
          <p>{featuresError}</p>
          <p>{t('app.configErrorMessage')}</p>
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
        onViewReport={() => setIsReportOpen(true)}
      />
      <div style={{ display: activeScreen === 'main' ? 'contents' : 'none' }}>
        <HeaderBar projectName={projectName} setProjectName={setProjectName} featureGuard={guard} />
      </div>
      {activeScreen === 'content-search' && (
        <div className="content-search-subheader">
          <span>{t('contentSearch.subtitle')}</span>
        </div>
      )}
      <div style={{ display: activeScreen === 'grading' ? 'none' : 'contents' }}>
        <div className="main-content">
          <Body isModalOpen={isSettingsOpen} activeScreen={activeScreen} featureGuard={guard} hasMainFeatures={hasMainFeatures} />
        </div>
      </div>
      {activeScreen === 'grading' && (
        <>
          <div className="main-content">
            <GradingScreen />
          </div>
        </>
      )}
      <Footer />
      
      {/* Report Panel */}
      <ReportPanel
        isOpen={isReportOpen}
        onClose={() => setIsReportOpen(false)}
        featureGuard={guard}
      />
    </div>
  );
};

export default App;