import React from 'react';
import notificationIcon from '../../assets/images/notification.svg';
import attentionTriangleIcon from '../../assets/images/attention-triangle.svg'; // Import the error icon

interface NotificationsDisplayProps {
  notification: string;
  error?: string | null; 
}

const NotificationsDisplay: React.FC<NotificationsDisplayProps> = ({ notification, error }) => {
  // Dynamically choose the icon based on whether it's an error
  const icon = error ? attentionTriangleIcon : notificationIcon;

  return (
    <div className={`notifications-display ${error ? 'has-error' : ''}`}>
      <img
        src={icon}
        alt={error ? 'Error Icon' : 'Notification Icon'}
        className="notification-icon"
      />
      <span>{error || notification}</span>
    </div>
  );
};

export default NotificationsDisplay;