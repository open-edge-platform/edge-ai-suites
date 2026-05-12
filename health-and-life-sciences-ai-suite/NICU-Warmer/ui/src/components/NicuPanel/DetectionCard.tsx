import React from 'react';

interface DetectionCardProps {
  title: string;
  icon: string;
  detected: boolean;
  confidence: number | null;
  detail?: string;
  lastSeenSeconds?: number;
}

const DetectionCard: React.FC<DetectionCardProps> = ({
  title,
  icon,
  detected,
  confidence,
  detail,
  lastSeenSeconds,
}) => {
  const isLowConf = confidence !== null && confidence < 0.5;

  const formatLastSeen = (s: number) => {
    if (s < 60)   return `${s}s ago`;
    if (s < 3600) return `${Math.floor(s / 60)}m ago`;
    return `>${Math.floor(s / 3600)}h ago`;
  };

  return (
    <div className={`nicu-det-card ${detected ? 'nicu-det-card--on' : 'nicu-det-card--off'}`}>
      <div className="nicu-det-accent" />

      <div className="nicu-det-body">
        {/* Row 1: icon + title + pill */}
        <div className="nicu-det-row">
          <span className="nicu-det-icon">{icon}</span>
          <span className="nicu-det-title">{title}</span>
          <span className={`nicu-det-pill ${detected ? 'nicu-det-pill--on' : 'nicu-det-pill--off'}`}>
            {detected ? '✓ YES' : '✗ NO'}
          </span>
        </div>

        {/* Row 2: detail / last-seen / low-conf warning */}
        <div className="nicu-det-row nicu-det-row--sub">
          {detected ? (
            <>
              <span className="nicu-det-sub">{detail ?? 'Present'}</span>
              {isLowConf && (
                <span className="nicu-det-conf nicu-det-conf--warn">
                  ⚠ low conf
                </span>
              )}
            </>
          ) : (
            <>
              <span className="nicu-det-sub nicu-det-sub--absent">Not detected</span>
              {lastSeenSeconds !== undefined && (
                <span className="nicu-det-conf">
                  {formatLastSeen(lastSeenSeconds)}
                </span>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default DetectionCard;