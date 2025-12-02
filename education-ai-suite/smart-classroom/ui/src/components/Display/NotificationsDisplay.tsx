import React from 'react';
import '../../assets/css/NotificationsDisplay.css';
import { useTranslation } from 'react-i18next';
interface NotificationsDisplayProps {
  audioNotification: string;
  videoNotification: string;
  error: string | null;
}

const NotificationsDisplay: React.FC<NotificationsDisplayProps> = ({ 
  audioNotification, 
  videoNotification, 
  error 
}) => {
  const { t } = useTranslation();
  return (
    <div className="notifications-display">
      {error ? (
        <div className="notification-container error">
          <span className="notification-text error-text">{error}</span>
        </div>
      ) : (
        <div className="dual-notifications">
          <div className="notification-container audio">
            <span className="notification-label">{t('notifications.audio')}:</span>
            <span className="notification-text">{audioNotification}</span>
          </div>
          <div className="notification-separator">|</div>
          <div className="notification-container video">
            <span className="notification-label">{t('notifications.video')}:</span>
            <span className="notification-text">{videoNotification}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default NotificationsDisplay;

