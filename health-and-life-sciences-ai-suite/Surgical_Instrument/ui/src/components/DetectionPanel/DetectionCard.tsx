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
    <div className={`det-card ${hero ? 'det-card--hero' : ''} ${detected ? 'det-card--on' : 'det-card--off'}`}>
      <div className="det-accent" />

      <div className="det-body">
        {/* Row 1: icon + title + pill */}
        <div className="det-row">
          <span className="det-icon">{icon}</span>
          <span className="det-title">{title}</span>
          {detected && confidence !== null && !isLowConf && (
            <span className="det-conf-inline">conf {confidence.toFixed(2)}</span>
          )}
          <span className={`det-pill ${detected ? 'det-pill--on' : 'det-pill--off'}`}>
            {detected ? '✓ DETECTED' : '✗ NOT DETECTED'}
          </span>
        </div>

        {/* Row 2: detail / last-seen / low-conf warning */}
        <div className="det-row det-row--sub">
          {detected ? (
            <>
              <span className="det-sub">{detail ?? 'Present'}</span>
              {isLowConf && (
                <span className="det-conf det-conf--warn">
                  ⚠ low conf {confidence !== null ? confidence.toFixed(2) : ''}
                </span>
              )}
            </>
          ) : (
            <>
              <span className="det-sub det-sub--absent">No polyp in current frame</span>
              {lastSeenSeconds !== undefined && (
                <span className="det-conf">
                  {formatLastSeen(lastSeenSeconds)}
                </span>
              )}
            </>
          )}
        </div>

        {/* Row 3: session cumulative */}
        {showSession && (
          <div className="det-session">
            <span className="det-session-label">SESSION</span>
            <span className="det-session-metric">
              <strong>{(sessionCumulative ?? 0).toLocaleString()}</strong>
              <span className="det-session-unit">detections</span>
            </span>
            <span className="det-session-sep">·</span>
            <span className="det-session-metric">
              <strong>{((sessionRate ?? 0) * 100).toFixed(1)}%</strong>
              <span className="det-session-unit">of frames</span>
            </span>
            {sessionFrames !== undefined && sessionFrames > 0 && (
              <>
                <span className="det-session-sep">·</span>
                <span className="det-session-metric">
                  <strong>{sessionFrames.toLocaleString()}</strong>
                  <span className="det-session-unit">positive frames</span>
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