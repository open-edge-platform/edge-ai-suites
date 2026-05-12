import React, { useRef } from 'react';
import type { ActionData } from '../../types/nicu';

interface ActionCardProps {
  action: ActionData;
}

const MOTION_COLORS: Record<string, string> = {
  still: '#4caf50',
  low: '#8bc34a',
  moderate: '#ff9800',
  high: '#f44336',
  unknown: '#999',
};

// Hold movement state for this many ms so the user can read it
const STICKY_HOLD_MS = 2000;

const ActionCard: React.FC<ActionCardProps> = ({ action }) => {
  const isValid = action.status === 'valid';
  const isError = action.status === 'error';
  const motionLevel = action.motion_level || 'unknown';
  const topActivity = action.top_activity || 'Unknown';
  const isModelStill = topActivity === 'Resting / Still';
  const isMotionStill = motionLevel === 'still';
  const liveStill = isMotionStill && isModelStill;

  // --- Sticky hold: keep movement visible for STICKY_HOLD_MS ---
  const lastMovement = useRef<{ activity: string; confidence: number; motionLevel: string; time: number } | null>(null);

  const now = Date.now();
  if (!liveStill && isValid && !isError) {
    // Movement detected — capture it
    lastMovement.current = {
      activity: topActivity,
      confidence: action.top_confidence,
      motionLevel,
      time: now,
    };
  }

  // Use sticky movement if within hold window
  const sticky = lastMovement.current;
  const withinHold = sticky != null && (now - sticky.time) < STICKY_HOLD_MS;
  const isStill = liveStill && !withinHold;

  // Determine display state
  let cardMod: string;
  let pillMod: string;
  let pillText: string;
  let subText: string;
  let confColor: string;
  let confValue: number;

  if (isError) {
    cardMod = 'nicu-det-card--off';
    pillMod = 'nicu-det-pill--off';
    pillText = '✗ ERR';
    subText = 'Error';
    confColor = '#999';
    confValue = 0;
  } else if (!isValid || isStill) {
    cardMod = 'nicu-det-card--on';
    pillMod = 'nicu-det-pill--on';
    pillText = 'STILL';
    subText = 'Patient still · No activity';
    confColor = MOTION_COLORS.still;
    confValue = action.top_confidence;
  } else if (withinHold && sticky) {
    // Showing held movement from a moment ago
    cardMod = 'nicu-det-card--warn';
    pillMod = 'nicu-det-pill--warn';
    pillText = ' MOVEMENT';
    subText = sticky.activity;
    confColor = MOTION_COLORS[sticky.motionLevel] || '#ff9800';
    confValue = sticky.confidence;
  } else {
    // Live movement
    cardMod = 'nicu-det-card--warn';
    pillMod = 'nicu-det-pill--warn';
    pillText = '⚡ MOVEMENT';
    subText = topActivity;
    confColor = MOTION_COLORS[motionLevel] || '#ff9800';
    confValue = action.top_confidence;
  }

  return (
    <div className={`nicu-det-card ${cardMod}`}>
      <div className="nicu-det-accent" />
      <div className="nicu-det-body">
        <div className="nicu-det-row">
          <span className="nicu-det-title">Activity</span>
          <span className={`nicu-det-pill ${pillMod}`}>{pillText}</span>
        </div>
        <div className="nicu-det-row nicu-det-row--sub">
          <span className="nicu-det-sub">{subText}</span>
          {isValid && (
            <span className="nicu-det-conf" style={{ color: confColor, fontWeight: 600 }}>
              {(confValue * 100).toFixed(0)}%
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

export default ActionCard;
