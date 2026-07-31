import React, { useEffect, useState } from 'react';
import '../../assets/css/DisclaimerModal.css';

const ACK_KEY = 'surgical_disclaimer_ack_v1';

interface DisclaimerModalProps {
  /** Force the modal open (for a "View disclaimer" link, if we ever add one). */
  forceOpen?: boolean;
  /** Called after the user acknowledges. */
  onAcknowledge?: () => void;
}

/**
 * First-run disclaimer. Persists an ack flag in localStorage so we only show
 * it once per browser profile. Purely client-side — the backend does not
 * gate on it, so nothing here should be treated as a security control.
 */
const DisclaimerModal: React.FC<DisclaimerModalProps> = ({ forceOpen, onAcknowledge }) => {
  const [open, setOpen] = useState<boolean>(() => {
    if (forceOpen) return true;
    try {
      return window.localStorage.getItem(ACK_KEY) !== '1';
    } catch {
      return true;
    }
  });

  useEffect(() => {
    if (forceOpen) setOpen(true);
  }, [forceOpen]);

  if (!open) return null;

  const handleAck = () => {
    try { window.localStorage.setItem(ACK_KEY, '1'); } catch { /* private mode: ignore */ }
    setOpen(false);
    onAcknowledge?.();
  };

  return (
    <div className="disclaimer-overlay" role="dialog" aria-modal="true" aria-labelledby="disclaimer-title">
      <div className="disclaimer-modal">
        <div className="disclaimer-header">
          <span className="disclaimer-badge">RESEARCH USE ONLY</span>
          <h2 id="disclaimer-title">Before you continue</h2>
        </div>

        <div className="disclaimer-body">
          <p>
            This application is a <strong>reference implementation</strong> that
            demonstrates real-time polyp-detection inference on Intel hardware
            using pre-trained open models.
          </p>
          <p className="disclaimer-not-for">
            It is <strong>not a medical device</strong>, is <strong>not FDA / CE-marked</strong>,
            and <strong>must not be used for clinical diagnosis, treatment, or
            any patient-care decision</strong>.
          </p>
          <ul className="disclaimer-list">
            <li>Model output is provided as-is; no accuracy or safety guarantees.</li>
            <li>Video sources and uploaded files are processed locally on this host.</li>
            <li>Intended audience: engineers, researchers, and demonstration reviewers.</li>
          </ul>
        </div>

        <div className="disclaimer-footer">
          <button type="button" className="disclaimer-btn" onClick={handleAck}>
            I understand — continue
          </button>
        </div>
      </div>
    </div>
  );
};

export default DisclaimerModal;
