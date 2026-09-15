import React from 'react';
import { createPortal } from 'react-dom';
import { useTitleBarTheme } from '../../hooks/useTitleBarTheme';

interface GradingModalProps {
  title: React.ReactNode;
  onClose: () => void;
  /** Class of the dialog body, e.g. `grading-picker`, `grading-editor`, `grading-log-modal`. */
  className?: string;
  children: React.ReactNode;
}

/**
 * Shared shell for the grading modals: dimmed overlay, a dialog body with a
 * header (title + close button). Clicking the overlay closes the modal;
 * clicks inside the dialog are swallowed.
 */
const GradingModal: React.FC<GradingModalProps> = ({ title, onClose, className = 'grading-picker', children }) => {
  useTitleBarTheme(true, 'dimmed');

  return createPortal(
    <div className="grading-picker-overlay" onClick={onClose}>
      <div className={className} onClick={(e) => e.stopPropagation()}>
        <div className="grading-picker-header">
          <span className="grading-picker-title">{title}</span>
          <button className="grading-picker-close" onClick={onClose}>
            ×
          </button>
        </div>
        {children}
      </div>
    </div>,
    document.body
  );
};

export default GradingModal;
