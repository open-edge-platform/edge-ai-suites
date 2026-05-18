import React from 'react';
import type { LatchStatus } from '../../types/nicu';

/** Simple SVG padlock — closed or open */
function PadlockIcon({ closed }: { closed: boolean }) {
  return closed ? (
    // Closed padlock
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="nicu-latch-icon">
      <rect x="3" y="7" width="10" height="8" rx="1.5" fill="#2e7d32" />
      <path d="M5 7V5a3 3 0 0 1 6 0v2" stroke="#2e7d32" strokeWidth="1.5" strokeLinecap="round" fill="none" />
      <circle cx="8" cy="11" r="1.2" fill="#fff" />
    </svg>
  ) : (
    // Open padlock
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="nicu-latch-icon">
      <rect x="3" y="7" width="10" height="8" rx="1.5" fill="#e65100" />
      <path d="M5 7V5a3 3 0 0 1 6 0" stroke="#e65100" strokeWidth="1.5" strokeLinecap="round" fill="none" />
      <circle cx="8" cy="11" r="1.2" fill="#fff" />
    </svg>
  );
}

const LatchStatusCard: React.FC<{ latch: LatchStatus }> = ({ latch }) => {
  const isClosed  = latch.state === 'closed';
  const isOpen    = latch.state === 'open';

  const cardMod  = isClosed ? 'nicu-det-card--on' : isOpen ? 'nicu-det-card--warn' : 'nicu-det-card--off';
  const pillMod  = isClosed ? 'nicu-det-pill--on'  : isOpen ? 'nicu-det-pill--warn' : 'nicu-det-pill--off';
  const pillText = isClosed ? '✓ CLOSED' : isOpen ? '✗ OPEN' : '? UNKNOWN';
  const subText  = isClosed ? 'Warmer secured' : isOpen ? 'Check latch now' : 'State unknown';

  return (
    <div className={`nicu-det-card ${cardMod}`}>
      <div className="nicu-det-accent" />
      <div className="nicu-det-body">
        <div className="nicu-det-row">
          {/* SVG padlock instead of emoji/signal dots */}
          <PadlockIcon closed={isClosed} />
          <span className="nicu-det-title">Latch</span>
          <span className={`nicu-det-pill ${pillMod}`}>{pillText}</span>
        </div>
        <div className="nicu-det-row nicu-det-row--sub">
          <span className={`nicu-det-sub${isOpen ? ' nicu-det-sub--absent' : ''}`}>
            {subText}
          </span>
        </div>
      </div>
    </div>
  );
};

export default LatchStatusCard;