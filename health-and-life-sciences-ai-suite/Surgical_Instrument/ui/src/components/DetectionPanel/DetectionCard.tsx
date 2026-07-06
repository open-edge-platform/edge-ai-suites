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
  /** Session KPIs (per Start→Stop). When any is provided a session bar is rendered. */
  sessionDistinctPolyps?: number;
  sessionFramesProcessed?: number;
  sessionFramesWithDetection?: number;
  sessionRate?: number;         // 0..1
  sessionPeakConfidence?: number; // 0..1
  sessionSeconds?: number;      // wall time since Start
}

const DetectionCard: React.FC<DetectionCardProps> = ({
  title,
  icon,
  detected,
  confidence,
  detail,
  lastSeenSeconds,
  hero = false,
  sessionDistinctPolyps,
  sessionFramesProcessed,
  sessionFramesWithDetection,
  sessionRate,
  sessionPeakConfidence,
  sessionSeconds,
}) => {
  const isLowConf = confidence !== null && confidence < 0.5;

  const formatLastSeen = (s: number) => {
    if (s < 60)   return `${s}s ago`;
    if (s < 3600) return `${Math.floor(s / 60)}m ago`;
    return `>${Math.floor(s / 3600)}h ago`;
  };

  const formatSessionTime = (s: number) => {
    const total = Math.max(0, Math.floor(s));
    const mm = Math.floor(total / 60);
    const ss = total % 60;
    return `${mm}:${ss.toString().padStart(2, '0')}`;
  };

  const showSession = [
    sessionDistinctPolyps,
    sessionFramesProcessed,
    sessionFramesWithDetection,
    sessionRate,
    sessionPeakConfidence,
    sessionSeconds,
  ].some((v) => v !== undefined);

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

        {/* Row 3: session KPIs (per Start→Stop) — grid table */}
        {showSession && (
          <div className="det-session">
            <div className="det-session-header">
              <span className="det-session-label">SESSION</span>
              {sessionSeconds !== undefined && sessionSeconds > 0 && (
                <span className="det-session-time">
                  <span className="det-session-time-icon">⏱</span>
                  {formatSessionTime(sessionSeconds)}
                </span>
              )}
            </div>
            <div className="det-session-grid">
              {sessionDistinctPolyps !== undefined && (
                <div className="det-session-cell det-session-cell--hero">
                  <span className="det-session-value">{sessionDistinctPolyps.toLocaleString()}</span>
                  <span className="det-session-label-sm">Polyps detected</span>
                </div>
              )}
              <div className="det-session-cell">
                <span className="det-session-value">{(sessionFramesProcessed ?? 0).toLocaleString()}</span>
                <span className="det-session-label-sm">Frames processed</span>
              </div>
              <div className="det-session-cell">
                <span className="det-session-value">{(sessionFramesWithDetection ?? 0).toLocaleString()}</span>
                <span className="det-session-label-sm">Frames with polyp</span>
              </div>
              <div className="det-session-cell">
                <span className="det-session-value">{((sessionRate ?? 0) * 100).toFixed(1)}%</span>
                <span className="det-session-label-sm">Detection rate</span>
              </div>
              {sessionPeakConfidence !== undefined && sessionPeakConfidence > 0 && (
                <div className="det-session-cell det-session-cell--conf">
                  <span className="det-session-value">{(sessionPeakConfidence * 100).toFixed(1)}%</span>
                  <span className="det-session-label-sm">Peak confidence</span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default DetectionCard;