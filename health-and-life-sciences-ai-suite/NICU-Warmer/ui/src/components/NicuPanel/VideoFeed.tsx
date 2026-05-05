import React, { useEffect, useRef, useState } from 'react';
import type { NicuState } from '../../types/nicu';

interface VideoFeedProps {
  frameUrl: string | null;
  fps: number;
  systemStatus: NicuState['systemStatus'];
  patientDetected: boolean;
  caretakerDetected: boolean;
  caretakerCount: number;
  latchState: string;
}

/**
 * Displays the live video feed from the backend by polling /frame/latest.
 * Uses base64-encoded JPEG polling instead of MJPEG multipart streaming
 * to avoid browser connection issues caused by React re-renders.
 */
const VideoFeed: React.FC<VideoFeedProps> = ({
  frameUrl,
  fps,
  systemStatus,
  patientDetected,
  caretakerDetected,
  caretakerCount,
  latchState,
}) => {
  const [frameSrc, setFrameSrc] = useState<string | null>(null);
  const [stale, setStale] = useState(false);
  const cancelRef = useRef(false);
  const failCountRef = useRef(0);
  const lastGoodRef = useRef<string | null>(null);

  useEffect(() => {
    if (!frameUrl) {
      setFrameSrc(null);
      setStale(false);
      lastGoodRef.current = null;
      return;
    }

    cancelRef.current = false;
    failCountRef.current = 0;

    const baseUrl = frameUrl.replace(/\/video_feed$/, '');

    const poll = async () => {
      while (!cancelRef.current) {
        try {
          const res = await fetch(`${baseUrl}/frame/latest?base64=1`, { cache: 'no-store' });
          if (!cancelRef.current && res.ok) {
            const json = await res.json();
            if (!cancelRef.current && json.available && json.data) {
              const src = `data:image/jpeg;base64,${json.data}`;
              lastGoodRef.current = src;
              failCountRef.current = 0;
              setFrameSrc(src);
              setStale(false);
            } else {
              failCountRef.current++;
            }
          } else {
            failCountRef.current++;
          }
        } catch {
          failCountRef.current++;
        }

        // After 8+ consecutive failures (~130 ms), mark stale so we show
        // a loading overlay instead of the flickering image.
        if (failCountRef.current >= 8 && !cancelRef.current) {
          setStale(true);
        }

        await new Promise((r) => setTimeout(r, 16));
      }
    };

    poll();

    return () => {
      cancelRef.current = true;
    };
  }, [frameUrl]);

  const statusClass =
    systemStatus === 'running'
      ? 'nicu-video-status--running'
      : systemStatus === 'error'
      ? 'nicu-video-status--error'
      : 'nicu-video-status--other';

  return (
    <div className="nicu-video">
      {/* System status badge */}
      <div className={`nicu-video-status ${statusClass}`}>
        <span
          className={`nicu-video-status-dot ${
            systemStatus === 'running' || systemStatus === 'starting'
              ? 'nicu-video-status-dot--pulse'
              : ''
          }`}
        />
        {systemStatus.toUpperCase()}
      </div>

      {/* Detection overlay badges */}
      <div className="nicu-video-overlays">
        <span className={`nicu-video-tag ${patientDetected ? '' : 'nicu-video-tag--warn'}`}>
          Patient: {patientDetected ? 'Detected' : 'Not Detected'}
        </span>
        <span className={`nicu-video-tag ${caretakerDetected ? '' : 'nicu-video-tag--off'}`}>
          Caretaker: {caretakerDetected ? `Detected (${caretakerCount})` : 'Not Detected'}
        </span>
        <span className={`nicu-video-tag ${latchState === 'closed' ? '' : 'nicu-video-tag--warn'}`}>
          Latch: {latchState.charAt(0).toUpperCase() + latchState.slice(1)}
        </span>
      </div>

      {/* FPS badge */}
      <span className="nicu-video-fps">{fps.toFixed(1)} FPS</span>

      {/* Frame or placeholder */}
      {frameSrc ? (
        <div style={{ position: 'relative', width: '100%' }}>
          <img
            src={frameSrc}
            alt="NICU Warmer Live Feed"
            style={{ display: 'block', width: '100%' }}
          />
          {stale && (
            <div style={{
              position: 'absolute', inset: 0,
              background: 'rgba(0,0,0,0.55)',
              display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center',
              color: '#fff', gap: 8, borderRadius: 'inherit',
            }}>
              <div className="nicu-video-spinner" />
              <span style={{ fontSize: 13, fontWeight: 500 }}>Loading video feed…</span>
            </div>
          )}
        </div>
      ) : (
        <div className="nicu-video-placeholder">
          <span className="nicu-video-placeholder-icon">📹</span>
          <span className="nicu-video-placeholder-label">NICU Warmer Video Feed</span>
          <span className="nicu-video-placeholder-sub">
            Connect backend to stream live frames with detection overlays
          </span>
        </div>
      )}
    </div>
  );
};

export default VideoFeed;