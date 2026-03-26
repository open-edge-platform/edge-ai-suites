import React from 'react';
import '../../assets/css/Toast.css';

interface ToastProps {
  message: string;
  onClose: () => void;
  onCopy: () => void;
}

const Toast: React.FC<ToastProps> = ({ message, onClose, onCopy }) => {
  return (
    <div className="toast">
      <div className="toast-message">{message}</div>
      <div className="toast-actions">
        <button className="copy-button" onClick={onCopy}>Copy</button>
        <button className="close-button" onClick={onClose}>×</button>
      </div>
    </div>
  );
};

export default Toast;