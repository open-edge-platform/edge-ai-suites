import React from 'react';
import '../../assets/css/Modal.css';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  canClose?: () => boolean; // Optional validation function
  children: React.ReactNode;
}

const Modal: React.FC<ModalProps> = ({ isOpen, onClose, canClose, children }) => {
  if (!isOpen) return null;

  const handleOverlayClick = () => {
    if (canClose && !canClose()) {
      return; // Prevent closing if validation fails
    }
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={handleOverlayClick}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        {children}
      </div>
    </div>
  );
};

export default Modal;