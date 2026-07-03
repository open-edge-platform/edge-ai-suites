import React from 'react';

interface DetectionCardProps {
  title: string;
  icon: string;
  detected: boolean;
  confidence: number | null;
  detail?: string;
  lastSeenSeconds?: number;
  /** When true, renders a larger hero variant suitable for a full-width slot. */
  hero?: boolean;
  /** Session-cumulative stats. When any is provided a session bar is rendered. */
  sessionCumulative?: number;
  sessionFrames?: number;
  sessionRate?: number; // 0..1
}

const DetectionCard: React.FC<DetectionCardProps> = ({
  title,
  icon,
  detected,
  confidence,
  detail,
  lastSeenSeconds,
  hero = false,
  sessionCumulative,
  sessionFrames,
  sessionRate,
}) => {
  const isLowConf = confidence !== null && confidence < 0.5;

  const formatLastSeen = (s: number) => {
    if (s < 60)   return `${s}s ago`;
    if (s < 3600) return `${Math.floor(s / 60)}m ago`;
    return `>${Math.floor(s / 3600)}h ago`;
  };

  const showSession = sessionCumulative !== undefined || sessionFrames !== undefined || sessionRate !== undefined;

  return (
    <div className={`nicu-det-card ${hero ? 'nicu-det-card--hero' : ''} ${detected ? 'nicu-det-card--on' : 'nicu-det-card--off'}`}>
      <div className="nicu-det-accent" />

      <div className="nicu-det-body">
        {/* Row 1: icon + title + pill */}
        <div className="nicu-det-row">
          <span className="nicu-det-icon">{icon}</span>
          <span className="nicu-det-title">{title}</span>
          {detected && confidence !== null && !isLowConf && (
            <span className="nicu-det-conf-inline">conf {confidence.toFixed(2)}</span>
          )}
          <span className={`nicu-det-pill ${detected ? 'nicu-det-pill--on' : 'nicu-det-pill--off'}`}>
            {detected ? '✓ DETECTED' : '✗ NOT DETECTED'}
          </span>
        </div>

        {/* Row 2: detail / last-seen / low-conf warning */}
        <div className="nicu-det-row nicu-det-row--sub">
          {detected ? (
            <>
              <span className="nicu-det-sub">{detail ?? 'Present'}</span>
              {isLowConf && (
                <span className="nicu-det-conf nicu-det-conf--warn">
                  ⚠ low conf {confidence !== null ? confidence.toFixed(2) : ''}
                </span>
              )}
            </>
          ) : (
            <>
              <span className="nicu-det-sub nicu-det-sub--absent">No polyp in current frame</span>
              {lastSeenSeconds !== undefined && (
                <span className="nicu-det-conf">
                  {formatLastSeen(lastSeenSeconds)}
                </span>
              )}
            </>
          )}
        </div>

        {/* Row 3: session cumulative */}
        {showSession && (
          <div className="nicu-det-session">
            <span className="nicu-det-session-label">SESSION</span>
            <span className="nicu-det-session-metric">
              <strong>{(sessionCumulative ?? 0).toLocaleString()}</strong>
              <span className="nicu-det-session-unit">detections</span>
            </span>
            <span className="nicu-det-session-sep">·</span>
            <span className="nicu-det-session-metric">
              <strong>{((sessionRate ?? 0) * 100).toFixed(1)}%</strong>
              <span className="nicu-det-session-unit">of frames</span>
            </span>
            {sessionFrames !== undefined && sessionFrames > 0 && (
              <>
                <span className="nicu-det-session-sep">·</span>
                <span className="nicu-det-session-metric">
                  <strong>{sessionFrames.toLocaleString()}</strong>
                  <span className="nicu-det-session-unit">positive frames</span>
                </span>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default DetectionCard;