import React from 'react';
import { createPortal } from 'react-dom';
import '../../assets/css/Modal.css';
import { useTitleBarTheme } from '../../hooks/useTitleBarTheme';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
  showCloseIcon?: boolean; // Optional prop to show/hide the close icon
  closeOnOverlayClick?: boolean;
}

const Modal: React.FC<ModalProps> = ({ isOpen, onClose, children, showCloseIcon = true, closeOnOverlayClick = true }) => {
  useTitleBarTheme(isOpen, 'dimmed');

  if (!isOpen) return null;

  return createPortal(
    <div className="modal-overlay" onClick={closeOnOverlayClick ? onClose : undefined}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        {showCloseIcon && (
          <button className="modal-close-icon" onClick={onClose}>
            &times;
          </button>
        )}
        {children}
      </div>
    </div>,
    document.body
  );
};

export default Modal;