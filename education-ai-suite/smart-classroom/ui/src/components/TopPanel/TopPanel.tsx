import React, { useRef, useState, useEffect } from 'react';
import '../../assets/css/TopPanel.css';
import BrandSlot from '../../assets/images/BrandSlot.svg';
import menu from '../../assets/images/settings.svg';
import LanguageSwitcher from '../LanguageSwitcher';
import SettingsModal from '../Menu/SettingsButton';
import { useTranslation } from 'react-i18next';
import type { FeatureGuard } from '../../utils/featureGuards';

interface TopPanelProps {
  projectName: string;
  setProjectName: (name: string) => void;
  isSettingsOpen: boolean;
  setIsSettingsOpen: (isOpen: boolean) => void;
  activeScreen: 'main' | 'content-search' | 'grading';
  setActiveScreen: (screen: 'main' | 'content-search' | 'grading') => void;
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
  const { t } = useTranslation();
  const [isNavMenuOpen, setIsNavMenuOpen] = useState(false);

  const isElectron = !!window.electronAPI?.isElectron;
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

  const openAppMenu = (e: React.MouseEvent<HTMLButtonElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    window.electronAPI?.popupMenu({ x: rect.left, y: rect.bottom });
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
          </ul>
        </div>
      )}
    </div>
  );

  if (activeScreen === 'grading') {
    return (
      <header className="top-panel">
        <div className="brand-slot">
          {isElectron && (
            <button
              className="app-menu-btn"
              onClick={openAppMenu}
              aria-label={t('menu.appMenu', 'Application menu')}
              title={t('menu.appMenu', 'Application menu')}
            >
              &#9776;
            </button>
          )}
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
          {isElectron && (
            <button
              className="app-menu-btn"
              onClick={openAppMenu}
              aria-label={t('menu.appMenu', 'Application menu')}
              title={t('menu.appMenu', 'Application menu')}
            >
              &#9776;
            </button>
          )}
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
        {isElectron && (
          <button
            className="app-menu-btn"
            onClick={openAppMenu}
            aria-label={t('menu.appMenu', 'Application menu')}
            title={t('menu.appMenu', 'Application menu')}
          >
            &#9776;
          </button>
        )}
        {renderNavMenu()}
        <img src={BrandSlot} alt="Intel Logo" className="logo" />
        <span className="app-title">{t('header.title')}</span>
      </div>
      <div className="action-slot">
        <LanguageSwitcher />
        <img
          src={menu}
          alt="Menu Icon"
          className="menu-icon"
          onClick={openSettings}
          ref={menuIconRef}
        />
      </div>
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={closeSettings}
        projectName={projectName}
        setProjectName={setProjectName}
        featureGuard={featureGuard}
      />
    </header>
  );
};

export default TopPanel;
