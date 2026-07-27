import React, { useRef } from 'react';
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
}

const TopPanel: React.FC<TopPanelProps> = ({ 
  projectName, 
  setProjectName, 
  isSettingsOpen, 
  setIsSettingsOpen, 
  activeScreen, 
  setActiveScreen,
  featureGuard,
  hasMainFeatures
}) => {
  const menuIconRef = useRef<HTMLImageElement>(null);
  const { t } = useTranslation();

  const isElectron = !!window.electronAPI?.isElectron;
  // Show Content Search UI if either content_search OR qa feature is enabled
  const hasContentSearchFeatures = featureGuard.hasFeature('content_search') || featureGuard.hasFeature('qa');

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
          <img src={BrandSlot} alt="Intel Logo" className="logo" />
          <span className="app-title">{t('grading.title', 'Grading')}</span>
        </div>
        <div className="action-slot">
          <button
            className="content-search-back-btn"
            onClick={() => setActiveScreen('main')}
          >
            {t('grading.back', '← Back')}
          </button>
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
          <img src={BrandSlot} alt="Intel Logo" className="logo" />
          <span className="app-title">{t('contentSearch.title', 'Content Search')}</span>
        </div>
        <div className="action-slot">
          {/* Only show back button if there are main features to go back to */}
          {hasMainFeatures && (
            <button
              className="content-search-back-btn"
              onClick={() => setActiveScreen('main')}
            >
              {t('contentSearch.back', '← Back')}
            </button>
          )}
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
        <img src={BrandSlot} alt="Intel Logo" className="logo" />
        <span className="app-title">{t('header.title')}</span>
      </div>
      <div className="action-slot">
<<<<<<< HEAD
        {/* Only show Content Search button if content_search or qa feature is enabled */}
        {hasContentSearchFeatures && (
          <button
            className="content-search-btn"
            onClick={() => setActiveScreen('content-search')}
          >
            {t('contentSearch.title', 'Content Search')}
          </button>
        )}
=======
        <button
          className="content-search-btn"
          onClick={() => setActiveScreen('content-search')}
        >
          {t('contentSearch.title', 'Content Search')}
        </button>
        <button
          className="content-search-btn"
          onClick={() => setActiveScreen('grading')}
        >
          {t('grading.open', 'Grading')}
        </button>
>>>>>>> 5b6e87f38e8d831888df270fd622316f875094dd
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
