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

  // Check if we have any notifications to show
  const hasAudio = audioNotification && audioNotification.trim() !== '';
  const hasVideo = videoNotification && videoNotification.trim() !== '';
  const hasAnyNotification = hasAudio || hasVideo || error;

  // If no notifications at all, don't render anything
  if (!hasAnyNotification) {
    return null;
  }

  return (
    <div className="notifications-display">
      {error ? (
        <div className="notification-container error">
          {/* Kept to one line so the navbar height stays put; the full text —
              which can list a reason per camera — is on hover. */}
          <span className="notification-text error-text" title={error}>{error}</span>
        </div>
      ) : (
        <div className="dual-notifications">
          {hasAudio && (
            <>
              <div className="notification-container audio">
                <span className="notification-label">{t('notifications.audio')}:</span>
                <span className="notification-text" title={audioNotification}>{audioNotification}</span>
              </div>
              {hasVideo && <div className="notification-separator">|</div>}
            </>
          )}
          {hasVideo && (
            <div className="notification-container video">
              <span className="notification-label">{t('notifications.video')}:</span>
              <span className="notification-text" title={videoNotification}>{videoNotification}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default NotificationsDisplay;

