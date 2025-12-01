import React from 'react';
import '../../assets/css/NotificationsDisplay.css';

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
  return (
    <div className="notifications-display">
      {error ? (
        <div className="notification-container error">
          <span className="notification-text error-text">{error}</span>
        </div>
      ) : (
        <div className="dual-notifications">
          <div className="notification-container audio">
            <span className="notification-label">Audio:</span>
            <span className="notification-text">{audioNotification}</span>
          </div>
          <div className="notification-separator">|</div>
          <div className="notification-container video">
            <span className="notification-label">Video:</span>
            <span className="notification-text">{videoNotification}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default NotificationsDisplay;