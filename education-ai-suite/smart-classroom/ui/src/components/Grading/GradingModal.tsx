import React from 'react';

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
const GradingModal: React.FC<GradingModalProps> = ({ title, onClose, className = 'grading-picker', children }) => (
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
  </div>
);

export default GradingModal;
