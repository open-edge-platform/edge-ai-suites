import React, { useRef } from 'react';
import '../../assets/css/TopPanel.css';
import BrandSlot from '../../assets/images/BrandSlot.svg';
import menu from '../../assets/images/settings.svg';
import LanguageSwitcher from '../LanguageSwitcher';
import SettingsModal from '../Menu/SettingsButton';
import { useTranslation } from 'react-i18next';

interface TopPanelProps {
  projectName: string;
  setProjectName: (name: string) => void;
  isSettingsOpen: boolean;
  setIsSettingsOpen: (isOpen: boolean) => void;
  activeScreen: 'main' | 'content-search';
  setActiveScreen: (screen: 'main' | 'content-search') => void;
}

const TopPanel: React.FC<TopPanelProps> = ({ projectName, setProjectName, isSettingsOpen, setIsSettingsOpen, activeScreen, setActiveScreen }) => {
  const menuIconRef = useRef<HTMLImageElement>(null);
  const { t } = useTranslation();

  const openSettings = () => {
    setIsSettingsOpen(true);
  };

  const closeSettings = () => {
    setIsSettingsOpen(false);
  };

  if (activeScreen === 'content-search') {
    return (
      <header className="top-panel">
        <div className="brand-slot">
          <img src={BrandSlot} alt="Intel Logo" className="logo" />
          <span className="app-title">{t('contentSearch.title', 'Content Search')}</span>
        </div>
        <div className="action-slot">
          <button
            className="content-search-back-btn"
            onClick={() => setActiveScreen('main')}
          >
            {t('contentSearch.back', '← Back')}
          </button>
          <LanguageSwitcher />
        </div>
      </header>
    );
  }

  return (
    <header className="top-panel">
      <div className="brand-slot">
        <img src={BrandSlot} alt="Intel Logo" className="logo" />
        <span className="app-title">{t('header.title')}</span>
      </div>
      <div className="action-slot">
        <button
          className="content-search-btn"
          onClick={() => setActiveScreen('content-search')}
        >
          {t('contentSearch.title', 'Content Search')}
        </button>
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
      />
    </header>
  );
};

export default TopPanel;
