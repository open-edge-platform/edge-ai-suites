import React from 'react';
import '../../assets/css/Modal.css';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
  showCloseIcon?: boolean; // Optional prop to show/hide the close icon
}

const Modal: React.FC<ModalProps> = ({ isOpen, onClose, children, showCloseIcon = true }) => {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        {showCloseIcon && (
          <button className="modal-close-icon" onClick={onClose}>
            &times;
          </button>
        )}
        {children}
      </div>
    </div>
  );
};

export default Modal;