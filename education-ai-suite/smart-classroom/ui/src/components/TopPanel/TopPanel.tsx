import React, { useRef, useState, useEffect } from 'react';
import '../../assets/css/TopPanel.css';
import BrandSlot from '../../assets/images/BrandSlot.svg';
import menu from '../../assets/images/settings.svg';
import LanguageSwitcher from '../LanguageSwitcher';
import SettingsModal from '../Menu/SettingsButton';
import { useTranslation } from 'react-i18next';
import { isServiceManagerAvailable } from '../../services/serviceManager';
import type { FeatureGuard } from '../../utils/featureGuards';

interface TopPanelProps {
  projectName: string;
  setProjectName: (name: string) => void;
  isSettingsOpen: boolean;
  setIsSettingsOpen: (isOpen: boolean) => void;
  activeScreen: 'main' | 'content-search' | 'grading' | 'services' | 'config' | 'setup' | 'ready';
  setActiveScreen: (screen: 'main' | 'content-search' | 'grading' | 'services' | 'config' | 'setup' | 'ready') => void;
  featureGuard: FeatureGuard;
  hasMainFeatures: boolean;
  onViewReport: () => void;
}

const TopPanel: React.FC<TopPanelProps> = ({
  projectName,
  setProjectName,
  isSettingsOpen,
  setIsSettingsOpen,
  activeScreen,
  setActiveScreen,
  featureGuard,
  hasMainFeatures,
  onViewReport
}) => {
  const menuIconRef = useRef<HTMLImageElement>(null);
  const navMenuRef = useRef<HTMLDivElement>(null);
  const navToggleRef = useRef<HTMLButtonElement>(null);
  const { t } = useTranslation();
  const [isNavMenuOpen, setIsNavMenuOpen] = useState(false);

  const isElectron = !!window.electronAPI?.isElectron;
  const hasServiceManager = isServiceManagerAvailable();
  // The gear edits session settings over the backend API. The tool screens are
  // where that is either redundant (Configuration) or impossible: App renders
  // them whenever the backend is unreachable.
  const isToolScreen =
    activeScreen === 'services' ||
    activeScreen === 'config' ||
    activeScreen === 'setup' ||
    activeScreen === 'ready';
  // Show Content Search UI if either content_search OR qa feature is enabled
  const hasContentSearchFeatures = featureGuard.hasFeature('content_search') || featureGuard.hasFeature('qa');
  const hasGradingFeature = featureGuard.hasFeature('grading');
  const hasReportFeature = featureGuard.hasFeature('report');

  // Close nav menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (navMenuRef.current && !navMenuRef.current.contains(event.target as Node)) {
        setIsNavMenuOpen(false);
      }
    };

    if (isNavMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isNavMenuOpen]);

  const toggleNavMenu = () => {
    setIsNavMenuOpen(!isNavMenuOpen);
  };

  const handleNavItemClick = (action: () => void) => {
    action();
    setIsNavMenuOpen(false);
  };

  // Electron only: open the native application menu (File/Edit/View/Window).
  // Anchored under the hamburger toggle. Using the still-visible toggle 
  // makes the native menu appear where the dropdown was.
  const openAppMenu = () => {
    const rect = navToggleRef.current?.getBoundingClientRect();
    window.electronAPI?.popupMenu(
      rect ? { x: rect.left, y: rect.bottom + 8 } : undefined
    );
  };

  const openSettings = () => {
    setIsSettingsOpen(true);
  };

  const closeSettings = () => {
    setIsSettingsOpen(false);
  };

  // Reusable navigation menu component
  const renderNavMenu = () => (
    <div className="nav-menu-container" ref={navMenuRef}>
      <button
        ref={navToggleRef}
        className="nav-menu-toggle"
        onClick={toggleNavMenu}
        aria-label={t('menu.toggle', 'Toggle menu')}
        title={t('menu.toggle', 'Toggle menu')}
      >
        <span className="hamburger-icon">
          <span></span>
          <span></span>
          <span></span>
        </span>
      </button>
      {isNavMenuOpen && (
        <div className="nav-menu-dropdown">
          <div className="nav-menu-header">
            <span>{t('menu.navigation', 'Navigation')}</span>
          </div>
          <ul className="nav-menu-list">
            <li
              className={`${activeScreen === 'main' ? 'active' : ''} ${!hasMainFeatures ? 'no-click' : ''}`}
              onClick={() => hasMainFeatures && handleNavItemClick(() => setActiveScreen('main'))}
            >
              <span className="menu-icon">🏠</span>
              <span className={!hasMainFeatures ? 'disabled' : ''}>{t('menu.home', 'Home')}</span>
            </li>
            <li
              className={`${activeScreen === 'content-search' ? 'active' : ''} ${!hasContentSearchFeatures ? 'no-click' : ''}`}
              onClick={() => hasContentSearchFeatures && handleNavItemClick(() => setActiveScreen('content-search'))}
            >
              <span className="menu-icon">🔍</span>
              <span className={!hasContentSearchFeatures ? 'disabled' : ''}>{t('contentSearch.title', 'Content Search')}</span>
            </li>
            <li
              className={`${activeScreen === 'grading' ? 'active' : ''} ${!hasGradingFeature ? 'no-click' : ''}`}
              onClick={() => hasGradingFeature && handleNavItemClick(() => setActiveScreen('grading'))}
            >
              <span className="menu-icon">📝</span>
              <span className={!hasGradingFeature ? 'disabled' : ''}>{t('grading.title', 'Grading')}</span>
            </li>
            <li
              className={!hasReportFeature ? 'no-click' : ''}
              onClick={() => hasReportFeature && handleNavItemClick(onViewReport)}
            >
              <span className="menu-icon">📊</span>
              <span className={!hasReportFeature ? 'disabled' : ''}>{t('reportPanel.title', 'View Report')}</span>
            </li>
            {/* Electron only: supervision of the Python backend processes */}
            {hasServiceManager && (
              <li
                className={`nav-menu-tools${activeScreen === 'ready' ? ' active' : ''}`}
                onClick={() => handleNavItemClick(() => setActiveScreen('ready'))}
              >
                <span className="menu-icon">🧭</span>
                <span>{t('getStarted.title', 'Get started')}</span>
              </li>
            )}
            {/* Electron only: prerequisite checks and environment preparation */}
            {hasServiceManager && (
              <li
                className={activeScreen === 'setup' ? 'active' : ''}
                onClick={() => handleNavItemClick(() => setActiveScreen('setup'))}
              >
                <span className="menu-icon">🧰</span>
                <span>{t('setup.title', 'Setup')}</span>
              </li>
            )}
            {/* Electron only: schema-guarded editor for config.yaml and friends */}
            {hasServiceManager && (
              <li
                className={activeScreen === 'config' ? 'active' : ''}
                onClick={() => handleNavItemClick(() => setActiveScreen('config'))}
              >
                <span className="menu-icon">🔧</span>
                <span>{t('config.title', 'Configuration')}</span>
              </li>
            )}
            {hasServiceManager && (
              <li
                className={activeScreen === 'services' ? 'active' : ''}
                onClick={() => handleNavItemClick(() => setActiveScreen('services'))}
              >
                <span className="menu-icon">🖥️</span>
                <span>{t('services.title', 'Services')}</span>
              </li>
            )}
            {/* Electron only: the native application menu (File/Edit/View/Window) */}
            {isElectron && (
              <li
                className="nav-menu-app-menu"
                onClick={() => {
                  setIsNavMenuOpen(false);
                  openAppMenu();
                }}
              >
                <span className="menu-icon">⚙️</span>
                <span>{t('menu.appMenu', 'Application menu')}</span>
              </li>
            )}
          </ul>
        </div>
      )}
    </div>
  );

  if (activeScreen === 'grading') {
    return (
      <header className="top-panel">
        <div className="brand-slot">
          {renderNavMenu()}
          <img src={BrandSlot} alt="Intel Logo" className="logo" />
          <span className="app-title">{t('grading.title', 'Grading')}</span>
        </div>
        <div className="action-slot">
          <LanguageSwitcher />
        </div>
      </header>
    );
  }

  if (activeScreen === 'content-search') {
    return (
      <header className="top-panel">
        <div className="brand-slot">
          {renderNavMenu()}
          <img src={BrandSlot} alt="Intel Logo" className="logo" />
          <span className="app-title">{t('contentSearch.title', 'Content Search')}</span>
        </div>
        <div className="action-slot">
          <LanguageSwitcher />
        </div>
      </header>
    );
  }

  return (
    <header className="top-panel">
      <div className="brand-slot">
        {renderNavMenu()}
        <img src={BrandSlot} alt="Intel Logo" className="logo" />
        <span className="app-title">{t('header.title')}</span>
      </div>
      <div className="action-slot">
        <LanguageSwitcher />
        {!isToolScreen && (
          <img
            src={menu}
            alt="Menu Icon"
            className="menu-icon"
            onClick={openSettings}
            ref={menuIconRef}
          />
        )}
      </div>
      {!isToolScreen && (
        <SettingsModal
          isOpen={isSettingsOpen}
          onClose={closeSettings}
          projectName={projectName}
          setProjectName={setProjectName}
          featureGuard={featureGuard}
        />
      )}
    </header>
  );
};

export default TopPanel;
