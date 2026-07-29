import React, { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import './LeftSidebarMenu.css';
import type { FeatureGuard } from '../../utils/featureGuards';

interface LeftSidebarMenuProps {
  activeScreen: 'main' | 'content-search' | 'grading';
  setActiveScreen: (screen: 'main' | 'content-search' | 'grading') => void;
  onViewReport: () => void;
  featureGuard: FeatureGuard;
  hasMainFeatures: boolean;
}

const LeftSidebarMenu: React.FC<LeftSidebarMenuProps> = ({
  activeScreen,
  setActiveScreen,
  onViewReport,
  featureGuard,
  hasMainFeatures,
}) => {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Check which features are enabled
  const hasContentSearchFeatures = featureGuard.hasFeature('content_search') || featureGuard.hasFeature('qa');
  const hasGradingFeature = featureGuard.hasFeature('grading');
  const hasReportFeature = featureGuard.hasFeature('report');

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const toggleMenu = () => {
    setIsOpen(!isOpen);
  };

  const handleMenuItemClick = (action: () => void) => {
    action();
    setIsOpen(false);
  };

  return (
    <div className="left-sidebar-menu" ref={menuRef}>
      <button
        className="sidebar-menu-toggle"
        onClick={toggleMenu}
        aria-label={t('menu.toggle', 'Toggle menu')}
        title={t('menu.toggle', 'Toggle menu')}
      >
        <span className="hamburger-icon">
          <span></span>
          <span></span>
          <span></span>
        </span>
      </button>

      {isOpen && (
        <div className="sidebar-menu-dropdown">
          <div className="sidebar-menu-header">
            <span>{t('menu.navigation', 'Navigation')}</span>
          </div>
          <ul className="sidebar-menu-list">
            {hasMainFeatures && (
              <li
                className={activeScreen === 'main' ? 'active' : ''}
                onClick={() => handleMenuItemClick(() => setActiveScreen('main'))}
              >
                <span className="menu-icon">🏠</span>
                <span>{t('menu.home', 'Home')}</span>
              </li>
            )}
            {hasContentSearchFeatures && (
              <li
                className={activeScreen === 'content-search' ? 'active' : ''}
                onClick={() => handleMenuItemClick(() => setActiveScreen('content-search'))}
              >
                <span className="menu-icon">🔍</span>
                <span>{t('contentSearch.title', 'Content Search')}</span>
              </li>
            )}
            {hasGradingFeature && (
              <li
                className={activeScreen === 'grading' ? 'active' : ''}
                onClick={() => handleMenuItemClick(() => setActiveScreen('grading'))}
              >
                <span className="menu-icon">📝</span>
                <span>{t('grading.title', 'Grading')}</span>
              </li>
            )}
            {hasReportFeature && (
              <li onClick={() => handleMenuItemClick(onViewReport)}>
                <span className="menu-icon">📊</span>
                <span>{t('reportPanel.title', 'View Report')}</span>
              </li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
};

export default LeftSidebarMenu;
