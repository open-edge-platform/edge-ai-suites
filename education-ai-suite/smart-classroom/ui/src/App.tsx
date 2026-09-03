import React, { useCallback, useEffect, useRef, useState } from 'react';
import TopPanel from './components/TopPanel/TopPanel';
import HeaderBar from './components/Header/Header';
import Body from './components/common/Body';
import GradingScreen from './components/Grading/GradingScreen';
import Footer from './components/Footer/Footer';
import ReportPanel from './components/ReportPanel';
import ServicesScreen from './components/Services/ServicesScreen';
import ConfigScreen from './components/Settings/ConfigScreen';
import SetupScreen from './components/Settings/SetupScreen';
import GetStartedScreen from './components/Settings/GetStartedScreen';
import './App.css';
import './assets/css/HeaderBar.css';
import MetricsPoller from './components/common/MetricsPoller';
import { getSettings, pingBackend } from './services/api';
import { isServiceManagerAvailable, useServices } from './services/serviceManager';
import { useSetup } from './services/setupManager';
import { useVideoPipelineMonitor } from "../src/redux/videoMonitor";
import { useTranslation } from 'react-i18next';
import { useFeatureConfig } from './hooks/useFeatureConfig';
import { FeatureGuard } from './utils/featureGuards';
  
const App: React.FC = () => {
  const { t } = useTranslation();
  const [projectName, setProjectName] = useState<string>('');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [backendStatus, setBackendStatus] = useState<'checking' | 'available' | 'unavailable'>('checking');
  const [activeScreen, setActiveScreen] = useState<'main' | 'content-search' | 'grading' | 'services' | 'config' | 'setup' | 'ready'>('main');
  const [isReportOpen, setIsReportOpen] = useState(false);
  const [focusTarget, setFocusTarget] = useState<string | null>(null);
  useVideoPipelineMonitor();

  // Load feature configuration
  const { guard, loaded: featuresLoaded, loading: featuresLoading, error: featuresError } = useFeatureConfig();

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
  // Electron-only screens that replace the whole body rather than sitting
  // inside the normal main/content-search/grading layout.
  const isToolScreen =
    activeScreen === 'services' || activeScreen === 'config' || activeScreen === 'setup' || activeScreen === 'ready';

  // A screen can be opened pointing at one row — a setup step id, or a config
  // field path. Cleared by any other navigation so it never fires twice.
  const openScreen = (screen: typeof activeScreen, target?: string) => {
    setActiveScreen(screen);
    setFocusTarget(target ?? null);
  };

  const renderToolScreen = (screen: typeof activeScreen) => {
    if (screen === 'ready') return <GetStartedScreen onOpenScreen={openScreen} />;
    if (screen === 'config') return <ConfigScreen onOpenScreen={openScreen} focusPath={focusTarget} />;
    if (screen === 'setup') return <SetupScreen onOpenScreen={openScreen} focusStepId={focusTarget} />;
    if (screen === 'services') return <ServicesScreen />;
    return null;
  };

  // Get started is the landing screen whenever anything still needs doing, so a
  // machine with broken prerequisites is told what is wrong instead of being
  // dropped on Services to watch a start fail. Services is only the right
  // landing spot when there is nothing to fix and the backend could run.
  const { services: managedServices } = useServices();
  const { steps: setupSteps } = useSetup();
  const backendService = managedServices.find((service) => service.id === 'backend');
  const setupChecked = setupSteps.some((step) => step.status !== 'unknown');
  const setupBlocking = setupSteps.some((step) => step.status === 'missing' || step.status === 'failed');
  const firstRunScreen =
    setupChecked && !setupBlocking && backendService?.runnable !== false ? 'services' : 'ready';

  // Both are memoised so the effects below can depend on them by name without
  // re-running on every render.
  const loadSettings = useCallback(async () => {
    try {
      const settings = await getSettings();
      if (settings.projectName) setProjectName(settings.projectName);
    } catch {
      console.warn('Failed to fetch project settings');
    }
  }, []);

  const checkBackendHealth = useCallback(async () => {
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
  }, [loadSettings]);

  useEffect(() => {
    checkBackendHealth();
  }, [checkBackendHealth]);

  useEffect(() => {
    if (backendStatus === 'available') return;

    const interval = setInterval(checkBackendHealth, 5000);
    return () => clearInterval(interval);
  }, [backendStatus, checkBackendHealth]);

  // backendStatus is read by the effect below but must not trigger it: that
  // effect exists to react to the managed service changing, and listing our own
  // ping result as a dependency would make every result schedule another ping.
  const backendStatusRef = useRef(backendStatus);
  useEffect(() => {
    backendStatusRef.current = backendStatus;
  }, [backendStatus]);

  // The managed backend reports health faster than the poll above, and keeps
  // reporting it after we go available — so stopping it re-checks immediately
  // instead of leaving a dead UI. Ping stays the authority: VITE_API_BASE_URL
  // may point somewhere the local probe knows nothing about.
  const backendServiceStatus = backendService?.status;
  useEffect(() => {
    if (!isServiceManagerAvailable() || !backendServiceStatus) return;
    // uvicorn binds the port before it can serve, so the first ping can block
    // for its full timeout on the startup spinner. The snapshot already knows.
    if (backendStatusRef.current === 'checking' && backendServiceStatus !== 'healthy') {
      setBackendStatus('unavailable');
      return;
    }
    checkBackendHealth();
  }, [backendServiceStatus, checkBackendHealth]);


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
    // In Electron the backend can be started from here, so show the service
    // manager instead of a dead end. Health polling flips this screen away once
    // the backend answers.
    if (isServiceManagerAvailable()) {
      const screen = isToolScreen ? activeScreen : firstRunScreen;
      return (
        <div className="app">
          <TopPanel
            projectName={projectName}
            setProjectName={setProjectName}
            isSettingsOpen={isSettingsOpen}
            setIsSettingsOpen={setIsSettingsOpen}
            activeScreen={screen}
            setActiveScreen={openScreen}
            // No features are known until the backend answers, so every
            // feature-gated nav entry renders disabled.
            featureGuard={new FeatureGuard([])}
            hasMainFeatures={false}
            onViewReport={() => {}}
          />
          <div className="main-content">{renderToolScreen(screen)}</div>
          <Footer />
        </div>
      );
    }

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
        setActiveScreen={openScreen}
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
      <div style={{ display: activeScreen === 'grading' || isToolScreen ? 'none' : 'contents' }}>
        <div className="main-content">
          <Body isModalOpen={isSettingsOpen} activeScreen={isToolScreen ? 'main' : activeScreen} featureGuard={guard} hasMainFeatures={hasMainFeatures} />
        </div>
      </div>
      {activeScreen === 'grading' && (
        <>
          <div className="main-content">
            <GradingScreen />
          </div>
        </>
      )}
      {isToolScreen && <div className="main-content">{renderToolScreen(activeScreen)}</div>}
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